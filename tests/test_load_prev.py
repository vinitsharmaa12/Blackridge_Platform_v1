"""Tests for load_prev_snapshot reconstruction."""
from __future__ import annotations

from datetime import date, datetime

from core.db import load_prev_snapshot
from core.normalize import Snapshot


class _FakeCursor:
    def __init__(self, rows: list[tuple]) -> None:
        self._rows = rows
        self._step = 0

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, _sql: str, _params: tuple) -> None:
        self._step += 1

    def fetchone(self) -> tuple | None:
        if self._step == 1:
            return (datetime(2026, 6, 8, 10, 35, 9),)
        return None

    def fetchall(self) -> list[tuple]:
        if self._step == 2:
            return self._rows
        return []


class _FakeConn:
    def __init__(self, rows: list[tuple]) -> None:
        self._rows = rows

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self._rows)


def test_load_prev_snapshot_reconstructs() -> None:
    ts = datetime(2026, 6, 8, 10, 35, 9)
    exp = date(2026, 6, 9)
    row = (
        ts, exp, 23000.0, 23212.9,
        100, 10, 15.5, 120.0, 500,
        1.0, 0.5, 1000, 900,
        200, 20, 16.0, 130.0, 600,
        2.0, 1.0, 1100, 800,
        "nse",
    )
    snap = load_prev_snapshot(_FakeConn([row]), instrument_id=1)
    assert snap is not None
    assert isinstance(snap, Snapshot)
    assert len(snap.rows) == 1
    assert snap.rows[0].strike == 23000.0
    assert snap.expiry == exp


def test_load_prev_snapshot_none_on_first_run() -> None:
    class _EmptyCursor:
        def __enter__(self) -> _EmptyCursor:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def execute(self, _sql: str, _params: tuple) -> None:
            pass

        def fetchone(self) -> tuple | None:
            return (None,)

        def fetchall(self) -> list[tuple]:
            return []

    class _EmptyConn:
        def cursor(self) -> _EmptyCursor:
            return _EmptyCursor()

    assert load_prev_snapshot(_EmptyConn(), instrument_id=1) is None
