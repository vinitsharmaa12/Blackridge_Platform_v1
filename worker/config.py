"""Ingestion worker configuration (pydantic-settings)."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ExpiryMode = Literal["nearest", "nearest_weekly"]


class WorkerSettings(BaseSettings):
    """Worker env config. Workers must use a service-role DATABASE_URL."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(alias="DATABASE_URL")
    ingest_interval_seconds: int = Field(180, alias="INGEST_INTERVAL_SECONDS")
    market_open: str = Field("09:15", alias="MARKET_OPEN")
    market_close: str = Field("15:35", alias="MARKET_CLOSE")
    instruments: list[str] = Field(default_factory=lambda: ["NIFTY"], alias="INSTRUMENTS")
    archive_raw: bool = Field(True, alias="ARCHIVE_RAW")
    archive_dir: str = Field("nifty_data", alias="ARCHIVE_DIR")
    fetch_india_vix: bool = Field(False, alias="FETCH_INDIA_VIX")
    nse_timeout: float = Field(15.0, alias="NSE_TIMEOUT")
    nse_max_retries: int = Field(3, alias="NSE_MAX_RETRIES")
    expiry_mode: ExpiryMode = Field("nearest", alias="EXPIRY_MODE")

    @field_validator("instruments", mode="before")
    @classmethod
    def _parse_instruments(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        if isinstance(v, list):
            return [str(s).strip() for s in v if str(s).strip()]
        return ["NIFTY"]


def get_settings() -> WorkerSettings:
    return WorkerSettings()  # type: ignore[call-arg]
