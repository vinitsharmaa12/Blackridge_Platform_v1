"""Tests for NSE expiry resolution and fixture parsing."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from core.normalize import normalize
from core.sources.nse import (
    NseFetchError,
    fetch_chain,
    is_empty_response,
    resolve_expiry,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_normalize_fixture(sample_chain_json: dict) -> None:
    snap = normalize(sample_chain_json, source_name="fixture.json")
    assert len(snap.rows) > 100
    assert snap.expiry == date(2026, 6, 9)
    assert snap.underlying is not None


def test_resolve_expiry_nearest(sample_chain_json: dict) -> None:
    expiry = resolve_expiry(sample_chain_json, today=date(2026, 6, 8))
    assert expiry == "09-Jun-2026"


def test_resolve_expiry_no_future_raises(sample_chain_json: dict) -> None:
    with pytest.raises(ValueError, match="No expiryDates"):
        resolve_expiry(sample_chain_json, today=date(2031, 1, 1))


def test_is_empty_response(empty_chain_json: dict) -> None:
    assert is_empty_response(empty_chain_json) is True
    assert is_empty_response({"records": {"data": []}}) is True


def test_normalize_empty_raises(empty_chain_json: dict) -> None:
    with pytest.raises(ValueError, match="missing 'records'"):
        normalize(empty_chain_json)


def test_fetch_chain_with_expiry_mocked() -> None:
    fixture = json.loads((FIXTURES / "nifty_20260608_103626.json").read_text())
    session = MagicMock()
    session.headers = {}
    session.get.return_value = MagicMock(status_code=200)

    with patch("core.sources.nse.requests.Session", return_value=session):
        with patch("core.sources.nse._get_json", return_value=fixture):
            raw = fetch_chain("NIFTY", expiry="09-Jun-2026", max_retries=1)
    assert raw["records"]["data"]


def test_fetch_chain_auto_expiry_mocked() -> None:
    fixture = json.loads((FIXTURES / "nifty_20260608_103626.json").read_text())

    with patch("core.sources.nse.requests.Session") as sess_cls:
        session = MagicMock()
        session.headers = {}
        sess_cls.return_value = session
        with patch("core.sources.nse._get_json", side_effect=[fixture, fixture]):
            raw = fetch_chain("NIFTY", expiry=None, max_retries=1)
    assert raw["records"]["expiryDates"]


def test_fetch_chain_retries_on_timeout() -> None:
    fixture = json.loads((FIXTURES / "nifty_20260608_103626.json").read_text())
    calls = {"n": 0}

    def _get_json(_session, url, timeout):  # noqa: ARG001
        calls["n"] += 1
        if calls["n"] == 1:
            raise requests.Timeout("slow")
        return fixture

    with patch("core.sources.nse.requests.Session") as sess_cls:
        session = MagicMock()
        session.headers = {}
        sess_cls.return_value = session
        with patch("core.sources.nse._get_json", side_effect=_get_json):
            raw = fetch_chain("NIFTY", expiry="09-Jun-2026", max_retries=3)
    assert raw["records"]["data"]
    assert calls["n"] == 2


def test_fetch_chain_empty_raises() -> None:
    with patch("core.sources.nse.requests.Session") as sess_cls:
        session = MagicMock()
        session.headers = {}
        sess_cls.return_value = session
        with patch("core.sources.nse._get_json", return_value={}):
            with pytest.raises(NseFetchError, match="Empty"):
                fetch_chain("NIFTY", expiry="09-Jun-2026", max_retries=1)
