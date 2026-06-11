"""Insights engine configuration from environment."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class InsightsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(alias="DATABASE_URL")

    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        "https://openrouter.ai/api/v1",
        alias="OPENROUTER_BASE_URL",
    )
    insights_model_cheap: str = Field(default="", alias="INSIGHTS_MODEL_CHEAP")
    insights_model_premium: str = Field(default="", alias="INSIGHTS_MODEL_PREMIUM")
    insights_premium_native: bool = Field(False, alias="INSIGHTS_PREMIUM_NATIVE")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    insights_escalate_confidence: float = Field(0.6, alias="INSIGHTS_ESCALATE_CONFIDENCE")
    insights_max_tool_calls: int = Field(8, alias="INSIGHTS_MAX_TOOL_CALLS")
    insights_max_tokens: int = Field(4096, alias="INSIGHTS_MAX_TOKENS")


def get_insights_settings() -> InsightsSettings:
    return InsightsSettings()  # type: ignore[call-arg]
