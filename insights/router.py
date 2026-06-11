"""Model tier routing and escalation policy."""
from __future__ import annotations

import logging

from insights.config import InsightsSettings
from insights.schemas import ModelProvider, ModelSpec, ModelTier, TaskType

logger = logging.getLogger(__name__)


def select_model(task_type: TaskType, settings: InsightsSettings) -> ModelSpec:
    """Map task complexity to tier + provider. Model ids come from env only."""
    if task_type == TaskType.SESSION_CLOSE:
        tier = ModelTier.PREMIUM
    else:
        tier = ModelTier.CHEAP

    if tier == ModelTier.PREMIUM and settings.insights_premium_native:
        model_id = settings.insights_model_premium
        provider = ModelProvider.ANTHROPIC
    elif tier == ModelTier.PREMIUM:
        model_id = settings.insights_model_premium
        provider = ModelProvider.OPENROUTER
    else:
        model_id = settings.insights_model_cheap
        provider = ModelProvider.OPENROUTER

    if not model_id:
        raise ValueError(
            f"Model id not configured for tier={tier.value}. "
            "Set INSIGHTS_MODEL_CHEAP and INSIGHTS_MODEL_PREMIUM in env."
        )

    return ModelSpec(model_id=model_id, tier=tier, provider=provider)


def escalation_model(settings: InsightsSettings) -> ModelSpec:
    """Premium tier used when cheap output fails validation or confidence is low."""
    if settings.insights_premium_native:
        return ModelSpec(
            model_id=settings.insights_model_premium,
            tier=ModelTier.PREMIUM,
            provider=ModelProvider.ANTHROPIC,
        )
    return ModelSpec(
        model_id=settings.insights_model_premium,
        tier=ModelTier.PREMIUM,
        provider=ModelProvider.OPENROUTER,
    )


def should_escalate(
    *,
    validation_error: str | None,
    confidence: float | None,
    threshold: float,
) -> bool:
    if validation_error:
        return True
    if confidence is not None and confidence < threshold:
        return True
    return False


def log_run_tier(
    *,
    symbol: str,
    tier: ModelTier,
    model_id: str,
    escalated: bool,
    usage_input: int,
    usage_output: int,
    latency_ms: float,
) -> None:
    logger.info(
        "insight_run symbol=%s tier=%s model=%s escalated=%s "
        "tokens_in=%d tokens_out=%d latency_ms=%.0f",
        symbol,
        tier.value,
        model_id,
        escalated,
        usage_input,
        usage_output,
        latency_ms,
    )
