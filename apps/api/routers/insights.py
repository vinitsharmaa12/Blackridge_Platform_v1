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
from apps.api.db import (
    fetch_insights,
    fetch_instrument,
    fetch_today_on_demand_job,
    resolve_on_demand_job,
    user_connection,
    user_has_insight_today,
)
from apps.api.models import Insight, InsightJobResponse, InsightJobStatusResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/instruments", tags=["insights"])
IST = ZoneInfo("Asia/Kolkata")


def _session_date() -> date:
    return datetime.now(tz=IST).astimezone(IST).date()


def _needs_retry(job_status_db: str, has_insight: bool) -> bool:
    return job_status_db in ("failed", "running") or (
        job_status_db == "done" and not has_insight
    )


async def _process_job_background(job_id: UUID) -> None:
    from insights.runner import process_job

    logger.info("insight_background_start job_id=%s", job_id)
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


@router.get("/{symbol}/insights/job", response_model=InsightJobStatusResponse)
async def get_insight_job(
    symbol: str,
    user: AuthUser = Depends(get_current_user),
) -> InsightJobStatusResponse:
    session_day = _session_date()
    async with user_connection(user) as conn:
        inst = await fetch_instrument(conn, symbol)
        if inst is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown symbol")
        job = await fetch_today_on_demand_job(
            conn,
            instrument_id=inst["id"],
            user_id=user.id,
            session_date=session_day,
        )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No insight job for today")
    return InsightJobStatusResponse(
        job_id=str(job["id"]),
        status=job["status"],
        error=job.get("error"),
    )


@router.post("/{symbol}/insights:generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_insight(
    symbol: str,
    user: AuthUser = Depends(get_current_user),
) -> JSONResponse:
    session_day = _session_date()
    async with user_connection(user) as conn:
        inst = await fetch_instrument(conn, symbol)
        if inst is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown symbol")
        job_id, job_status_db = await resolve_on_demand_job(
            conn,
            instrument_id=inst["id"],
            symbol=symbol,
            user_id=user.id,
            session_date=session_day,
        )
        has_insight = await user_has_insight_today(
            conn,
            instrument_id=inst["id"],
            user_id=user.id,
            session_date=session_day,
        )

    if job_status_db == "done" and has_insight:
        body = InsightJobResponse(job_id=str(job_id), status="already_generated").model_dump()
        return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=body)

    if job_status_db in ("queued", "failed", "running") or (
        job_status_db == "done" and not has_insight
    ):
        if _needs_retry(job_status_db, has_insight):
            from insights.runner import reset_job_for_retry_by_id

            reset_job_for_retry_by_id(job_id)
        asyncio.create_task(_process_job_background(job_id))
        body = InsightJobResponse(job_id=str(job_id), status="generating").model_dump()
        return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=body)

    body = InsightJobResponse(job_id=str(job_id), status="generating").model_dump()
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=body)
