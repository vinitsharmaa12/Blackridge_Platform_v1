"""Dev token mint endpoint tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import TEST_USER_ID, apply_test_api_env


def _dev_client(monkeypatch: pytest.MonkeyPatch, *, enabled: bool) -> TestClient:
    async def _noop(*_args: object, **_kwargs: object) -> None:
        return None

    apply_test_api_env(monkeypatch)
    monkeypatch.setenv("ENABLE_DEV_TOKEN", "true" if enabled else "false")
    monkeypatch.setattr("apps.api.db.init_pool", _noop)
    monkeypatch.setattr("apps.api.db.close_pool", _noop)
    monkeypatch.setattr("apps.api.ws.start_ws_background", _noop)
    monkeypatch.setattr("apps.api.ws.stop_ws_background", _noop)

    from apps.api.main import create_app

    app = create_app()
    return TestClient(app)


def test_dev_token_not_mounted_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    with _dev_client(monkeypatch, enabled=False) as client:
        resp = client.post("/dev/token")
    assert resp.status_code == 404


def test_dev_token_mints_jwt(monkeypatch: pytest.MonkeyPatch) -> None:
    with _dev_client(monkeypatch, enabled=True) as client:
        resp = client.post("/dev/token", json={"email": "dev@local.test"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600
    assert isinstance(body["access_token"], str)
    assert body["access_token"]


def test_minted_token_authenticates_instruments(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_rows = [
        {
            "id": 1,
            "symbol": "NIFTY",
            "name": "Nifty 50",
            "type": "index",
            "segment": "NSE-OPT",
            "lot_size": 75,
            "tick_size": None,
            "active": True,
        }
    ]

    with _dev_client(monkeypatch, enabled=True) as client:
        mint = client.post("/dev/token", json={"user_id": str(TEST_USER_ID)})
        assert mint.status_code == 200
        token = mint.json()["access_token"]

        with patch(
            "apps.api.routers.instruments.fetch_instruments",
            new=AsyncMock(return_value=mock_rows),
        ), patch(
            "apps.api.routers.instruments.user_connection",
        ) as mock_conn:
            mock_conn.return_value.__aenter__ = AsyncMock(return_value=object())
            mock_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            resp = client.get("/instruments", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    assert resp.json()[0]["symbol"] == "NIFTY"
