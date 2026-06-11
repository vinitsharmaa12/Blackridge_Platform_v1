"""Insights DB tool tests."""
from __future__ import annotations

from datetime import datetime

import pytest

from insights.tools import compare_sessions, get_chain, get_latest_metrics, get_metric_series


class _FakeCursor:
    def __init__(self, fetchone_results: list, fetchall_results: list | None = None) -> None:
        self._fetchone = list(fetchone_results)
        self._fetchall = fetchall_results or []
        self._fetchone_idx = 0
        self.row_factory = None
        self.executed: list[tuple[str, tuple]] = []

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, sql: str, params: tuple) -> None:
        self.executed.append((sql, params))

    def fetchone(self):
        if self._fetchone_idx < len(self._fetchone):
            result = self._fetchone[self._fetchone_idx]
            self._fetchone_idx += 1
            return result
        return None

    def fetchall(self):
        return self._fetchall


class _FakeConn:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor
        self.instrument_id = 1

    def cursor(self, *, row_factory=None) -> _FakeCursor:
        self._cursor.row_factory = row_factory
        return self._cursor


def test_get_latest_metrics_none(monkeypatch: pytest.MonkeyPatch) -> None:
    cur = _FakeCursor(fetchone_results=[None])
    conn = _FakeConn(cur)
    monkeypatch.setattr("insights.tools.get_instrument_id", lambda _c, _s: 1)
    result = get_latest_metrics(conn, "NIFTY")  # type: ignore[arg-type]
    assert result["metrics"] is None


def test_get_metric_series_rejects_unknown_field(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _FakeConn(_FakeCursor(fetchone_results=[]))
    monkeypatch.setattr("insights.tools.get_instrument_id", lambda _c, _s: 1)
    with pytest.raises(ValueError, match="Unknown metrics field"):
        get_metric_series(
            conn,  # type: ignore[arg-type]
            "NIFTY",
            "not_a_field",
            "2026-06-08T09:00:00+00:00",
            "2026-06-08T15:00:00+00:00",
        )


def test_get_chain_latest_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    cur = _FakeCursor(fetchone_results=[{"t": None}])
    conn = _FakeConn(cur)
    monkeypatch.setattr("insights.tools.get_instrument_id", lambda _c, _s: 1)
    result = get_chain(conn, "NIFTY")  # type: ignore[arg-type]
    assert result["strikes"] == [] or result["strike_count"] == 0


def test_compare_sessions_builds_deltas(monkeypatch: pytest.MonkeyPatch) -> None:
    ts = datetime(2026, 6, 8, 10, 0)
    row = {
        "time": ts,
        "underlying": 25000.0,
        "pcr_oi": 1.1,
        "sentiment_score": 50,
        "cog_shift": 5.0,
        "max_pain": 24900.0,
    }

    class _MultiCursor(_FakeCursor):
        def fetchone(self):
            return row

    conn = _FakeConn(_MultiCursor(fetchone_results=[]))
    monkeypatch.setattr("insights.tools.get_instrument_id", lambda _c, _s: 1)
    result = compare_sessions(conn, "NIFTY", "2026-06-08", "2026-06-09")  # type: ignore[arg-type]
    assert result["symbol"] == "NIFTY"
    assert "deltas" in result
