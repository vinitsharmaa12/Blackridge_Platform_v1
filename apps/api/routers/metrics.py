"""Metrics time-series routes."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from apps.api.auth import AuthUser, get_current_user
from apps.api.config import Settings, get_settings
from apps.api.db import (
    fetch_instrument,
    fetch_metrics_series,
    user_connection,
    validate_metrics_window,
)
from apps.api.models import MetricsRow

router = APIRouter(prefix="/instruments", tags=["metrics"])


@router.get("/{symbol}/metrics", response_model=list[MetricsRow])
async def metrics_series(
    symbol: str,
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = Query(None),
    fields: list[str] | None = Query(None),
    user: AuthUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[MetricsRow]:
    try:
        from_ts, to_ts = validate_metrics_window(
            from_, to, max_days=settings.metrics_max_days
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    try:
        async with user_connection(user) as conn:
            inst = await fetch_instrument(conn, symbol)
            if inst is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown symbol")
            rows = await fetch_metrics_series(
                conn,
                inst["id"],
                from_ts=from_ts,
                to_ts=to_ts,
                fields=fields,
                limit=settings.metrics_max_rows,
            )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    return [MetricsRow.model_validate(r) for r in rows]
