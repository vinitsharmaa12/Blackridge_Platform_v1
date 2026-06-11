"""Shared pytest fixtures."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"


@pytest.fixture
def project_root() -> Path:
    return ROOT


@pytest.fixture
def sample_chain_json() -> dict:
    """Real NSE fixture with records.expiryDates and strike data."""
    path = FIXTURES / "nifty_20260608_103626.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def empty_chain_json() -> dict:
    path = FIXTURES / "empty_chain.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)
