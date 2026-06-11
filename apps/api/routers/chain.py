"""Option chain routes."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from apps.api.auth import AuthUser, get_current_user
from apps.api.db import fetch_chain_at, fetch_instrument, user_connection
from apps.api.models import ChainRow

router = APIRouter(prefix="/instruments", tags=["chain"])


@router.get("/{symbol}/chain", response_model=list[ChainRow])
async def option_chain(
    symbol: str,
    at: str = Query("latest"),
    user: AuthUser = Depends(get_current_user),
) -> list[ChainRow]:
    at_time: datetime | None
    if at == "latest":
        at_time = None
    else:
        try:
            at_time = datetime.fromisoformat(at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="at must be 'latest' or an ISO-8601 timestamp",
            ) from exc

    async with user_connection(user) as conn:
        inst = await fetch_instrument(conn, symbol)
        if inst is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown symbol")
        _, rows = await fetch_chain_at(conn, inst["id"], at_time)

    return [ChainRow.model_validate(r) for r in rows]
