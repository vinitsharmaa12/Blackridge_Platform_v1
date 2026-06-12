"""Model-agnostic insight agent loop."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import psycopg
from pydantic import ValidationError

from insights.config import InsightsSettings
from insights.llm import TOOL_DEFINITIONS, LLMClient
from insights.router import escalation_model, log_run_tier, select_model, should_escalate
from insights.schemas import AgentRunResult, InsightOutput, LLMUsage, ModelSpec, ModelTier, TaskType
from insights.tools import dispatch_tool

logger = logging.getLogger(__name__)

_NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")

_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "system.md"


def load_system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def extract_numbers(text: str) -> set[str]:
    return set(_NUMBER_PATTERN.findall(text))


def _numbers_from_cited(cited: dict[str, Any]) -> set[str]:
    found: set[str] = set()

    def _walk(value: Any) -> None:
        if isinstance(value, bool):
            return
        if isinstance(value, int | float):
            found.add(str(value))
            if isinstance(value, float) and value.is_integer():
                found.add(str(int(value)))
            return
        if isinstance(value, str):
            found.update(extract_numbers(value))
            return
        if isinstance(value, dict):
            for v in value.values():
                _walk(v)
        elif isinstance(value, list):
            for item in value:
                _walk(item)

    _walk(cited)
    return found


def validate_grounding(output: InsightOutput) -> str | None:
    """Return error message if narrative numbers are not grounded in cited_metrics."""
    narrative_nums = extract_numbers(output.narrative)
    if len(narrative_nums) < 2:
        return "narrative must cite at least two numeric data points for signal strength"

    cited_nums = _numbers_from_cited(output.cited_metrics)
    for num in narrative_nums:
        if num not in cited_nums:
            # tolerate integer/float formatting differences
            try:
                fval = float(num)
                alt = {str(int(fval)) if fval.is_integer() else str(fval), f"{fval:.2f}"}
                if not alt & cited_nums:
                    return f"narrative number {num} missing from cited_metrics"
            except ValueError:
                return f"narrative number {num} missing from cited_metrics"
    return None


def parse_insight_output(content: str | None) -> tuple[InsightOutput | None, str | None]:
    if not content:
        return None, "empty model response"
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        payload = json.loads(text)
        return InsightOutput.model_validate(payload), None
    except (json.JSONDecodeError, ValidationError) as exc:
        return None, f"invalid insight JSON: {exc}"


def _run_with_model(
    *,
    client: LLMClient,
    conn: psycopg.Connection,
    symbol: str,
    task_type: TaskType,
    model: ModelSpec,
    settings: InsightsSettings,
) -> tuple[InsightOutput | None, LLMUsage, float, str | None]:
    system = load_system_prompt()
    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": (
                f"Produce a market signal for {symbol.upper()} (task={task_type.value}). "
                "Use tools first. State the signal, justify its strength with at least two "
                "numeric metrics from tools, set confidence to match that strength, then "
                "return JSON only."
            ),
        }
    ]
    total_usage = LLMUsage()
    total_latency = 0.0
    tool_calls_used = 0
    use_cache = model.tier == ModelTier.PREMIUM and model.provider.value == "anthropic"

    for _ in range(settings.insights_max_tool_calls + 1):
        response = client.chat(
            model=model,
            system=system,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            use_prompt_cache=use_cache,
        )
        total_usage.input_tokens += response.usage.input_tokens
        total_usage.output_tokens += response.usage.output_tokens
        total_usage.cached_tokens += response.usage.cached_tokens
        total_latency += response.latency_ms

        if response.tool_calls:
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": response.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in response.tool_calls
                ],
            }
            messages.append(assistant_msg)
            for tc in response.tool_calls:
                tool_calls_used += 1
                if tool_calls_used > settings.insights_max_tool_calls:
                    return None, total_usage, total_latency, "tool call limit exceeded"
                try:
                    tool_result = dispatch_tool(conn, tc.name, tc.arguments)
                except Exception as exc:  # noqa: BLE001
                    tool_result = json.dumps({"error": str(exc)})
                messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": tool_result}
                )
            continue

        output, err = parse_insight_output(response.content)
        if output is None:
            return None, total_usage, total_latency, err
        grounding_err = validate_grounding(output)
        if grounding_err:
            return None, total_usage, total_latency, grounding_err
        return output, total_usage, total_latency, None

    return None, total_usage, total_latency, "agent loop exhausted"


def run_agent(
    conn: psycopg.Connection,
    symbol: str,
    client: LLMClient,
    settings: InsightsSettings,
    *,
    task_type: TaskType = TaskType.SNAPSHOT_SUMMARY,
) -> AgentRunResult:
    """Cheap-first with one premium escalation on validation/confidence failure."""
    primary = select_model(task_type, settings)
    output, usage, latency, err = _run_with_model(
        client=client,
        conn=conn,
        symbol=symbol,
        task_type=task_type,
        model=primary,
        settings=settings,
    )

    escalated = False
    model_id = primary.model_id
    tier = primary.tier

    if (
        output
        and primary.tier == ModelTier.CHEAP
        and should_escalate(
            validation_error=None,
            confidence=output.confidence,
            threshold=settings.insights_escalate_confidence,
        )
    ):
        err = f"confidence {output.confidence} below threshold"
        output = None

    if (
        output is None
        and primary.tier == ModelTier.CHEAP
        and should_escalate(
            validation_error=err,
            confidence=None,
            threshold=settings.insights_escalate_confidence,
        )
    ):
        premium = escalation_model(settings)
        if premium.model_id != primary.model_id or premium.provider != primary.provider:
            escalated = True
            output, premium_usage, premium_latency, err = _run_with_model(
                client=client,
                conn=conn,
                symbol=symbol,
                task_type=task_type,
                model=premium,
                settings=settings,
            )
            usage.input_tokens += premium_usage.input_tokens
            usage.output_tokens += premium_usage.output_tokens
            usage.cached_tokens += premium_usage.cached_tokens
            latency += premium_latency
            model_id = premium.model_id
            tier = premium.tier

    log_run_tier(
        symbol=symbol,
        tier=tier,
        model_id=model_id,
        escalated=escalated,
        usage_input=usage.input_tokens,
        usage_output=usage.output_tokens,
        latency_ms=latency,
    )

    if output is None:
        return AgentRunResult(
            output=None,
            model_id=model_id,
            tier=tier,
            escalated=escalated,
            usage=usage,
            latency_ms=latency,
            error=err or "agent failed",
        )

    return AgentRunResult(
        output=output,
        model_id=model_id,
        tier=tier,
        escalated=escalated,
        usage=usage,
        latency_ms=latency,
    )
