"""API settings tests."""
from __future__ import annotations

import pytest

from apps.api.config import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_settings_reads_railway_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
    monkeypatch.delenv("API_PORT", raising=False)
    monkeypatch.setenv("PORT", "8080")
    assert get_settings().api_port == 8080


def test_api_port_prefers_railway_port_over_api_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
    monkeypatch.setenv("PORT", "8080")
    monkeypatch.setenv("API_PORT", "9000")
    assert get_settings().api_port == 8080
