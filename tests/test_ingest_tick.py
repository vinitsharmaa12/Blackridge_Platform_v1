"""Tests for worker ingest tick orchestration."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.enrich import compute_metrics
from core.normalize import Snapshot
from worker.config import WorkerSettings
from worker.ingest import COUNTERS, run_all, run_tick

NIFTY_DATA = Path(__file__).resolve().parent.parent / "nifty_data"
FIXTURE = json.loads((NIFTY_DATA / "nifty_20260608_103626.json").read_text())
FIXTURE_NEXT = json.loads((NIFTY_DATA / "nifty_20260608_103751.json").read_text())


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


def test_second_tick_uses_prev_for_cog_shift(settings: WorkerSettings) -> None:
    """PRD 001: prev from DB → cog_shift/buildup non-null on 2nd+ tick."""
    conn = MagicMock()
    stored: list[Snapshot] = []
    metric_calls: list[tuple[bool, float | None, str | None]] = []

    def _load_prev(_conn: object, _instrument_id: int) -> Snapshot | None:
        return stored[-1] if stored else None

    def _write(_conn: object, _instrument_id: int, snap: Snapshot, metrics_row: object) -> int:
        stored.append(snap)
        return len(snap.rows)

    def _track_metrics(
        snap: Snapshot,
        prev: Snapshot | None = None,
        india_vix: float | None = None,
    ):
        row = compute_metrics(snap, prev=prev, india_vix=india_vix)
        metric_calls.append((prev is not None, row.cog_shift, row.buildup))
        return row

    with patch("worker.ingest.db.get_instrument_id", return_value=1), patch(
        "worker.ingest.db.load_prev_snapshot", side_effect=_load_prev
    ), patch("worker.ingest.db.write", side_effect=_write), patch(
        "worker.ingest.compute_metrics", side_effect=_track_metrics
    ):
        first = run_tick(conn, "NIFTY", settings, fetch_fn=lambda _s: FIXTURE)
        second = run_tick(conn, "NIFTY", settings, fetch_fn=lambda _s: FIXTURE_NEXT)

    assert first.success is True
    assert second.success is True
    assert len(metric_calls) == 2
    assert metric_calls[0][0] is False
    assert metric_calls[1][0] is True
    assert metric_calls[1][1] is not None
    assert metric_calls[1][2] is not None


def test_run_all_loops_configured_instruments(settings: WorkerSettings) -> None:
    settings = WorkerSettings(
        DATABASE_URL="postgresql://test:test@localhost/test",
        INSTRUMENTS="NIFTY,BANKNIFTY",
        ARCHIVE_RAW=False,
    )
    seen: list[str] = []

    def _fake_tick(_conn: object, symbol: str, _settings: WorkerSettings, **kwargs: object):
        seen.append(symbol)
        return MagicMock(success=True)

    with patch("worker.ingest.db.connect") as mock_connect, patch(
        "worker.ingest.run_tick", side_effect=_fake_tick
    ):
        mock_connect.return_value.__enter__ = MagicMock(return_value=object())
        mock_connect.return_value.__exit__ = MagicMock(return_value=None)
        run_all(settings)

    assert seen == ["NIFTY", "BANKNIFTY"]
