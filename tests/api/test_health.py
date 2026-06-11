"""Health endpoint tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    with patch("apps.api.main.check_db", new=AsyncMock(return_value=True)):
        resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"


def test_health_degraded(client: TestClient) -> None:
    with patch("apps.api.main.check_db", new=AsyncMock(return_value=False)):
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "degraded"
