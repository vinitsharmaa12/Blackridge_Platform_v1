"""Tests for market-hours guard."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from worker.scheduler import is_market_open

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
