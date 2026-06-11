"""Auth enforcement tests."""
from __future__ import annotations

from fastapi.testclient import TestClient

from tests.api.conftest import make_token


def test_instruments_requires_auth(client: TestClient) -> None:
    resp = client.get("/instruments")
    assert resp.status_code == 401


def test_instruments_rejects_expired_token(client: TestClient) -> None:
    token = make_token(expired=True)
    resp = client.get("/instruments", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_instruments_rejects_bad_token(client: TestClient) -> None:
    resp = client.get("/instruments", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401
