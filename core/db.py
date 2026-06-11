"""Postgres writer for snapshots + metrics (Supabase-ready, psycopg 3).

Connection comes from the DATABASE_URL env var (Supabase → Project Settings →
Database → Connection string). Writes are idempotent: re-running the backfill
will not duplicate rows.

    export DATABASE_URL='postgresql://postgres:<pwd>@db.<ref>.supabase.co:5432/postgres'
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator, Optional

import psycopg
from psycopg.types.json import Json

from core.enrich import MetricsRow
from core.normalize import Snapshot, StrikeRow

# Column order for each table — single source of truth for the INSERTs.
_SNAPSHOT_COLS = [
    "time", "instrument_id", "expiry", "strike", "underlying",
    "ce_oi", "ce_oi_change", "ce_iv", "ce_ltp", "ce_volume",
    "ce_change", "ce_pchange", "ce_buy_qty", "ce_sell_qty",
    "pe_oi", "pe_oi_change", "pe_iv", "pe_ltp", "pe_volume",
    "pe_change", "pe_pchange", "pe_buy_qty", "pe_sell_qty",
    "source",
]
_METRICS_COLS = [
    "time", "instrument_id", "expiry", "dte", "underlying",
    "pcr_oi", "pcr_volume", "ce_cog", "pe_cog", "cog_shift",
    "atm_strike", "atm_iv", "iv_skew", "india_vix",
    "atm_straddle", "expected_move", "max_pain",
    "total_ce_oi", "total_pe_oi", "net_ce_oi_change", "net_pe_oi_change",
    "total_ce_volume", "total_pe_volume", "buy_sell_imbalance", "buildup",
    "immediate_support", "major_support", "immediate_resistance", "major_resistance",
    "sentiment_score", "sentiment_label", "drivers",
]


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env and fill in your "
            "Supabase connection string, or `export DATABASE_URL=...`."
        )
    return url


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(database_url())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_instrument_id(conn: psycopg.Connection, symbol: str) -> int:
    with conn.cursor() as cur:
        cur.execute("select id from instruments where symbol = %s", (symbol,))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute(
            "insert into instruments (symbol, name, type) values (%s, %s, 'index') "
            "returning id",
            (symbol, symbol),
        )
        return cur.fetchone()[0]


def _snapshot_params(r: StrikeRow, instrument_id: int) -> tuple:
    return (
        r.time, instrument_id, r.expiry, r.strike, r.underlying,
        r.ce_oi, r.ce_oi_change, r.ce_iv, r.ce_ltp, r.ce_volume,
        r.ce_change, r.ce_pchange, r.ce_buy_qty, r.ce_sell_qty,
        r.pe_oi, r.pe_oi_change, r.pe_iv, r.pe_ltp, r.pe_volume,
        r.pe_change, r.pe_pchange, r.pe_buy_qty, r.pe_sell_qty,
        r.source,
    )


def write_snapshot(conn: psycopg.Connection, instrument_id: int, snap: Snapshot) -> int:
    """Insert per-strike rows. ON CONFLICT DO NOTHING → safe to re-run."""
    placeholders = ", ".join(["%s"] * len(_SNAPSHOT_COLS))
    sql = (
        f"insert into option_snapshots ({', '.join(_SNAPSHOT_COLS)}) "
        f"values ({placeholders}) "
        f"on conflict (instrument_id, expiry, strike, time) do nothing"
    )
    params = [_snapshot_params(r, instrument_id) for r in snap.rows]
    with conn.cursor() as cur:
        cur.executemany(sql, params)
    return len(params)


def write_metrics(conn: psycopg.Connection, instrument_id: int, m: MetricsRow) -> None:
    """Upsert the instrument-level metrics row for this timestamp."""
    d = m.as_dict()
    d["instrument_id"] = instrument_id
    d["drivers"] = Json(d.get("drivers") or [])
    values = [d[c] for c in _METRICS_COLS]
    placeholders = ", ".join(["%s"] * len(_METRICS_COLS))
    updatable = [c for c in _METRICS_COLS if c not in ("time", "instrument_id")]
    set_clause = ", ".join(f"{c} = excluded.{c}" for c in updatable)
    sql = (
        f"insert into metrics ({', '.join(_METRICS_COLS)}) "
        f"values ({placeholders}) "
        f"on conflict (instrument_id, time) do update set {set_clause}"
    )
    with conn.cursor() as cur:
        cur.execute(sql, values)


def write(conn: psycopg.Connection, instrument_id: int,
          snap: Snapshot, metrics_row: MetricsRow) -> int:
    """Write one snapshot + its metrics row. Returns strike-row count."""
    n = write_snapshot(conn, instrument_id, snap)
    write_metrics(conn, instrument_id, metrics_row)
    return n
