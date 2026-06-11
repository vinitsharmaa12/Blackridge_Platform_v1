"""Model routing and escalation tests."""
from __future__ import annotations

import pytest

from insights.config import InsightsSettings
from insights.router import escalation_model, select_model, should_escalate
from insights.schemas import ModelProvider, ModelTier, TaskType


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> InsightsSettings:
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")
    monkeypatch.setenv("INSIGHTS_MODEL_CHEAP", "google/gemini-flash")
    monkeypatch.setenv("INSIGHTS_MODEL_PREMIUM", "anthropic/claude-sonnet-4")
    monkeypatch.setenv("INSIGHTS_PREMIUM_NATIVE", "false")
    monkeypatch.setenv("INSIGHTS_ESCALATE_CONFIDENCE", "0.6")
    return InsightsSettings()  # type: ignore[call-arg]


def test_select_model_cheap_for_snapshot(settings: InsightsSettings) -> None:
    spec = select_model(TaskType.SNAPSHOT_SUMMARY, settings)
    assert spec.tier == ModelTier.CHEAP
    assert spec.model_id == "google/gemini-flash"
    assert spec.provider == ModelProvider.OPENROUTER


def test_select_model_premium_for_session_close(settings: InsightsSettings) -> None:
    spec = select_model(TaskType.SESSION_CLOSE, settings)
    assert spec.tier == ModelTier.PREMIUM
    assert spec.model_id == "anthropic/claude-sonnet-4"


def test_select_model_premium_native(
    settings: InsightsSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("INSIGHTS_PREMIUM_NATIVE", "true")
    cfg = InsightsSettings()  # type: ignore[call-arg]
    spec = select_model(TaskType.SESSION_CLOSE, cfg)
    assert spec.provider == ModelProvider.ANTHROPIC


def test_escalation_model_uses_premium(settings: InsightsSettings) -> None:
    spec = escalation_model(settings)
    assert spec.tier == ModelTier.PREMIUM


def test_should_escalate_on_validation_error() -> None:
    assert should_escalate(validation_error="bad json", confidence=None, threshold=0.6)


def test_should_escalate_on_low_confidence() -> None:
    assert should_escalate(validation_error=None, confidence=0.4, threshold=0.6) is True
    assert should_escalate(validation_error=None, confidence=0.8, threshold=0.6) is False
