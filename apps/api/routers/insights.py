"""Insights routes."""
from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from apps.api.auth import AuthUser, get_current_user
from apps.api.db import fetch_insights, fetch_instrument, user_connection
from apps.api.models import Insight, InsightJobResponse

router = APIRouter(prefix="/instruments", tags=["insights"])

# Stub queue until PRD 004 worker consumes jobs.
_insight_jobs: dict[str, dict[str, str]] = {}


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

    job_id = str(uuid4())
    _insight_jobs[job_id] = {"status": "queued", "symbol": symbol.upper(), "user_id": str(user.id)}
    body = InsightJobResponse(job_id=job_id).model_dump()
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=body)
