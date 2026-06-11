"""WebSocket live metrics fan-out."""
from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from psycopg import AsyncConnection
from psycopg.rows import dict_row

from apps.api.auth import verify_ws_token
from apps.api.config import Settings, get_settings
from apps.api.db import fetch_latest_metrics, get_pool, resolve_symbol_id, set_rls_context

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


class ConnectionManager:
    def __init__(self) -> None:
        self._subs: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, symbol: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._subs[symbol.upper()].add(ws)

    async def disconnect(self, symbol: str, ws: WebSocket) -> None:
        async with self._lock:
            peers = self._subs.get(symbol.upper())
            if peers and ws in peers:
                peers.remove(ws)
            if peers is not None and not peers:
                del self._subs[symbol.upper()]

    async def broadcast(self, symbol: str, payload: dict[str, Any]) -> None:
        async with self._lock:
            peers = list(self._subs.get(symbol.upper(), ()))
        dead: list[WebSocket] = []
        for ws in peers:
            try:
                await ws.send_json(payload)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            await self.disconnect(symbol, ws)


manager = ConnectionManager()
_listener_task: asyncio.Task[None] | None = None
_id_to_symbol: dict[int, str] = {}


async def _refresh_symbol_map(conn: AsyncConnection) -> None:
    cur = await conn.execute("select id, symbol from instruments where active = true")
    rows = await cur.fetchall()
    _id_to_symbol.clear()
    for row in rows:
        _id_to_symbol[int(row["id"])] = row["symbol"]


async def _listen_loop(settings: Settings) -> None:
    """LISTEN on metrics_new; fall back to polling if LISTEN fails."""
    while True:
        try:
            async with get_pool().connection() as conn:
                await conn.set_autocommit(True)
                await conn.execute("listen metrics_new")
                async for notify in conn.notifies():
                    payload = json.loads(notify.payload)
                    instrument_id = int(payload["instrument_id"])
                    symbol = _id_to_symbol.get(instrument_id)
                    if symbol:
                        await manager.broadcast(symbol, payload)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("ws_listen_failed; falling back to poll")
            await _poll_loop(settings)
            return


async def _poll_loop(settings: Settings) -> None:
    last_seen: dict[str, datetime | None] = {}
    while True:
        try:
            async with get_pool().connection() as conn:
                await _refresh_symbol_map(conn)
                for symbol in list(manager._subs.keys()):  # noqa: SLF001
                    inst_id = next(
                        (i for i, s in _id_to_symbol.items() if s == symbol),
                        None,
                    )
                    if inst_id is None:
                        continue
                    row = await fetch_latest_metrics(conn, inst_id)
                    if not row:
                        continue
                    ts = row["time"]
                    if last_seen.get(symbol) != ts:
                        last_seen[symbol] = ts
                        await manager.broadcast(
                            symbol,
                            {
                                "instrument_id": inst_id,
                                "time": ts.isoformat(),
                                "underlying": row.get("underlying"),
                                "sentiment_label": row.get("sentiment_label"),
                            },
                        )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("ws_poll_error")
        await asyncio.sleep(settings.ws_poll_seconds)


async def start_ws_background(settings: Settings) -> None:
    global _listener_task
    async with get_pool().connection() as conn:
        await _refresh_symbol_map(conn)
    _listener_task = asyncio.create_task(_listen_loop(settings))


async def stop_ws_background() -> None:
    global _listener_task
    if _listener_task is not None:
        _listener_task.cancel()
        try:
            await _listener_task
        except asyncio.CancelledError:
            pass
        _listener_task = None


@router.websocket("/ws/instruments/{symbol}")
async def metrics_ws(
    websocket: WebSocket,
    symbol: str,
    token: str = Query(...),
    settings: Settings = Depends(get_settings),
) -> None:
    user = await verify_ws_token(token, settings)
    sym = symbol.upper()
    inst_id = None
    async with get_pool().connection() as conn:
        conn.row_factory = dict_row
        await set_rls_context(conn, user)
        inst_id = await resolve_symbol_id(conn, sym)
    if inst_id is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(sym, websocket)
    try:
        async with get_pool().connection() as conn:
            row = await fetch_latest_metrics(conn, inst_id)
            if row:
                await websocket.send_json(
                    {
                        "instrument_id": inst_id,
                        "time": row["time"].isoformat(),
                        "underlying": row.get("underlying"),
                        "sentiment_label": row.get("sentiment_label"),
                        "initial": True,
                    }
                )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(sym, websocket)
