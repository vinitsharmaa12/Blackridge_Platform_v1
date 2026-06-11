"""Insights routes."""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from apps.api.auth import AuthUser, get_current_user
from apps.api.db import enqueue_insight_job, fetch_insights, fetch_instrument, user_connection
from apps.api.models import Insight, InsightJobResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/instruments", tags=["insights"])
IST = ZoneInfo("Asia/Kolkata")


def _session_date() -> date:
    return datetime.now(tz=IST).astimezone(IST).date()


async def _process_job_background(job_id: UUID) -> None:
    from insights.runner import process_job

    try:
        await asyncio.to_thread(process_job, job_id)
    except Exception:  # noqa: BLE001
        logger.exception("insight_background_failed job_id=%s", job_id)


@router.get("/{symbol}/insights", response_model=list[Insight])
async def list_insights(
    symbol: str,
    limit: int = Query(20, ge=1, le=100),
    user: AuthUser = Depends(get_current_user),
) -> list[Insight]:
    async with user_connection(user) as conn:
        inst = await fetch_instrument(conn, symbol)
        if inst is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown symbol")
        rows = await fetch_insights(conn, inst["id"], limit=limit)
    return [Insight.model_validate(r) for r in rows]


@router.post("/{symbol}/insights:generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_insight(
    symbol: str,
    user: AuthUser = Depends(get_current_user),
) -> JSONResponse:
    async with user_connection(user) as conn:
        inst = await fetch_instrument(conn, symbol)
        if inst is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown symbol")
        job_id = await enqueue_insight_job(
            conn,
            instrument_id=inst["id"],
            symbol=symbol,
            user_id=user.id,
            session_date=_session_date(),
        )

    if job_id is None:
        body = InsightJobResponse(job_id="", status="already_queued").model_dump()
        return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=body)

    asyncio.create_task(_process_job_background(job_id))
    body = InsightJobResponse(job_id=str(job_id)).model_dump()
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=body)
