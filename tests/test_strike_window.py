"""Tests for ATM ±10 top-OI window (_ref/Preprocessing.py parity)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from core.normalize import StrikeRow
from core.strike_window import (
    rows_in_window,
    top_oi_from_chain_dicts,
    top_oi_strike_numbers,
    top_oi_strikes,
)

_TS = datetime(2026, 6, 12, 10, 0)
_EXP = date(2026, 6, 12)


def _row(strike: float, ce_oi: int = 0, pe_oi: int = 0) -> StrikeRow:
    return StrikeRow(
        time=_TS,
        expiry=_EXP,
        strike=strike,
        underlying=24500.0,
        ce_oi=ce_oi,
        pe_oi=pe_oi,
    )


def test_window_limits_strikes_around_atm() -> None:
    rows = [_row(float(24000 + i * 50), ce_oi=100 + i) for i in range(21)]
    in_window = rows_in_window(rows, 24500.0, window=2)
    strikes = sorted(r.strike for r in in_window)
    assert strikes == [24400.0, 24450.0, 24500.0, 24550.0, 24600.0]


def test_top_oi_returns_highest_three_in_window() -> None:
    rows = [
        _row(24400.0, ce_oi=10),
        _row(24500.0, ce_oi=500),
        _row(24550.0, ce_oi=300),
        _row(24600.0, ce_oi=200),
        _row(25000.0, ce_oi=999),
    ]
    top = top_oi_strikes(rows, 24500.0, side="ce", n=3, window=2)
    assert top == [(24500.0, 500), (24550.0, 300), (24600.0, 200)]


def test_top_oi_from_chain_dicts_accepts_decimal_underlying() -> None:
    rows = [
        {"strike": Decimal("24500"), "ce_oi": 500, "pe_oi": 400},
        {"strike": Decimal("24550"), "ce_oi": 300, "pe_oi": 350},
    ]
    top = top_oi_from_chain_dicts(rows, Decimal("24500"), side="ce", n=2, window=2)
    assert top == [{"strike": 24500.0, "oi": 500}, {"strike": 24550.0, "oi": 300}]


def test_top_oi_strike_numbers_for_migration() -> None:
    rows = [
        _row(24500.0, ce_oi=100),
        _row(24550.0, ce_oi=50),
    ]
    assert top_oi_strike_numbers(rows, 24500.0, side="ce") == [24500.0, 24550.0]
