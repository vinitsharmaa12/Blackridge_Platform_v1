"""Scheduler tick guard — idle outside market hours."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from worker.config import WorkerSettings
from worker.scheduler import _tick, is_market_open

IST = ZoneInfo("Asia/Kolkata")


def test_market_closed_after_close() -> None:
    now = datetime(2026, 6, 9, 16, 0, tzinfo=IST)
    assert is_market_open(now) is False


def test_tick_skips_run_all_outside_market_hours() -> None:
    settings = WorkerSettings(
        DATABASE_URL="postgresql://test:test@localhost/test",
        INSTRUMENTS="NIFTY",
    )
    closed = datetime(2026, 6, 9, 8, 0, tzinfo=IST)

    with patch("worker.scheduler.datetime") as mock_dt, patch(
        "worker.scheduler.run_all"
    ) as mock_run_all:
        mock_dt.now.return_value = closed
        _tick(settings)

    mock_run_all.assert_not_called()


def test_tick_calls_run_all_during_market_hours() -> None:
    settings = WorkerSettings(
        DATABASE_URL="postgresql://test:test@localhost/test",
        INSTRUMENTS="NIFTY",
    )
    open_time = datetime(2026, 6, 9, 12, 0, tzinfo=IST)

    with patch("worker.scheduler.datetime") as mock_dt, patch(
        "worker.scheduler.run_all",
        return_value=[MagicMock()],
    ) as mock_run_all:
        mock_dt.now.return_value = open_time
        _tick(settings)

    mock_run_all.assert_called_once_with(settings)
