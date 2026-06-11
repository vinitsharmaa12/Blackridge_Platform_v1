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


def _tick(settings: WorkerSettings) -> None:
    now = datetime.now(tz=IST)
    if not is_market_open(
        now, market_open=settings.market_open, market_close=settings.market_close
    ):
        logger.debug("idle outside market hours now=%s", now.isoformat())
        return
    logger.info("scheduler_tick instruments=%s", settings.instruments)
    run_all(settings)


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
