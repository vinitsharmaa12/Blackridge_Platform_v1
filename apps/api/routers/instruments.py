"""Instrument routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from apps.api.auth import AuthUser, get_current_user
from apps.api.config import Settings, get_settings
from apps.api.db import (
    fetch_instrument,
    fetch_instruments,
    fetch_latest_metrics,
    fetch_top_oi_strikes,
    user_connection,
)
from apps.api.models import (
    Instrument,
    LatestMetricsResponse,
    LatestSummary,
    MetricsRow,
    TopOiStrike,
)

router = APIRouter(prefix="/instruments", tags=["instruments"])


@router.get("", response_model=list[Instrument])
async def list_instruments(user: AuthUser = Depends(get_current_user)) -> list[Instrument]:
    async with user_connection(user) as conn:
        rows = await fetch_instruments(conn)
    return [Instrument.model_validate(r) for r in rows]


@router.get("/{symbol}/latest", response_model=LatestMetricsResponse)
async def latest_metrics(
    symbol: str,
    user: AuthUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> LatestMetricsResponse:
    async with user_connection(user) as conn:
        inst = await fetch_instrument(conn, symbol)
        if inst is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown symbol")
        metrics = await fetch_latest_metrics(conn, inst["id"])
        if metrics is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No metrics yet")
        top_ce, top_pe = await fetch_top_oi_strikes(
            conn, inst["id"], metrics["time"], limit=settings.chain_top_oi_limit
        )
    return LatestMetricsResponse(
        metrics=MetricsRow.model_validate(metrics),
        summary=LatestSummary(
            underlying=metrics.get("underlying"),
            atm_strike=metrics.get("atm_strike"),
            top_ce_oi=[TopOiStrike.model_validate(r) for r in top_ce],
            top_pe_oi=[TopOiStrike.model_validate(r) for r in top_pe],
        ),
    )
