"""Tests for market-hours guard."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from worker.scheduler import is_market_open, is_morning_burst_window

IST = ZoneInfo("Asia/Kolkata")


def test_market_open_weekday_midday() -> None:
    now = datetime(2026, 6, 9, 12, 0, tzinfo=IST)  # Tuesday
    assert is_market_open(now) is True


def test_market_closed_weekend() -> None:
    now = datetime(2026, 6, 13, 12, 0, tzinfo=IST)  # Saturday
    assert is_market_open(now) is False


def test_market_closed_before_open() -> None:
    now = datetime(2026, 6, 9, 8, 0, tzinfo=IST)
    assert is_market_open(now) is False


def test_morning_burst_inside_window() -> None:
    now = datetime(2026, 6, 9, 9, 21, 30, tzinfo=IST)
    assert is_morning_burst_window(now) is True


def test_morning_burst_outside_window() -> None:
    now = datetime(2026, 6, 9, 9, 26, tzinfo=IST)
    assert is_morning_burst_window(now) is False


def test_morning_burst_weekend() -> None:
    now = datetime(2026, 6, 13, 9, 22, tzinfo=IST)
    assert is_morning_burst_window(now) is False
