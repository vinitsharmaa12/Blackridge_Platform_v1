"""Provider-agnostic LLM client abstraction."""
from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx

from insights.config import InsightsSettings
from insights.schemas import LLMResponse, LLMUsage, ModelSpec, ToolCallRequest

logger = logging.getLogger(__name__)

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_latest_metrics",
            "description": "Latest metrics row for a symbol.",
            "parameters": {
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_metric_series",
            "description": "Time-series for one metrics field between ISO timestamps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "field": {"type": "string"},
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                },
                "required": ["symbol", "field", "from", "to"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_chain",
            "description": "Option chain snapshot at a timestamp or latest.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "at": {"type": "string", "description": "ISO timestamp or 'latest'"},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_sessions",
            "description": "Metric deltas between two session dates (YYYY-MM-DD).",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "date_a": {"type": "string"},
                    "date_b": {"type": "string"},
                },
                "required": ["symbol", "date_a", "date_b"],
            },
        },
    },
]


class LLMClient(ABC):
    @abstractmethod
    def chat(
        self,
        *,
        model: ModelSpec,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        use_prompt_cache: bool = False,
    ) -> LLMResponse:
        """Single chat turn; may return tool_calls or final content."""


class MockLLMClient(LLMClient):
    """Deterministic client for contract tests."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def chat(
        self,
        *,
        model: ModelSpec,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        use_prompt_cache: bool = False,
    ) -> LLMResponse:
        self.calls.append(
            {
                "model": model.model_id,
                "provider": model.provider.value,
                "use_prompt_cache": use_prompt_cache,
                "messages": messages,
            }
        )
        if not self._responses:
            return LLMResponse(content="{}", model_id=model.model_id)
        return self._responses.pop(0)


class OpenRouterClient(LLMClient):
    def __init__(self, settings: InsightsSettings) -> None:
        self._settings = settings

    def chat(
        self,
        *,
        model: ModelSpec,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        use_prompt_cache: bool = False,
    ) -> LLMResponse:
        if not self._settings.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not configured")

        payload: dict[str, Any] = {
            "model": model.model_id,
            "max_tokens": self._settings.insights_max_tokens,
            "messages": [{"role": "system", "content": system}, *messages],
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self._settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        started = time.perf_counter()
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{self._settings.openrouter_base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        latency_ms = (time.perf_counter() - started) * 1000
        choice = data["choices"][0]["message"]
        usage_raw = data.get("usage") or {}
        usage = LLMUsage(
            input_tokens=int(usage_raw.get("prompt_tokens") or 0),
            output_tokens=int(usage_raw.get("completion_tokens") or 0),
        )
        tool_calls = _parse_openai_tool_calls(choice.get("tool_calls") or [])
        return LLMResponse(
            content=choice.get("content"),
            tool_calls=tool_calls,
            usage=usage,
            model_id=model.model_id,
            latency_ms=latency_ms,
        )


class AnthropicClient(LLMClient):
    """Native Anthropic path — supports prompt caching on the system block."""

    def __init__(self, settings: InsightsSettings) -> None:
        self._settings = settings

    def chat(
        self,
        *,
        model: ModelSpec,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        use_prompt_cache: bool = False,
    ) -> LLMResponse:
        if not self._settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")

        import anthropic

        system_block: list[dict[str, Any]]
        if use_prompt_cache:
            system_block = [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            system_block = [{"type": "text", "text": system}]

        anthropic_tools = _to_anthropic_tools(tools or [])
        anthropic_messages = _to_anthropic_messages(messages)

        started = time.perf_counter()
        client = anthropic.Anthropic(api_key=self._settings.anthropic_api_key)
        response = client.messages.create(
            model=model.model_id,
            max_tokens=self._settings.insights_max_tokens,
            system=system_block,
            messages=anthropic_messages,
            tools=anthropic_tools or anthropic.NOT_GIVEN,
        )
        latency_ms = (time.perf_counter() - started) * 1000

        usage = LLMUsage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cached_tokens=getattr(response.usage, "cache_read_input_tokens", 0) or 0,
        )
        content_parts: list[str] = []
        tool_calls: list[ToolCallRequest] = []
        for block in response.content:
            if block.type == "text":
                content_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCallRequest(
                        id=block.id,
                        name=block.name,
                        arguments=block.input if isinstance(block.input, dict) else {},
                    )
                )

        return LLMResponse(
            content="\n".join(content_parts) if content_parts else None,
            tool_calls=tool_calls,
            usage=usage,
            model_id=model.model_id,
            latency_ms=latency_ms,
        )


def build_client(spec: ModelSpec, settings: InsightsSettings) -> LLMClient:
    if spec.provider.value == "anthropic":
        return AnthropicClient(settings)
    return OpenRouterClient(settings)


def _parse_openai_tool_calls(raw: list[dict[str, Any]]) -> list[ToolCallRequest]:
    calls: list[ToolCallRequest] = []
    for item in raw:
        fn = item.get("function") or {}
        args_raw = fn.get("arguments") or "{}"
        try:
            args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
        except json.JSONDecodeError:
            args = {}
        calls.append(
            ToolCallRequest(
                id=str(item.get("id") or ""),
                name=str(fn.get("name") or ""),
                arguments=args if isinstance(args, dict) else {},
            )
        )
    return calls


def _to_anthropic_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for tool in tools:
        fn = tool.get("function") or {}
        out.append(
            {
                "name": fn.get("name"),
                "description": fn.get("description"),
                "input_schema": fn.get("parameters") or {"type": "object", "properties": {}},
            }
        )
    return out


def _to_anthropic_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for msg in messages:
        role = msg["role"]
        if role == "tool":
            converted.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.get("tool_call_id", ""),
                            "content": msg.get("content", ""),
                        }
                    ],
                }
            )
            continue
        if role == "assistant" and msg.get("tool_calls"):
            content: list[dict[str, Any]] = []
            if msg.get("content"):
                content.append({"type": "text", "text": msg["content"]})
            for tc in msg["tool_calls"]:
                fn = tc.get("function") or {}
                args_raw = fn.get("arguments") or "{}"
                args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                content.append(
                    {
                        "type": "tool_use",
                        "id": tc.get("id"),
                        "name": fn.get("name"),
                        "input": args,
                    }
                )
            converted.append({"role": "assistant", "content": content})
            continue
        converted.append({"role": role, "content": msg.get("content") or ""})
    return converted
