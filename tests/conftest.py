"""Shared pytest fixtures."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
NIFTY_DATA = ROOT / "nifty_data"


@pytest.fixture
def project_root() -> Path:
    return ROOT


@pytest.fixture
def sample_chain_json() -> dict:
    """Real NSE fixture with records.expiryDates and strike data."""
    path = NIFTY_DATA / "nifty_20260608_103626.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def empty_chain_json() -> dict:
    return {}
