"""Tests for worker ingest tick orchestration."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from worker.config import WorkerSettings
from worker.ingest import COUNTERS, run_tick

NIFTY_DATA = Path(__file__).resolve().parent.parent / "nifty_data"
FIXTURE = json.loads((NIFTY_DATA / "nifty_20260608_103626.json").read_text())


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> WorkerSettings:
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")
    return WorkerSettings(
        DATABASE_URL="postgresql://test:test@localhost/test",
        ARCHIVE_RAW=False,
        FETCH_INDIA_VIX=False,
    )


@pytest.fixture(autouse=True)
def _reset_counters() -> None:
    COUNTERS.success = 0
    COUNTERS.failure = 0
    COUNTERS.skipped = 0


def test_run_tick_happy_path(settings: WorkerSettings) -> None:
    conn = MagicMock()
    prev_snap = MagicMock()

    with patch("worker.ingest.db.get_instrument_id", return_value=1), patch(
        "worker.ingest.db.load_prev_snapshot", return_value=prev_snap
    ), patch("worker.ingest.db.write", return_value=210) as mock_write, patch(
        "worker.ingest.compute_metrics"
    ) as mock_metrics:
        mock_metrics.return_value.pcr_oi = 1.2
        mock_metrics.return_value.sentiment_label = "bullish"
        result = run_tick(
            conn,
            "NIFTY",
            settings,
            fetch_fn=lambda _s: FIXTURE,
        )

    assert result.success is True
    assert result.rows_written == 210
    assert result.pcr_oi == 1.2
    mock_write.assert_called_once()
    mock_metrics.assert_called_once()
    assert COUNTERS.success == 1


def test_run_tick_skips_empty(settings: WorkerSettings) -> None:
    conn = MagicMock()
    result = run_tick(conn, "NIFTY", settings, fetch_fn=lambda _s: {})
    assert result.skipped is True
    assert result.success is False
    assert COUNTERS.skipped == 1


def test_run_tick_fail_soft_on_error(settings: WorkerSettings) -> None:
    conn = MagicMock()

    def _boom(_s: str) -> dict:
        raise RuntimeError("network down")

    result = run_tick(conn, "NIFTY", settings, fetch_fn=_boom)
    assert result.success is False
    assert "network down" in (result.error or "")
    assert COUNTERS.failure == 1
