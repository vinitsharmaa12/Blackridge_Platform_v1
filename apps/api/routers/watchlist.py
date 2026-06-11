"""Watchlist routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from apps.api.auth import AuthUser, get_current_user
from apps.api.db import (
    add_watchlist,
    fetch_instrument,
    fetch_watchlist,
    remove_watchlist,
    user_connection,
)
from apps.api.models import WatchlistEntry

router = APIRouter(prefix="/me/watchlist", tags=["watchlist"])


class WatchlistAddRequest(BaseModel):
    symbol: str


@router.get("", response_model=list[WatchlistEntry])
async def get_watchlist(user: AuthUser = Depends(get_current_user)) -> list[WatchlistEntry]:
    async with user_connection(user) as conn:
        rows = await fetch_watchlist(conn, user.id)
    return [WatchlistEntry.model_validate(r) for r in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_to_watchlist(
    body: WatchlistAddRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, str]:
    async with user_connection(user) as conn:
        inst = await fetch_instrument(conn, body.symbol)
        if inst is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown symbol")
        await add_watchlist(conn, user.id, inst["id"])
    return {"symbol": inst["symbol"]}


@router.delete("/{symbol}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def remove_from_watchlist(
    symbol: str,
    user: AuthUser = Depends(get_current_user),
) -> Response:
    async with user_connection(user) as conn:
        inst = await fetch_instrument(conn, symbol)
        if inst is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown symbol")
        removed = await remove_watchlist(conn, user.id, inst["id"])
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not on watchlist")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
