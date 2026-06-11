"""Async read-only Postgres access with Supabase RLS session context."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from apps.api.auth import AuthUser
from apps.api.config import Settings

_pool: AsyncConnectionPool | None = None

# Whitelist for metrics field projection (matches metrics table).
METRICS_COLUMNS = frozenset({
    "time", "instrument_id", "expiry", "dte", "underlying",
    "pcr_oi", "pcr_volume", "ce_cog", "pe_cog", "cog_shift",
    "atm_strike", "atm_iv", "iv_skew", "india_vix",
    "atm_straddle", "expected_move", "max_pain",
    "total_ce_oi", "total_pe_oi", "net_ce_oi_change", "net_pe_oi_change",
    "total_ce_volume", "total_pe_volume", "buy_sell_imbalance", "buildup",
    "immediate_support", "major_support", "immediate_resistance", "major_resistance",
    "sentiment_score", "sentiment_label", "drivers",
})


async def init_pool(settings: Settings) -> None:
    global _pool
    _pool = AsyncConnectionPool(
        conninfo=settings.database_url,
        kwargs={"row_factory": dict_row},
        open=False,
        min_size=1,
        max_size=10,
    )
    await _pool.open()


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialized")
    return _pool


async def check_db() -> bool:
    async with get_pool().connection() as conn:
        row = await conn.execute("select 1 as ok")
        result = await row.fetchone()
        return result is not None and result["ok"] == 1


async def set_rls_context(conn: AsyncConnection, user: AuthUser) -> None:
    claims = json.dumps({"sub": str(user.id), "role": "authenticated"})
    await conn.execute("select set_config('request.jwt.claims', %s, true)", (claims,))
    await conn.execute("set local role authenticated")


@asynccontextmanager
async def user_connection(user: AuthUser) -> AsyncIterator[AsyncConnection]:
    async with get_pool().connection() as conn:
        await set_rls_context(conn, user)
        yield conn


async def fetch_instruments(conn: AsyncConnection) -> list[dict[str, Any]]:
    cur = await conn.execute(
        """
        select id, symbol, name, type::text as type, segment, lot_size, tick_size, active
        from instruments
        where active = true
        order by symbol
        """
    )
    return list(await cur.fetchall())


async def fetch_instrument(conn: AsyncConnection, symbol: str) -> dict[str, Any] | None:
    cur = await conn.execute(
        """
        select id, symbol, name, type::text as type, segment, lot_size, tick_size, active
        from instruments
        where symbol = %s and active = true
        """,
        (symbol.upper(),),
    )
    return await cur.fetchone()


async def fetch_latest_metrics(conn: AsyncConnection, instrument_id: int) -> dict[str, Any] | None:
    cur = await conn.execute(
        """
        select *
        from metrics
        where instrument_id = %s
        order by time desc
        limit 1
        """,
        (instrument_id,),
    )
    return await cur.fetchone()


async def fetch_top_oi_strikes(
    conn: AsyncConnection,
    instrument_id: int,
    snap_time: datetime,
    *,
    limit: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cur = await conn.execute(
        """
        select strike, ce_oi, pe_oi
        from option_snapshots
        where instrument_id = %s and time = %s
        """,
        (instrument_id, snap_time),
    )
    rows = await cur.fetchall()
    ce = sorted(
        [{"strike": float(r["strike"]), "oi": int(r["ce_oi"] or 0)} for r in rows],
        key=lambda x: x["oi"],
        reverse=True,
    )[:limit]
    pe = sorted(
        [{"strike": float(r["strike"]), "oi": int(r["pe_oi"] or 0)} for r in rows],
        key=lambda x: x["oi"],
        reverse=True,
    )[:limit]
    return ce, pe


async def fetch_metrics_series(
    conn: AsyncConnection,
    instrument_id: int,
    *,
    from_ts: datetime,
    to_ts: datetime,
    fields: Sequence[str] | None,
    limit: int,
) -> list[dict[str, Any]]:
    cols = _resolve_metric_columns(fields)
    col_sql = ", ".join(cols)
    cur = await conn.execute(
        f"""
        select {col_sql}
        from metrics
        where instrument_id = %s and time >= %s and time <= %s
        order by time asc
        limit %s
        """,
        (instrument_id, from_ts, to_ts, limit),
    )
    return list(await cur.fetchall())


def _resolve_metric_columns(fields: Sequence[str] | None) -> list[str]:
    if not fields:
        return sorted(METRICS_COLUMNS)
    unknown = set(fields) - METRICS_COLUMNS
    if unknown:
        raise ValueError(f"Unknown metrics fields: {', '.join(sorted(unknown))}")
    # time + instrument_id always required for series identity
    chosen = set(fields) | {"time", "instrument_id"}
    return sorted(chosen)


async def fetch_chain_at(
    conn: AsyncConnection,
    instrument_id: int,
    at_time: datetime | None,
) -> tuple[datetime | None, list[dict[str, Any]]]:
    if at_time is None:
        cur = await conn.execute(
            "select max(time) as t from option_snapshots where instrument_id = %s",
            (instrument_id,),
        )
        row = await cur.fetchone()
        if not row or row["t"] is None:
            return None, []
        at_time = row["t"]

    cur = await conn.execute(
        """
        select time, instrument_id, expiry, strike, underlying,
               ce_oi, ce_oi_change, ce_iv, ce_ltp, ce_volume,
               pe_oi, pe_oi_change, pe_iv, pe_ltp, pe_volume, source
        from option_snapshots
        where instrument_id = %s and time = %s
        order by strike asc
        """,
        (instrument_id, at_time),
    )
    rows = list(await cur.fetchall())
    return at_time, rows


async def fetch_insights(
    conn: AsyncConnection,
    instrument_id: int,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    cur = await conn.execute(
        """
        select id, time, instrument_id, expiry, title, narrative,
               sentiment_label, confidence, cited_metrics, model, user_id
        from insights
        where instrument_id = %s
        order by time desc
        limit %s
        """,
        (instrument_id, limit),
    )
    return list(await cur.fetchall())


async def fetch_watchlist(conn: AsyncConnection, user_id: UUID) -> list[dict[str, Any]]:
    cur = await conn.execute(
        """
        select w.id, w.instrument_id, i.symbol, i.name, w.created_at
        from watchlists w
        join instruments i on i.id = w.instrument_id
        where w.user_id = %s
        order by w.created_at desc
        """,
        (user_id,),
    )
    return list(await cur.fetchall())


async def add_watchlist(conn: AsyncConnection, user_id: UUID, instrument_id: int) -> None:
    await conn.execute(
        """
        insert into watchlists (user_id, instrument_id)
        values (%s, %s)
        on conflict (user_id, instrument_id) do nothing
        """,
        (user_id, instrument_id),
    )


async def remove_watchlist(conn: AsyncConnection, user_id: UUID, instrument_id: int) -> bool:
    cur = await conn.execute(
        "delete from watchlists where user_id = %s and instrument_id = %s",
        (user_id, instrument_id),
    )
    return (cur.rowcount or 0) > 0


async def resolve_symbol_id(conn: AsyncConnection, symbol: str) -> int | None:
    cur = await conn.execute(
        "select id from instruments where symbol = %s and active = true",
        (symbol.upper(),),
    )
    row = await cur.fetchone()
    return int(row["id"]) if row else None


def default_metrics_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Default range: last calendar day in UTC (trading-day approximation for MVP)."""
    now = now or datetime.now(tz=UTC)
    start = now - timedelta(days=1)
    return start, now


def validate_metrics_window(
    from_ts: datetime | None,
    to_ts: datetime | None,
    *,
    max_days: int,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    now = now or datetime.now(tz=UTC)
    if from_ts is None and to_ts is None:
        return default_metrics_window(now)
    if from_ts is None or to_ts is None:
        raise ValueError("Both from and to are required when either is set")
    if from_ts > to_ts:
        raise ValueError("from must be before to")
    if (to_ts - from_ts).days > max_days:
        raise ValueError(f"Range exceeds maximum of {max_days} days")
    return from_ts, to_ts
