"""CLI entrypoint: python -m apps.api"""
from __future__ import annotations

import os

import uvicorn

from apps.api.config import Settings, get_settings


def resolve_listen_port(settings: Settings) -> int:
    """Railway injects PORT; prefer it over a stale API_PORT variable."""
    if port := os.environ.get("PORT"):
        return int(port)
    return settings.api_port


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "apps.api.main:app",
        host=settings.api_host,
        port=resolve_listen_port(settings),
        log_level="info",
    )


if __name__ == "__main__":
    main()
