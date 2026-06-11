"""Dev runner: normalize + enrich raw NSE JSON files and print the metrics row.

No database required — this validates core/ against the JSONs already in
nifty_data/. Pass one or two files (two exercises prev-snapshot metrics like
cog_shift and buildup); with no args it uses the two most recent files.

    python -m scripts.process_json
    python -m scripts.process_json nifty_data/nifty_20260608_092103.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# allow running as `python scripts/process_json.py` too
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.normalize import normalize_file
from core.enrich import compute_metrics

DATA_DIR = Path("nifty_data")


def _default_files() -> list[Path]:
    files = sorted(DATA_DIR.glob("*.json"))
    return files[-2:] if len(files) >= 2 else files


def main(argv: list[str]) -> int:
    paths = [Path(a) for a in argv] or _default_files()
    if not paths:
        print("No JSON files found.", file=sys.stderr)
        return 1

    prev = None
    for p in paths:
        snap = normalize_file(p)
        row = compute_metrics(snap, prev=prev)
        print(f"\n=== {p.name} ===")
        print(f"strikes: {len(snap.rows)}  underlying: {snap.underlying}  "
              f"expiry: {snap.expiry}  dte: {snap.dte}")
        print(json.dumps(row.as_dict(), default=str, indent=2))
        prev = snap
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
