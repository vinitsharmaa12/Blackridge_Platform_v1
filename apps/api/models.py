"""Pydantic response models — field names match DB columns."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class Instrument(BaseModel):
    id: int
    symbol: str
    name: str
    type: str
    segment: str | None = None
    lot_size: int | None = None
    tick_size: float | None = None
    active: bool = True


class TopOiStrike(BaseModel):
    strike: float
    oi: int


class LatestSummary(BaseModel):
    underlying: float | None = None
    atm_strike: float | None = None
    top_ce_oi: list[TopOiStrike] = Field(default_factory=list)
    top_pe_oi: list[TopOiStrike] = Field(default_factory=list)


class MetricsRow(BaseModel):
    time: datetime
    instrument_id: int
    expiry: date
    dte: int | None = None
    underlying: float | None = None
    pcr_oi: float | None = None
    pcr_volume: float | None = None
    ce_cog: float | None = None
    pe_cog: float | None = None
    cog_shift: float | None = None
    atm_strike: float | None = None
    atm_iv: float | None = None
    iv_skew: float | None = None
    india_vix: float | None = None
    atm_straddle: float | None = None
    expected_move: float | None = None
    max_pain: float | None = None
    total_ce_oi: int | None = None
    total_pe_oi: int | None = None
    net_ce_oi_change: int | None = None
    net_pe_oi_change: int | None = None
    total_ce_volume: int | None = None
    total_pe_volume: int | None = None
    buy_sell_imbalance: float | None = None
    buildup: str | None = None
    immediate_support: float | None = None
    major_support: float | None = None
    immediate_resistance: float | None = None
    major_resistance: float | None = None
    sentiment_score: int | None = None
    sentiment_label: str | None = None
    drivers: list[Any] = Field(default_factory=list)


class LatestMetricsResponse(BaseModel):
    metrics: MetricsRow
    summary: LatestSummary


class ChainRow(BaseModel):
    time: datetime
    instrument_id: int
    expiry: date
    strike: float
    underlying: float | None = None
    ce_oi: int | None = None
    ce_oi_change: int | None = None
    ce_iv: float | None = None
    ce_ltp: float | None = None
    ce_volume: int | None = None
    pe_oi: int | None = None
    pe_oi_change: int | None = None
    pe_iv: float | None = None
    pe_ltp: float | None = None
    pe_volume: int | None = None
    source: str = "nse"


class Insight(BaseModel):
    id: UUID
    time: datetime
    instrument_id: int
    expiry: date | None = None
    title: str
    narrative: str
    sentiment_label: str | None = None
    confidence: float | None = None
    cited_metrics: Any = None
    model: str | None = None
    user_id: UUID | None = None


class WatchlistEntry(BaseModel):
    id: UUID
    instrument_id: int
    symbol: str
    name: str
    created_at: datetime


class InsightJobResponse(BaseModel):
    job_id: str
    status: Literal["already_generated", "generating"] = "generating"


class InsightJobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "done", "failed"]
    error: str | None = None


class SignalCard(BaseModel):
    key: str
    category: Literal["bias", "levels", "flow", "structure", "volatility"]
    title: str
    text: str
    direction: Literal["bullish", "bearish", "neutral"]
    strength: int
    evidence: dict[str, Any] = Field(default_factory=dict)


class SignalsResponse(BaseModel):
    time: datetime
    underlying: float | None = None
    overall: SignalCard
    signals: list[SignalCard]


class SessionPhaseSnapshot(BaseModel):
    """Matches _ref/session_snap.py + session_snapshot_renderer field names."""

    status: Literal["populated", "pending", "missed"] = "missed"
    window_label: str = ""
    timestamp: str = "N/A"
    underlying: str = "N/A"
    top1ce_strike: str = "N/A"
    top1ce_oi: str = "N/A"
    top2ce_strike: str = "N/A"
    top2ce_oi: str = "N/A"
    top3ce_strike: str = "N/A"
    top3ce_oi: str = "N/A"
    top1pe_strike: str = "N/A"
    top1pe_oi: str = "N/A"
    top2pe_strike: str = "N/A"
    top2pe_oi: str = "N/A"
    top3pe_strike: str = "N/A"
    top3pe_oi: str = "N/A"
    pcr: str = "N/A"
    overall_ce_oi: str = "N/A"
    overall_pe_oi: str = "N/A"
    overall_ce_volume: str = "N/A"
    overall_pe_volume: str = "N/A"


class SessionSnapshotsResponse(BaseModel):
    date: str
    requested_date: str
    resolved_date: str
    date_fallback: bool = False
    morning: SessionPhaseSnapshot
    midday: SessionPhaseSnapshot
    evening: SessionPhaseSnapshot


class HealthResponse(BaseModel):
    status: str
    db: str
