"""Backfill script behaviour."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.backfill import main


def test_backfill_dry_run_skips_empty_json(tmp_path: Path, sample_chain_json: dict) -> None:
    good = tmp_path / "nifty_20260101_100000.json"
    empty = tmp_path / "nifty_20260101_100100.json"
    good.write_text(json.dumps(sample_chain_json))
    empty.write_text("{}")

    rc = main(["--dry-run", "--dir", str(tmp_path)])
    assert rc == 0
