"""API entrypoint tests."""
from __future__ import annotations

import pytest

from apps.api.__main__ import resolve_listen_port
from apps.api.config import Settings, get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_resolve_listen_port_prefers_railway_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PORT", "8080")
    monkeypatch.setenv("API_PORT", "8000")
    settings = Settings(
        database_url="postgresql://localhost/test",
        api_port=8000,
    )
    assert resolve_listen_port(settings) == 8080


def test_settings_port_alias_prefers_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
    monkeypatch.setenv("PORT", "8080")
    monkeypatch.setenv("API_PORT", "8000")
    assert get_settings().api_port == 8080
