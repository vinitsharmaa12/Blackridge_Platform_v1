"""Read-only DB-backed agent tools (reuse API query shapes)."""
from __future__ import annotations

import json
from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import psycopg

from core.db import get_instrument_id

IST = ZoneInfo("Asia/Kolkata")

METRICS_FIELDS = frozenset({
    "time", "instrument_id", "expiry", "dte", "underlying",
    "pcr_oi", "pcr_volume", "ce_cog", "pe_cog", "cog_shift",
    "atm_strike", "atm_iv", "iv_skew", "india_vix",
    "atm_straddle", "expected_move", "max_pain",
    "total_ce_oi", "total_pe_oi", "net_ce_oi_change", "net_pe_oi_change",
    "total_ce_volume", "total_pe_volume", "buy_sell_imbalance", "buildup",
    "immediate_support", "major_support", "immediate_resistance", "major_resistance",
    "sentiment_score", "sentiment_label", "drivers",
})


def _json_safe(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, datetime):
            out[key] = value.isoformat()
        elif isinstance(value, date):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


def get_latest_metrics(conn: psycopg.Connection, symbol: str) -> dict[str, Any]:
    instrument_id = get_instrument_id(conn, symbol.upper())
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(
            """
            select *
            from metrics
            where instrument_id = %s
            order by time desc
            limit 1
            """,
            (instrument_id,),
        )
        row = cur.fetchone()
    if row is None:
        return {"symbol": symbol.upper(), "metrics": None}
    return {"symbol": symbol.upper(), "metrics": _json_safe(dict(row))}


def get_metric_series(
    conn: psycopg.Connection,
    symbol: str,
    field: str,
    from_ts: str,
    to_ts: str,
    *,
    limit: int = 500,
) -> dict[str, Any]:
    if field not in METRICS_FIELDS:
        raise ValueError(f"Unknown metrics field: {field}")
    instrument_id = get_instrument_id(conn, symbol.upper())
    start = datetime.fromisoformat(from_ts.replace("Z", "+00:00"))
    end = datetime.fromisoformat(to_ts.replace("Z", "+00:00"))
    cols = sorted({field, "time", "instrument_id"})
    col_sql = ", ".join(cols)
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(
            f"""
            select {col_sql}
            from metrics
            where instrument_id = %s and time >= %s and time <= %s
            order by time asc
            limit %s
            """,
            (instrument_id, start, end, limit),
        )
        rows = [_json_safe(dict(r)) for r in cur.fetchall()]
    return {"symbol": symbol.upper(), "field": field, "series": rows}


def get_chain(
    conn: psycopg.Connection,
    symbol: str,
    at: str = "latest",
    *,
    top_oi_limit: int = 10,
) -> dict[str, Any]:
    instrument_id = get_instrument_id(conn, symbol.upper())
    at_time: datetime | None
    if at == "latest":
        at_time = None
    else:
        at_time = datetime.fromisoformat(at.replace("Z", "+00:00"))

    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        if at_time is None:
            cur.execute(
                "select max(time) as t from option_snapshots where instrument_id = %s",
                (instrument_id,),
            )
            row = cur.fetchone()
            if not row or row["t"] is None:
                return {
                    "symbol": symbol.upper(),
                    "time": None,
                    "strikes": [],
                    "top_ce_oi": [],
                    "top_pe_oi": [],
                }
            at_time = row["t"]

        cur.execute(
            """
            select strike, ce_oi, pe_oi, ce_iv, pe_iv, underlying
            from option_snapshots
            where instrument_id = %s and time = %s
            order by strike asc
            """,
            (instrument_id, at_time),
        )
        rows = [dict(r) for r in cur.fetchall()]

    ce = sorted(
        [{"strike": float(r["strike"]), "oi": int(r["ce_oi"] or 0)} for r in rows],
        key=lambda x: x["oi"],
        reverse=True,
    )[:top_oi_limit]
    pe = sorted(
        [{"strike": float(r["strike"]), "oi": int(r["pe_oi"] or 0)} for r in rows],
        key=lambda x: x["oi"],
        reverse=True,
    )[:top_oi_limit]
    return {
        "symbol": symbol.upper(),
        "time": at_time.isoformat() if at_time else None,
        "strike_count": len(rows),
        "top_ce_oi": ce,
        "top_pe_oi": pe,
    }


def compare_sessions(
    conn: psycopg.Connection,
    symbol: str,
    date_a: str,
    date_b: str,
) -> dict[str, Any]:
    instrument_id = get_instrument_id(conn, symbol.upper())
    day_a = date.fromisoformat(date_a)
    day_b = date.fromisoformat(date_b)

    def _session_close_row(day: date) -> dict[str, Any] | None:
        start = datetime.combine(day, time(9, 15), tzinfo=IST)
        end = datetime.combine(day, time(15, 35), tzinfo=IST)
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                """
                select *
                from metrics
                where instrument_id = %s and time >= %s and time <= %s
                order by time desc
                limit 1
                """,
                (instrument_id, start.astimezone(UTC), end.astimezone(UTC)),
            )
            row = cur.fetchone()
        return _json_safe(dict(row)) if row else None

    row_a = _session_close_row(day_a)
    row_b = _session_close_row(day_b)
    deltas: dict[str, Any] = {}
    if row_a and row_b:
        for key in ("underlying", "pcr_oi", "sentiment_score", "cog_shift", "max_pain"):
            a_val, b_val = row_a.get(key), row_b.get(key)
            if a_val is not None and b_val is not None:
                try:
                    deltas[key] = float(b_val) - float(a_val)
                except (TypeError, ValueError):
                    deltas[key] = None
    return {
        "symbol": symbol.upper(),
        "date_a": date_a,
        "date_b": date_b,
        "metrics_a": row_a,
        "metrics_b": row_b,
        "deltas": deltas,
    }


def dispatch_tool(
    conn: psycopg.Connection,
    name: str,
    arguments: dict[str, Any],
) -> str:
    """Execute a tool by name; returns JSON string for the LLM."""
    if name == "get_latest_metrics":
        result = get_latest_metrics(conn, str(arguments["symbol"]))
    elif name == "get_metric_series":
        result = get_metric_series(
            conn,
            str(arguments["symbol"]),
            str(arguments["field"]),
            str(arguments["from"]),
            str(arguments["to"]),
        )
    elif name == "get_chain":
        result = get_chain(conn, str(arguments["symbol"]), str(arguments.get("at", "latest")))
    elif name == "compare_sessions":
        result = compare_sessions(
            conn,
            str(arguments["symbol"]),
            str(arguments["date_a"]),
            str(arguments["date_b"]),
        )
    else:
        raise ValueError(f"Unknown tool: {name}")
    return json.dumps(result, default=str)
