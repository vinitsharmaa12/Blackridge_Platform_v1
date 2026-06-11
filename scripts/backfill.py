"""Backfill: load existing nifty_data/*.json into option_snapshots + metrics.

Processes files in chronological order so prev-snapshot metrics (cog_shift,
buildup) are correct. Idempotent — safe to re-run.

    python -m scripts.backfill --dry-run         # parse + enrich, no DB needed
    python -m scripts.backfill                    # write to DATABASE_URL
    python -m scripts.backfill --symbol NIFTY --dir nifty_data
"""
from __future__ import annotations
from dotenv import load_dotenv
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

load_dotenv()

from core.enrich import compute_metrics
from core.normalize import normalize_file


def _files(data_dir: Path) -> list[Path]:
    # filenames are nifty_YYYYMMDD_HHMMSS.json → lexical sort == chronological
    return sorted(data_dir.glob("*.json"))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Backfill NSE JSONs into Postgres.")
    ap.add_argument("--symbol", default="NIFTY")
    ap.add_argument("--dir", default="nifty_data", type=Path)
    ap.add_argument("--dry-run", action="store_true",
                    help="Normalize + enrich only; do not touch the database.")
    args = ap.parse_args(argv)

    files = _files(args.dir)
    if not files:
        print(f"No JSON files in {args.dir}", file=sys.stderr)
        return 1
    print(f"Found {len(files)} files in {args.dir} (symbol={args.symbol})")

    if args.dry_run:
        prev = None
        total_rows = ok = bad = 0
        for p in files:
            try:
                snap = normalize_file(p)
                m = compute_metrics(snap, prev=prev)
                total_rows += len(snap.rows)
                ok += 1
                prev = snap
            except Exception as exc:  # noqa: BLE001
                bad += 1
                print(f"  ! {p.name}: {exc}")
        print(f"DRY RUN ok: parsed {ok} files, {bad} failed, "
              f"{total_rows} strike-rows, {ok} metrics rows (nothing written).")
        return 0 if bad == 0 else 2

    # Live write
    from core import db

    with db.connect() as conn:
        instrument_id = db.get_instrument_id(conn, args.symbol)
        prev = None
        total_rows = written = bad = 0
        for p in files:
            try:
                snap = normalize_file(p)
                m = compute_metrics(snap, prev=prev)
                total_rows += db.write(conn, instrument_id, snap, m)
                written += 1
                prev = snap
            except Exception as exc:  # noqa: BLE001
                bad += 1
                print(f"  ! {p.name}: {exc}")
        print(f"Backfill done: {written} snapshots written ({bad} failed), "
              f"{total_rows} strike-rows into instrument_id={instrument_id}.")
    return 0 if bad == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
