"""Tests for worker settings parsing."""
from __future__ import annotations

import pytest

from worker.config import WorkerSettings


def test_instruments_from_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")
    monkeypatch.setenv("INSTRUMENTS", "NIFTY,BANKNIFTY")
    cfg = WorkerSettings()  # type: ignore[call-arg]
    assert cfg.instruments == ["NIFTY", "BANKNIFTY"]


def test_instruments_single_symbol(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")
    monkeypatch.setenv("INSTRUMENTS", "NIFTY")
    cfg = WorkerSettings()  # type: ignore[call-arg]
    assert cfg.instruments == ["NIFTY"]
