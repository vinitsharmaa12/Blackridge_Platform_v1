"""Instrument routes."""
from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg import AsyncConnection

from apps.api.auth import AuthUser, get_current_user
from apps.api.config import Settings, get_settings
from apps.api.db import (
    fetch_chain_for_times,
    fetch_day_metrics,
    fetch_instrument,
    fetch_instruments,
    fetch_latest_metrics,
    fetch_recent_metric_days,
    fetch_top_oi_strikes,
    user_connection,
)
from apps.api.models import (
    Instrument,
    LatestMetricsResponse,
    LatestSummary,
    MetricsRow,
    SessionPhaseSnapshot,
    SessionSnapshotsResponse,
    TopOiStrike,
)
from core.session_snapshots import (
    SESSION_WINDOWS,
    build_session_snapshots,
    count_populated_phases,
    day_bounds,
    format_session_date,
    parse_session_date,
    pick_metrics_in_window,
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
            conn,
            inst["id"],
            metrics["time"],
            limit=settings.chain_top_oi_limit,
            underlying=metrics.get("underlying"),
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


def _default_session_date() -> str:
    return date.today().strftime("%Y%m%d")


async def _resolve_session_metrics(
    conn: AsyncConnection,
    instrument_id: int,
    requested: date,
) -> tuple[date, bool, list[dict[str, Any]]]:
    """Return metrics rows for requested day, or fallback to latest day with phase data."""
    day_start, day_end = day_bounds(requested)
    rows = await fetch_day_metrics(
        conn,
        instrument_id,
        day_start=day_start,
        day_end=day_end,
    )
    if count_populated_phases(rows) > 0:
        return requested, False, rows

    recent_days = await fetch_recent_metric_days(conn, instrument_id)
    for candidate_day in recent_days:
        if candidate_day == requested:
            continue
        cand_start, cand_end = day_bounds(candidate_day)
        candidate_rows = await fetch_day_metrics(
            conn,
            instrument_id,
            day_start=cand_start,
            day_end=cand_end,
        )
        if count_populated_phases(candidate_rows) > 0:
            return candidate_day, True, candidate_rows

    return requested, False, rows


@router.get("/{symbol}/session-snapshots", response_model=SessionSnapshotsResponse)
async def session_snapshots(
    symbol: str,
    date_param: str = Query(
        default_factory=_default_session_date,
        alias="date",
        description="Session day as YYYYMMDD (IST wall-clock labels)",
    ),
    user: AuthUser = Depends(get_current_user),
) -> SessionSnapshotsResponse:
    try:
        requested_day = parse_session_date(date_param)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    async with user_connection(user) as conn:
        inst = await fetch_instrument(conn, symbol)
        if inst is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown symbol")
        resolved_day, date_fallback, metrics_rows = await _resolve_session_metrics(
            conn,
            inst["id"],
            requested_day,
        )
        phase_times = []
        for start, end in SESSION_WINDOWS.values():
            row = pick_metrics_in_window(metrics_rows, start, end)
            if row is not None:
                phase_times.append(row["time"])
        chain_by_time = await fetch_chain_for_times(conn, inst["id"], phase_times)
        phases = build_session_snapshots(
            metrics_rows,
            chain_by_time,
            session_date=resolved_day,
        )

    resolved_str = format_session_date(resolved_day)
    return SessionSnapshotsResponse(
        date=resolved_str,
        requested_date=date_param,
        resolved_date=resolved_str,
        date_fallback=date_fallback,
        morning=SessionPhaseSnapshot.model_validate(phases["morning"]),
        midday=SessionPhaseSnapshot.model_validate(phases["midday"]),
        evening=SessionPhaseSnapshot.model_validate(phases["evening"]),
    )
