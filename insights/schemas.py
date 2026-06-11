"""Pydantic schemas for the insights agent."""
from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class TaskType(StrEnum):
    SNAPSHOT_SUMMARY = "snapshot_summary"
    SESSION_CLOSE = "session_close"


class ModelTier(StrEnum):
    CHEAP = "cheap"
    PREMIUM = "premium"


class ModelProvider(StrEnum):
    OPENROUTER = "openrouter"
    ANTHROPIC = "anthropic"


class ModelSpec(BaseModel):
    model_id: str
    tier: ModelTier
    provider: ModelProvider


class InsightOutput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    narrative: str = Field(min_length=1, max_length=2000)
    sentiment_label: Literal["Bullish", "Bearish", "Neutral", "Mixed"] | str
    confidence: float = Field(ge=0.0, le=1.0)
    cited_metrics: dict[str, Any] = Field(default_factory=dict)

    @field_validator("confidence")
    @classmethod
    def _round_confidence(cls, value: float) -> float:
        return round(value, 3)


class ToolCallRequest(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class LLMUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0


class LLMResponse(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCallRequest] = Field(default_factory=list)
    usage: LLMUsage = Field(default_factory=LLMUsage)
    model_id: str = ""
    latency_ms: float = 0.0


class AgentRunResult(BaseModel):
    output: InsightOutput | None = None
    model_id: str = ""
    tier: ModelTier = ModelTier.CHEAP
    escalated: bool = False
    usage: LLMUsage = Field(default_factory=LLMUsage)
    latency_ms: float = 0.0
    error: str | None = None
