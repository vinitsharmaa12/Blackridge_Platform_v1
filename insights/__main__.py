"""CLI: python -m insights [--process-jobs | --session-close]"""
from __future__ import annotations

import argparse
import logging

from insights.runner import process_queued_jobs, run_session_close


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Insights engine runner")
    parser.add_argument("--process-jobs", action="store_true", help="Process queued jobs")
    parser.add_argument("--session-close", action="store_true", help="Enqueue session-close jobs")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    if args.session_close:
        run_session_close()
        return 0
    if args.process_jobs:
        process_queued_jobs()
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
