"""One ingestion tick: fetch → normalize → prev → enrich → write."""
from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core import db
from core.enrich import compute_metrics
from core.normalize import normalize
from core.sources.nse import fetch_chain, fetch_india_vix, is_empty_response
from worker.config import WorkerSettings

logger = logging.getLogger(__name__)

FetchFn = Callable[[str], dict]


@dataclass
class TickResult:
    symbol: str
    success: bool
    skipped: bool = False
    rows_written: int = 0
    expiry: str | None = None
    sentiment: str | None = None
    pcr_oi: float | None = None
    duration_ms: float = 0.0
    error: str | None = None


@dataclass
class IngestCounters:
    success: int = 0
    failure: int = 0
    skipped: int = 0


COUNTERS = IngestCounters()


def _archive_raw(raw: dict, symbol: str, archive_dir: str) -> None:
    out_dir = Path(archive_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = symbol.lower()
    path = out_dir / f"{prefix}_{ts}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2)


def run_tick(
    conn,
    symbol: str,
    settings: WorkerSettings,
    *,
    fetch_fn: FetchFn | None = None,
) -> TickResult:
    """Process one instrument tick. Fail-soft: returns result, never raises."""
    started = time.perf_counter()
    fetch = fetch_fn or (
        lambda s: fetch_chain(
            s,
            expiry=None,
            timeout=settings.nse_timeout,
            max_retries=settings.nse_max_retries,
            expiry_mode=settings.expiry_mode,
        )
    )

    try:
        raw = fetch(symbol)
        if is_empty_response(raw):
            COUNTERS.skipped += 1
            return TickResult(
                symbol=symbol,
                success=False,
                skipped=True,
                error="empty NSE response",
                duration_ms=(time.perf_counter() - started) * 1000,
            )

        if settings.archive_raw:
            _archive_raw(raw, symbol, settings.archive_dir)

        snap = normalize(raw, source_name=symbol)
        instrument_id = db.get_instrument_id(conn, symbol)
        prev = db.load_prev_snapshot(conn, instrument_id)

        india_vix: float | None = None
        if settings.fetch_india_vix:
            india_vix = fetch_india_vix(
                timeout=settings.nse_timeout,
                max_retries=settings.nse_max_retries,
            )

        metrics_row = compute_metrics(snap, prev=prev, india_vix=india_vix)
        rows_written = db.write(conn, instrument_id, snap, metrics_row)

        expiry_str = snap.expiry.isoformat() if snap.expiry else None
        duration_ms = (time.perf_counter() - started) * 1000
        COUNTERS.success += 1

        logger.info(
            "tick_ok symbol=%s expiry=%s ts=%s rows=%d pcr_oi=%s sentiment=%s duration_ms=%.0f",
            symbol,
            expiry_str,
            snap.time.isoformat(),
            rows_written,
            metrics_row.pcr_oi,
            metrics_row.sentiment_label,
            duration_ms,
        )
        return TickResult(
            symbol=symbol,
            success=True,
            rows_written=rows_written,
            expiry=expiry_str,
            sentiment=metrics_row.sentiment_label,
            pcr_oi=metrics_row.pcr_oi,
            duration_ms=duration_ms,
        )
    except Exception as exc:  # noqa: BLE001 — fail soft per PRD
        COUNTERS.failure += 1
        duration_ms = (time.perf_counter() - started) * 1000
        logger.exception("tick_failed symbol=%s duration_ms=%.0f", symbol, duration_ms)
        return TickResult(
            symbol=symbol,
            success=False,
            error=str(exc),
            duration_ms=duration_ms,
        )


def run_all(settings: WorkerSettings | None = None) -> list[TickResult]:
    """Run one tick for every configured instrument."""
    cfg = settings or WorkerSettings()  # type: ignore[call-arg]
    os.environ["DATABASE_URL"] = cfg.database_url
    results: list[TickResult] = []
    with db.connect() as conn:
        for symbol in cfg.instruments:
            results.append(run_tick(conn, symbol, cfg))
    return results
