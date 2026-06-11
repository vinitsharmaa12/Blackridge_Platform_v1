"""Agent contract tests with mocked LLM clients."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from insights.agent import (
    parse_insight_output,
    run_agent,
    validate_grounding,
)
from insights.config import InsightsSettings
from insights.llm import AnthropicClient, MockLLMClient, OpenRouterClient
from insights.schemas import (
    InsightOutput,
    LLMResponse,
    ModelProvider,
    ModelSpec,
    ModelTier,
    TaskType,
)

VALID_OUTPUT = {
    "title": "PCR supports bullish structure",
    "narrative": "PCR OI at 1.25 with underlying 25000 shows bullish positioning.",
    "sentiment_label": "Bullish",
    "confidence": 0.82,
    "cited_metrics": {
        "pcr_oi": 1.25,
        "underlying": 25000,
    },
}


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> InsightsSettings:
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")
    monkeypatch.setenv("INSIGHTS_MODEL_CHEAP", "google/gemini-flash")
    monkeypatch.setenv("INSIGHTS_MODEL_PREMIUM", "anthropic/claude-sonnet-4")
    monkeypatch.setenv("INSIGHTS_PREMIUM_NATIVE", "false")
    monkeypatch.setenv("INSIGHTS_ESCALATE_CONFIDENCE", "0.6")
    return InsightsSettings()  # type: ignore[call-arg]


def test_parse_insight_output_valid() -> None:
    output, err = parse_insight_output(json.dumps(VALID_OUTPUT))
    assert err is None
    assert output is not None
    assert output.title.startswith("PCR")


def test_validate_grounding_rejects_ungrounded_number() -> None:
    output = InsightOutput(
        title="Test",
        narrative="PCR at 1.25 and mystery 99999 level.",
        sentiment_label="Neutral",
        confidence=0.5,
        cited_metrics={"pcr_oi": 1.25},
    )
    assert validate_grounding(output) is not None


def test_validate_grounding_rejects_buy_sell() -> None:
    output = InsightOutput(
        title="Test",
        narrative="You should buy calls now.",
        sentiment_label="Bullish",
        confidence=0.5,
        cited_metrics={"underlying": 25000},
    )
    assert "buy/sell" in (validate_grounding(output) or "")


def test_validate_grounding_accepts_grounded_numbers() -> None:
    output = InsightOutput.model_validate(VALID_OUTPUT)
    assert validate_grounding(output) is None


def test_run_agent_happy_path(settings: InsightsSettings) -> None:
    client = MockLLMClient(
        [
            LLMResponse(
                content=json.dumps(VALID_OUTPUT),
                model_id="google/gemini-flash",
            )
        ]
    )
    conn = MagicMock()
    with patch("insights.agent.dispatch_tool") as mock_dispatch:
        result = run_agent(conn, "NIFTY", client, settings)
    mock_dispatch.assert_not_called()
    assert result.output is not None
    assert result.model_id == "google/gemini-flash"
    assert result.escalated is False


def test_run_agent_escalates_on_low_confidence(settings: InsightsSettings) -> None:
    low_conf = {**VALID_OUTPUT, "confidence": 0.3}
    client = MockLLMClient(
        [
            LLMResponse(content=json.dumps(low_conf), model_id="google/gemini-flash"),
            LLMResponse(content=json.dumps(VALID_OUTPUT), model_id="anthropic/claude-sonnet-4"),
        ]
    )
    conn = MagicMock()
    result = run_agent(conn, "NIFTY", client, settings)
    assert result.escalated is True
    assert result.output is not None
    assert result.output.confidence == 0.82


def test_mock_client_records_openrouter_provider(settings: InsightsSettings) -> None:
    spec = ModelSpec(
        model_id="google/gemini-flash",
        tier=ModelTier.CHEAP,
        provider=ModelProvider.OPENROUTER,
    )
    client = MockLLMClient([LLMResponse(content="{}", model_id=spec.model_id)])
    client.chat(model=spec, system="sys", messages=[], tools=[])
    assert client.calls[0]["provider"] == "openrouter"


def test_mock_client_records_anthropic_cache_flag(settings: InsightsSettings) -> None:
    spec = ModelSpec(
        model_id="anthropic/claude-sonnet-4",
        tier=ModelTier.PREMIUM,
        provider=ModelProvider.ANTHROPIC,
    )
    client = MockLLMClient([LLMResponse(content="{}", model_id=spec.model_id)])
    client.chat(model=spec, system="sys", messages=[], tools=[], use_prompt_cache=True)
    assert client.calls[0]["use_prompt_cache"] is True


def test_llm_client_classes_exist(settings: InsightsSettings) -> None:
    assert OpenRouterClient(settings) is not None
    assert AnthropicClient(settings) is not None


def test_session_close_selects_premium_tier(settings: InsightsSettings) -> None:
    from insights.router import select_model

    spec = select_model(TaskType.SESSION_CLOSE, settings)
    assert spec.tier == ModelTier.PREMIUM
