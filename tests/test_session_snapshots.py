"""Tests for _ref/session_snap.py parity."""
from __future__ import annotations

from datetime import date, datetime, time as dtime
from zoneinfo import ZoneInfo

from core.session_snapshots import (
    MIDDAY_END,
    MIDDAY_START,
    build_phase_snapshot,
    count_populated_phases,
    phase_status,
    pick_metrics_in_window,
)

IST = ZoneInfo("Asia/Kolkata")


def test_pick_last_row_in_window() -> None:
    rows = [
        {"time": datetime(2026, 6, 12, 12, 30)},
        {"time": datetime(2026, 6, 12, 12, 40)},
        {"time": datetime(2026, 6, 12, 12, 50)},
    ]
    picked = pick_metrics_in_window(rows, MIDDAY_START, MIDDAY_END)
    assert picked is not None
    assert picked["time"] == datetime(2026, 6, 12, 12, 40)


def test_build_phase_snapshot_simple_pcr() -> None:
    metrics_row = {
        "time": datetime(2026, 6, 12, 9, 21, 30),
        "underlying": 24500.0,
        "total_ce_oi": 1000,
        "total_pe_oi": 1100,
        "total_ce_volume": 50,
        "total_pe_volume": 60,
    }
    chain_rows = [
        {"strike": 24500.0, "ce_oi": 500, "pe_oi": 400},
        {"strike": 24550.0, "ce_oi": 300, "pe_oi": 350},
        {"strike": 24600.0, "ce_oi": 200, "pe_oi": 250},
    ]
    snap = build_phase_snapshot(metrics_row, chain_rows)
    assert snap.pcr == "1.10"
    assert snap.top1ce_strike == "24500"
    assert snap.overall_ce_oi == "1000"


def test_morning_window_boundaries() -> None:
    rows = [
        {"time": datetime(2026, 6, 12, 9, 20, 59)},
        {"time": datetime(2026, 6, 12, 9, 21, 0)},
        {"time": datetime(2026, 6, 12, 9, 21, 59)},
        {"time": datetime(2026, 6, 12, 9, 22, 0)},
    ]
    picked = pick_metrics_in_window(rows, dtime(9, 21), dtime(9, 22))
    assert picked is not None
    assert picked["time"] == datetime(2026, 6, 12, 9, 21, 59)


def test_phase_status_populated() -> None:
    row = {"time": datetime(2026, 6, 12, 12, 35)}
    now = datetime(2026, 6, 12, 14, 0, tzinfo=IST)
    assert (
        phase_status(row, MIDDAY_START, date(2026, 6, 12), now=now)
        == "populated"
    )


def test_phase_status_pending_before_window() -> None:
    now = datetime(2026, 6, 12, 10, 0, tzinfo=IST)
    assert (
        phase_status(None, MIDDAY_START, date(2026, 6, 12), now=now)
        == "pending"
    )


def test_phase_status_missed_after_window() -> None:
    now = datetime(2026, 6, 12, 16, 0, tzinfo=IST)
    assert (
        phase_status(None, MIDDAY_START, date(2026, 6, 12), now=now)
        == "missed"
    )


def test_phase_status_missed_historical_day() -> None:
    now = datetime(2026, 6, 12, 16, 0, tzinfo=IST)
    assert (
        phase_status(None, MIDDAY_START, date(2026, 6, 8), now=now)
        == "missed"
    )


def test_count_populated_phases() -> None:
    rows = [
        {"time": datetime(2026, 6, 11, 12, 35)},
        {"time": datetime(2026, 6, 11, 15, 10)},
    ]
    assert count_populated_phases(rows) == 2
