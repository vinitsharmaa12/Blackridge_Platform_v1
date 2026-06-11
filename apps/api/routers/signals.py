"""Deterministic signal card routes (PRD 002.5)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from apps.api.auth import AuthUser, get_current_user
from apps.api.db import (
    fetch_day_underlying_range,
    fetch_instrument,
    fetch_latest_metrics,
    fetch_metrics_at_time,
    fetch_prev_metrics,
    user_connection,
)
from apps.api.metrics_core import metrics_row_from_db
from apps.api.models import SignalCard, SignalsResponse
from core.signals import DayContext, Signal, build_signals

router = APIRouter(prefix="/instruments", tags=["signals"])


def _parse_at_param(at: str) -> datetime | None:
    if at == "latest":
        return None
    try:
        return datetime.fromisoformat(at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="at must be 'latest' or an ISO-8601 timestamp",
        ) from exc


def _day_start(at_time: datetime) -> datetime:
    return at_time.replace(hour=0, minute=0, second=0, microsecond=0)


def _signal_to_card(signal: Signal) -> SignalCard:
    return SignalCard(
        key=signal.key,
        category=signal.category,
        title=signal.title,
        text=signal.text,
        direction=signal.direction,
        strength=signal.strength,
        evidence=dict(signal.evidence),
    )


@router.get("/{symbol}/signals", response_model=SignalsResponse)
async def instrument_signals(
    symbol: str,
    at: str = Query("latest"),
    user: AuthUser = Depends(get_current_user),
) -> SignalsResponse:
    at_time = _parse_at_param(at)

    async with user_connection(user) as conn:
        inst = await fetch_instrument(conn, symbol)
        if inst is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown symbol")

        if at_time is None:
            metrics_row = await fetch_latest_metrics(conn, inst["id"])
        else:
            metrics_row = await fetch_metrics_at_time(conn, inst["id"], at_time)

        if metrics_row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No metrics yet")

        snap_time = metrics_row["time"]
        prev_row = await fetch_prev_metrics(conn, inst["id"], snap_time)
        day_start = _day_start(snap_time)
        day_open, day_high, day_low = await fetch_day_underlying_range(
            conn, inst["id"], day_start, snap_time
        )

    curr = metrics_row_from_db(metrics_row)
    prev = metrics_row_from_db(prev_row) if prev_row else None
    day = DayContext(open=day_open, high=day_high, low=day_low)

    ranked = build_signals(curr, prev=prev, day=day)
    overall = next((s for s in ranked if s.key == "overall_read"), ranked[0])

    return SignalsResponse(
        time=snap_time,
        underlying=metrics_row.get("underlying"),
        overall=_signal_to_card(overall),
        signals=[_signal_to_card(s) for s in ranked],
    )
