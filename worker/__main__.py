"""Entrypoint: python -m worker  |  python -m worker --once"""
from __future__ import annotations

import logging
import sys

from worker.ingest import run_all
from worker.scheduler import main

logger = logging.getLogger(__name__)


def run_once() -> int:
    """Run a single ingestion tick (all configured instruments). For local verification."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    results = run_all()
    for result in results:
        if result.success:
            logger.info(
                "verify_ok symbol=%s rows=%d expiry=%s pcr_oi=%s sentiment=%s",
                result.symbol,
                result.rows_written,
                result.expiry,
                result.pcr_oi,
                result.sentiment,
            )
        elif result.skipped:
            logger.warning("verify_skipped symbol=%s error=%s", result.symbol, result.error)
        else:
            logger.error("verify_failed symbol=%s error=%s", result.symbol, result.error)
    failures = sum(1 for r in results if not r.success and not r.skipped)
    return 1 if failures else 0


if __name__ == "__main__":
    if "--once" in sys.argv:
        raise SystemExit(run_once())
    raise SystemExit(main())
