"""API test fixtures."""
from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from jose import jwt

TEST_SECRET = "test-jwt-secret-for-pytest-only-32chars"
TEST_USER_ID = UUID("11111111-1111-1111-1111-111111111111")
TEST_SUPABASE_URL = "https://testproject.supabase.co"


@pytest.fixture(scope="session", autouse=True)
def _api_env() -> None:
    os.environ.setdefault("DATABASE_URL", os.environ.get("DATABASE_URL", "postgresql://localhost/test"))
    os.environ.setdefault("SUPABASE_URL", TEST_SUPABASE_URL)
    os.environ.setdefault("SUPABASE_JWT_SECRET", TEST_SECRET)
    os.environ.setdefault("WEB_ORIGIN", "http://localhost:3000")


def make_token(
    user_id: UUID = TEST_USER_ID,
    *,
    secret: str = TEST_SECRET,
    expired: bool = False,
) -> str:
    now = datetime.now(tz=UTC)
    exp = now - timedelta(hours=1) if expired else now + timedelta(hours=1)
    payload = {
        "sub": str(user_id),
        "aud": "authenticated",
        "iss": f"{TEST_SUPABASE_URL}/auth/v1",
        "exp": exp,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    async def _noop(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr("apps.api.db.init_pool", _noop)
    monkeypatch.setattr("apps.api.db.close_pool", _noop)
    monkeypatch.setattr("apps.api.ws.start_ws_background", _noop)
    monkeypatch.setattr("apps.api.ws.stop_ws_background", _noop)

    from apps.api.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_header() -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token()}"}
