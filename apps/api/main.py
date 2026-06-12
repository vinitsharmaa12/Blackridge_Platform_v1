"""FastAPI application factory."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.config import Settings, get_settings
from apps.api.db import check_db, close_pool, init_pool
from apps.api.models import HealthResponse
from apps.api.routers import chain, insights, instruments, metrics, signals, watchlist
from apps.api.ws import start_ws_background, stop_ws_background


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    await init_pool(settings)
    _log_insights_env()
    await start_ws_background(settings)
    yield
    await stop_ws_background()
    await close_pool()


def _log_insights_env() -> None:
    """Warn when insight generation env is incomplete (on-demand runs in API process)."""
    import logging
    import os

    log = logging.getLogger(__name__)
    missing = [
        name
        for name, value in (
            ("OPENROUTER_API_KEY", os.getenv("OPENROUTER_API_KEY", "")),
            ("INSIGHTS_MODEL_CHEAP", os.getenv("INSIGHTS_MODEL_CHEAP", "")),
            ("INSIGHTS_MODEL_PREMIUM", os.getenv("INSIGHTS_MODEL_PREMIUM", "")),
        )
        if not value
    ]
    if missing:
        log.warning(
            "Insight generation disabled — missing env: %s. "
            "Set these on the API service for POST …/insights:generate.",
            ", ".join(missing),
        )
    else:
        log.info("Insight generation env present (OPENROUTER + model tiers)")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Blackridge API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    async def health(_: Settings = Depends(get_settings)) -> HealthResponse:
        ok = await check_db()
        return HealthResponse(status="ok" if ok else "degraded", db="ok" if ok else "error")

    app.include_router(instruments.router)
    app.include_router(metrics.router)
    app.include_router(signals.router)
    app.include_router(chain.router)
    app.include_router(insights.router)
    app.include_router(watchlist.router)
    if settings.enable_dev_token:
        from apps.api.routers import dev  # noqa: PLC0415

        app.include_router(dev.router)
    from apps.api import ws as ws_module  # noqa: PLC0415 — avoid circular import

    app.include_router(ws_module.router)
    return app


app = create_app()
