"""Normalize a raw NSE option-chain JSON into per-strike snapshot rows.

Output shape matches `public.option_snapshots` (see 0001_init.sql). The DB writer
adds `instrument_id`; everything else is produced here. Pure functions, no I/O
beyond reading a file path.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

# NSE server timestamp, e.g. "08-Jun-2026 09:21:00"
_NSE_TS = "%d-%b-%Y %H:%M:%S"
# expiryDate on each leg, e.g. "09-06-2026"
_EXPIRY_FMT = "%d-%m-%Y"
# filename fallback: nifty_YYYYMMDD_HHMMSS.json
_FNAME_RE = re.compile(r"(\d{8})_(\d{6})")


def _num(v) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _int(v) -> int | None:
    n = _num(v)
    return int(round(n)) if n is not None else None


@dataclass
class StrikeRow:
    """One per-strike row, keyed to option_snapshots columns."""
    time: datetime
    expiry: date | None
    strike: float
    underlying: float | None
    ce_oi: int | None = None
    ce_oi_change: int | None = None
    ce_iv: float | None = None
    ce_ltp: float | None = None
    ce_volume: int | None = None
    ce_change: float | None = None
    ce_pchange: float | None = None
    ce_buy_qty: int | None = None
    ce_sell_qty: int | None = None
    pe_oi: int | None = None
    pe_oi_change: int | None = None
    pe_iv: float | None = None
    pe_ltp: float | None = None
    pe_volume: int | None = None
    pe_change: float | None = None
    pe_pchange: float | None = None
    pe_buy_qty: int | None = None
    pe_sell_qty: int | None = None
    source: str = "nse"


@dataclass
class Snapshot:
    """A full normalized snapshot for one instrument at one timestamp."""
    time: datetime
    underlying: float | None
    expiry: date | None
    rows: list[StrikeRow] = field(default_factory=list)

    @property
    def dte(self) -> int | None:
        if self.expiry is None:
            return None
        return (self.expiry - self.time.date()).days


def _parse_timestamp(records: dict, source_name: str) -> datetime:
    ts = records.get("timestamp")
    if ts:
        try:
            return datetime.strptime(ts, _NSE_TS)
        except ValueError:
            pass
    m = _FNAME_RE.search(source_name)
    if m:
        return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
    raise ValueError(f"Could not derive timestamp from {source_name!r}")


def _parse_expiry(leg: dict) -> date | None:
    ev = leg.get("expiryDate")
    if not ev:
        return None
    try:
        return datetime.strptime(ev, _EXPIRY_FMT).date()
    except ValueError:
        return None


def _leg_fields(prefix: str, leg: dict) -> dict:
    return {
        f"{prefix}_oi": _int(leg.get("openInterest")),
        f"{prefix}_oi_change": _int(leg.get("changeinOpenInterest")),
        f"{prefix}_iv": _num(leg.get("impliedVolatility")),
        f"{prefix}_ltp": _num(leg.get("lastPrice")),
        f"{prefix}_volume": _int(leg.get("totalTradedVolume")),
        f"{prefix}_change": _num(leg.get("change")),
        f"{prefix}_pchange": _num(leg.get("pChange", leg.get("PChange"))),
        f"{prefix}_buy_qty": _int(leg.get("totalBuyQuantity")),
        f"{prefix}_sell_qty": _int(leg.get("totalSellQuantity")),
    }


def normalize(raw: dict, source_name: str = "") -> Snapshot:
    """Convert a parsed NSE option-chain JSON dict into a `Snapshot`."""
    records = raw.get("records") if isinstance(raw, dict) else None
    if not isinstance(records, dict):
        raise ValueError("Unexpected JSON: missing 'records' object")

    data = records.get("data") or []
    ts = _parse_timestamp(records, source_name)
    top_underlying = _num(records.get("underlyingValue"))

    rows: list[StrikeRow] = []
    expiry: date | None = None
    for rec in data:
        ce = rec.get("CE") or {}
        pe = rec.get("PE") or {}
        strike = _num(ce.get("strikePrice") or pe.get("strikePrice") or rec.get("strikePrice"))
        if strike is None:
            continue
        underlying = (
            _num(ce.get("underlyingValue"))
            or _num(pe.get("underlyingValue"))
            or top_underlying
        )
        row_expiry = _parse_expiry(ce) or _parse_expiry(pe)
        if expiry is None:
            expiry = row_expiry
        rows.append(
            StrikeRow(
                time=ts,
                expiry=row_expiry or expiry,
                strike=strike,
                underlying=underlying,
                **_leg_fields("ce", ce),
                **_leg_fields("pe", pe),
            )
        )

    underlying = top_underlying
    if underlying is None and rows:
        underlying = next((r.underlying for r in rows if r.underlying is not None), None)

    return Snapshot(time=ts, underlying=underlying, expiry=expiry, rows=rows)


def normalize_file(path: str | Path) -> Snapshot:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return normalize(raw, source_name=path.name)
