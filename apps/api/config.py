"""API settings from environment."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    web_origin: str = "http://localhost:3000"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    metrics_max_rows: int = 2000
    metrics_max_days: int = 7
    chain_top_oi_limit: int = 5

    ws_poll_seconds: float = 3.0


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
