"""Postgres writer for snapshots + metrics (Supabase-ready, psycopg 3).

Connection comes from the DATABASE_URL env var (Supabase → Project Settings →
Database → Connection string). Writes are idempotent: re-running the backfill
will not duplicate rows.

    export DATABASE_URL='postgresql://postgres:<pwd>@db.<ref>.supabase.co:5432/postgres'
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date

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


def load_prev_snapshot(conn: psycopg.Connection, instrument_id: int) -> Snapshot | None:
    """Reconstruct the most recent stored snapshot for an instrument."""
    with conn.cursor() as cur:
        cur.execute(
            "select max(time) from option_snapshots where instrument_id = %s",
            (instrument_id,),
        )
        row = cur.fetchone()
        if not row or row[0] is None:
            return None
        prev_time = row[0]
        cur.execute(
            """
            select time, expiry, strike, underlying,
                   ce_oi, ce_oi_change, ce_iv, ce_ltp, ce_volume,
                   ce_change, ce_pchange, ce_buy_qty, ce_sell_qty,
                   pe_oi, pe_oi_change, pe_iv, pe_ltp, pe_volume,
                   pe_change, pe_pchange, pe_buy_qty, pe_sell_qty,
                   source
            from option_snapshots
            where instrument_id = %s and time = %s
            order by strike
            """,
            (instrument_id, prev_time),
        )
        db_rows = cur.fetchall()

    if not db_rows:
        return None

    strike_rows: list[StrikeRow] = []
    underlying: float | None = None
    expiry: date | None = None
    ts = db_rows[0][0]

    for r in db_rows:
        (
            time_val, exp, strike, und,
            ce_oi, ce_oi_change, ce_iv, ce_ltp, ce_volume,
            ce_change, ce_pchange, ce_buy_qty, ce_sell_qty,
            pe_oi, pe_oi_change, pe_iv, pe_ltp, pe_volume,
            pe_change, pe_pchange, pe_buy_qty, pe_sell_qty,
            source,
        ) = r
        ts = time_val
        if expiry is None and exp is not None:
            expiry = exp
        if underlying is None and und is not None:
            underlying = float(und)
        strike_rows.append(
            StrikeRow(
                time=time_val,
                expiry=exp,
                strike=float(strike),
                underlying=float(und) if und is not None else None,
                ce_oi=ce_oi,
                ce_oi_change=ce_oi_change,
                ce_iv=float(ce_iv) if ce_iv is not None else None,
                ce_ltp=float(ce_ltp) if ce_ltp is not None else None,
                ce_volume=ce_volume,
                ce_change=float(ce_change) if ce_change is not None else None,
                ce_pchange=float(ce_pchange) if ce_pchange is not None else None,
                ce_buy_qty=ce_buy_qty,
                ce_sell_qty=ce_sell_qty,
                pe_oi=pe_oi,
                pe_oi_change=pe_oi_change,
                pe_iv=float(pe_iv) if pe_iv is not None else None,
                pe_ltp=float(pe_ltp) if pe_ltp is not None else None,
                pe_volume=pe_volume,
                pe_change=float(pe_change) if pe_change is not None else None,
                pe_pchange=float(pe_pchange) if pe_pchange is not None else None,
                pe_buy_qty=pe_buy_qty,
                pe_sell_qty=pe_sell_qty,
                source=source or "nse",
            )
        )

    return Snapshot(time=ts, underlying=underlying, expiry=expiry, rows=strike_rows)
