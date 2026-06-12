"""APScheduler wiring + IST market-hours guard."""
from __future__ import annotations

import logging
import signal
import sys
from datetime import datetime
from datetime import time as dt_time
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler

from worker.config import WorkerSettings, get_settings
from worker.ingest import COUNTERS, run_all

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


def _parse_hhmm(value: str) -> dt_time:
    hour, minute = value.strip().split(":")
    return dt_time(int(hour), int(minute))


def is_market_open(
    now: datetime,
    *,
    market_open: str = "09:15",
    market_close: str = "15:35",
) -> bool:
    """True on weekdays within IST market hours."""
    local = now.astimezone(IST)
    if local.weekday() >= 5:
        return False
    open_t = _parse_hhmm(market_open)
    close_t = _parse_hhmm(market_close)
    current = local.time()
    return open_t <= current <= close_t


def is_morning_burst_window(
    now: datetime,
    *,
    burst_start: str = "09:21",
    burst_end: str = "09:25",
) -> bool:
    """True on weekdays within the high-frequency morning burst (IST)."""
    local = now.astimezone(IST)
    if local.weekday() >= 5:
        return False
    start_t = _parse_hhmm(burst_start)
    end_t = _parse_hhmm(burst_end)
    return start_t <= local.time() < end_t


def _tick(settings: WorkerSettings) -> None:
    now = datetime.now(tz=IST)
    if not is_market_open(
        now, market_open=settings.market_open, market_close=settings.market_close
    ):
        logger.debug("idle outside market hours now=%s", now.isoformat())
        _maybe_session_close(now, settings)
        return
    logger.info("scheduler_tick instruments=%s", settings.instruments)
    run_all(settings)
    _maybe_session_close(now, settings)


def _morning_burst_tick(settings: WorkerSettings) -> None:
    """10s cadence during morning burst — matches _ref/orchestrator.py open window."""
    now = datetime.now(tz=IST)
    if not is_morning_burst_window(
        now,
        burst_start=settings.morning_burst_start,
        burst_end=settings.morning_burst_end,
    ):
        return
    if not is_market_open(
        now, market_open=settings.market_open, market_close=settings.market_close
    ):
        return
    logger.info("morning_burst_tick instruments=%s", settings.instruments)
    run_all(settings)


def _maybe_session_close(now: datetime, settings: WorkerSettings) -> None:
    """Enqueue session-close insight jobs once per day after market close."""
    try:
        from insights.runner import is_session_close_window, run_session_close
    except ImportError:
        return
    if not is_session_close_window(now, market_close=settings.market_close):
        return
    try:
        run_session_close()
    except Exception:  # noqa: BLE001 — fail soft
        logger.exception("session_close_insights_failed")


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = get_settings()

    scheduler = BlockingScheduler(timezone=IST)
    scheduler.add_job(
        _tick,
        "interval",
        seconds=settings.ingest_interval_seconds,
        args=[settings],
        id="ingest",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _morning_burst_tick,
        "interval",
        seconds=settings.morning_burst_interval_seconds,
        args=[settings],
        id="morning_burst",
        max_instances=1,
        coalesce=True,
    )
    burst_hour, burst_minute = settings.morning_burst_start.split(":")
    scheduler.add_job(
        _tick,
        "cron",
        day_of_week="mon-fri",
        hour=int(burst_hour),
        minute=int(burst_minute),
        args=[settings],
        id="morning_anchor",
        max_instances=1,
        coalesce=True,
    )

    def _shutdown(signum: int, _frame: object) -> None:
        logger.info("shutdown signal=%s success=%d failure=%d skipped=%d",
                    signum, COUNTERS.success, COUNTERS.failure, COUNTERS.skipped)
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info(
        "worker_start interval_s=%d market=%s-%s IST instruments=%s",
        settings.ingest_interval_seconds,
        settings.market_open,
        settings.market_close,
        settings.instruments,
    )
    scheduler.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
