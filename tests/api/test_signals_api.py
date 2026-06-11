"""Signals API endpoint tests."""
from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

SNAP_TIME = datetime(2026, 6, 8, 10, 30, tzinfo=UTC)
PREV_TIME = datetime(2026, 6, 8, 10, 0, tzinfo=UTC)

SAMPLE_METRICS = {
    "time": SNAP_TIME,
    "instrument_id": 1,
    "expiry": date(2026, 6, 9),
    "dte": 1,
    "underlying": 25000.0,
    "pcr_oi": 1.25,
    "pcr_volume": 1.0,
    "ce_cog": 25000.0,
    "pe_cog": 24900.0,
    "cog_shift": 15.0,
    "atm_strike": 25000.0,
    "atm_iv": 12.0,
    "iv_skew": 2.5,
    "india_vix": None,
    "atm_straddle": 200.0,
    "expected_move": 200.0,
    "max_pain": 24900.0,
    "total_ce_oi": 1000000,
    "total_pe_oi": 1250000,
    "net_ce_oi_change": -30000,
    "net_pe_oi_change": 50000,
    "total_ce_volume": 100000,
    "total_pe_volume": 100000,
    "buy_sell_imbalance": 1.0,
    "buildup": "long_buildup",
    "immediate_support": 24800.0,
    "major_support": 24500.0,
    "immediate_resistance": 25100.0,
    "major_resistance": 25500.0,
    "sentiment_score": 35,
    "sentiment_label": "Bullish",
    "drivers": ["PCR 1.25 (bullish)."],
}

PREV_METRICS = {
    **SAMPLE_METRICS,
    "time": PREV_TIME,
    "pe_cog": 24885.0,
    "cog_shift": None,
    "underlying": 24950.0,
}

INST = {
    "id": 1,
    "symbol": "NIFTY",
    "name": "Nifty 50",
    "type": "index",
    "segment": "NSE-OPT",
    "lot_size": 75,
    "tick_size": None,
    "active": True,
}


def _mock_user_conn() -> AsyncMock:
    mock = AsyncMock()
    mock.__aenter__ = AsyncMock(return_value=object())
    mock.__aexit__ = AsyncMock(return_value=None)
    return mock


def test_signals_latest_success(client: TestClient, auth_header: dict[str, str]) -> None:
    with patch(
        "apps.api.routers.signals.user_connection",
        return_value=_mock_user_conn(),
    ), patch(
        "apps.api.routers.signals.fetch_instrument",
        new=AsyncMock(return_value=INST),
    ), patch(
        "apps.api.routers.signals.fetch_latest_metrics",
        new=AsyncMock(return_value=SAMPLE_METRICS),
    ), patch(
        "apps.api.routers.signals.fetch_prev_metrics",
        new=AsyncMock(return_value=PREV_METRICS),
    ), patch(
        "apps.api.routers.signals.fetch_day_underlying_range",
        new=AsyncMock(return_value=(24950.0, 25050.0, 24900.0)),
    ):
        resp = client.get("/instruments/NIFTY/signals", headers=auth_header)

    assert resp.status_code == 200
    body = resp.json()
    assert body["underlying"] == 25000.0
    assert body["overall"]["key"] == "overall_read"
    assert len(body["signals"]) <= 6
    assert body["signals"][0]["key"] == "overall_read"
    assert all(1 <= s["strength"] <= 3 for s in body["signals"])
    assert all(s["evidence"] for s in body["signals"])


def test_signals_unknown_symbol(client: TestClient, auth_header: dict[str, str]) -> None:
    with patch(
        "apps.api.routers.signals.user_connection",
        return_value=_mock_user_conn(),
    ), patch(
        "apps.api.routers.signals.fetch_instrument",
        new=AsyncMock(return_value=None),
    ):
        resp = client.get("/instruments/UNKNOWN/signals", headers=auth_header)

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Unknown symbol"


def test_signals_no_metrics(client: TestClient, auth_header: dict[str, str]) -> None:
    with patch(
        "apps.api.routers.signals.user_connection",
        return_value=_mock_user_conn(),
    ), patch(
        "apps.api.routers.signals.fetch_instrument",
        new=AsyncMock(return_value=INST),
    ), patch(
        "apps.api.routers.signals.fetch_latest_metrics",
        new=AsyncMock(return_value=None),
    ):
        resp = client.get("/instruments/NIFTY/signals", headers=auth_header)

    assert resp.status_code == 404
    assert resp.json()["detail"] == "No metrics yet"


def test_signals_at_timestamp(client: TestClient, auth_header: dict[str, str]) -> None:
    at = SNAP_TIME.isoformat().replace("+00:00", "Z")
    with patch(
        "apps.api.routers.signals.user_connection",
        return_value=_mock_user_conn(),
    ), patch(
        "apps.api.routers.signals.fetch_instrument",
        new=AsyncMock(return_value=INST),
    ), patch(
        "apps.api.routers.signals.fetch_metrics_at_time",
        new=AsyncMock(return_value=SAMPLE_METRICS),
    ), patch(
        "apps.api.routers.signals.fetch_prev_metrics",
        new=AsyncMock(return_value=PREV_METRICS),
    ), patch(
        "apps.api.routers.signals.fetch_day_underlying_range",
        new=AsyncMock(return_value=(24950.0, 25050.0, 24900.0)),
    ):
        resp = client.get(f"/instruments/NIFTY/signals?at={at}", headers=auth_header)

    assert resp.status_code == 200
    assert resp.json()["time"].startswith("2026-06-08")


def test_signals_invalid_at(client: TestClient, auth_header: dict[str, str]) -> None:
    resp = client.get("/instruments/NIFTY/signals?at=not-a-date", headers=auth_header)
    assert resp.status_code == 422


def test_signals_requires_auth(client: TestClient) -> None:
    resp = client.get("/instruments/NIFTY/signals")
    assert resp.status_code == 401
