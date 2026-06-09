("""
Preprocessing utilities:
- Finds the latest CSV in `nifty_data_csv/`
- Computes top-3 CE highest OI strikes and top-3 PE highest OI strikes
- Reads overall CE/PE open interest totals from the CSV (columns `Overall_CE_openInterest`, `Overall_PE_openInterest`)

Run as a script to print a short summary.
""")

import csv
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional


DATA_DIR = Path("nifty_data_csv")
JSON_DIR = Path("nifty_data")
OUTPUT_DIR = Path("preprocessed_output")
OUTPUT_DIR.mkdir(exist_ok=True)


def get_latest_csv(directory: Path = DATA_DIR) -> Path:
	files = list(directory.glob("*.csv"))
	if not files:
		raise FileNotFoundError(f"No CSV files found in {directory}")
	latest = max(files, key=lambda p: p.stat().st_mtime)
	return latest


def read_rows(csv_path: Path) -> List[Dict[str, str]]:
	with csv_path.open("r", encoding="utf-8", newline="") as f:
		reader = csv.DictReader(f)
		return list(reader)


def to_number(v: str) -> float:
	if v is None or v == "":
		return 0.0
	try:
		return float(v)
	except Exception:
		# Remove commas and try again
		try:
			return float(v.replace(",", ""))
		except Exception:
			return 0.0


def top_n_by_oi(rows: List[Dict[str, str]], prefix: str, n: int = 3) -> List[Tuple[int, float]]:
	# prefix: 'CE' or 'PE'
	items: List[Tuple[int, float]] = []
	oi_key = f"{prefix}_openInterest"
	# prefer CE_strikePrice as canonical strike column
	for r in rows:
		oi = to_number(r.get(oi_key, ""))
		strike = r.get("CE_strikePrice") or r.get("strikePrice") or r.get("CE_strikePrice")
		try:
			strike_val = int(float(strike))
		except Exception:
			strike_val = None
		items.append((strike_val, oi))

	# filter where strike is not None
	items = [it for it in items if it[0] is not None]
	items.sort(key=lambda x: x[1], reverse=True)
	return items[:n]


def read_overall_totals(rows: List[Dict[str, str]]) -> Dict[str, float]:
	if not rows:
		return {"Overall_CE_openInterest": 0.0, "Overall_PE_openInterest": 0.0,
				"Overall_CE_totalTradedVolume": 0.0, "Overall_PE_totalTradedVolume": 0.0}
	first = rows[0]
	return {
		"Overall_CE_openInterest": to_number(first.get("Overall_CE_openInterest", "0")),
		"Overall_PE_openInterest": to_number(first.get("Overall_PE_openInterest", "0")),
		"Overall_CE_totalTradedVolume": to_number(first.get("Overall_CE_totalTradedVolume", "0")),
		"Overall_PE_totalTradedVolume": to_number(first.get("Overall_PE_totalTradedVolume", "0")),
	}


def get_underlying_from_rows(rows: List[Dict[str, str]]) -> float:
	for r in rows:
		uv = r.get("underlyingValue") or r.get("underlying_value")
		if uv not in (None, ""):
			try:
				return float(uv)
			except Exception:
				continue
	return 0.0


def get_underlying_from_json_for_csv(csv_path: Path) -> float:
	json_path = JSON_DIR / (csv_path.stem + ".json")
	if not json_path.exists():
		return 0.0
	try:
		with json_path.open("r", encoding="utf-8") as f:
			data = json.load(f)
		if isinstance(data, dict) and "records" in data and isinstance(data["records"], dict):
			rows = data["records"].get("data", [])
		elif isinstance(data, dict) and "data" in data:
			rows = data.get("data", [])
		else:
			rows = []
		for r in rows:
			ce = r.get("CE") or {}
			pe = r.get("PE") or {}
			uv = ce.get("underlyingValue") or pe.get("underlyingValue")
			if uv is not None:
				try:
					return float(uv)
				except Exception:
					continue
	except Exception:
		return 0.0
	return 0.0


def strikes_from_rows(rows: List[Dict[str, str]]) -> List[int]:
	s = set()
	for r in rows:
		strike = r.get("CE_strikePrice") or r.get("strikePrice")
		try:
			s.add(int(float(strike)))
		except Exception:
			continue
	return sorted(s)


def get_center_index_for_underlying(strikes: List[int], underlying: float) -> Optional[int]:
	if not strikes:
		return None
	# find index of strike closest to underlying
	closest_idx = min(range(len(strikes)), key=lambda i: abs(strikes[i] - underlying))
	return closest_idx


def window_strikes(strikes: List[int], center_idx: int, window: int = 10) -> List[int]:
	if center_idx is None:
		return strikes
	start = max(0, center_idx - window)
	end = min(len(strikes) - 1, center_idx + window)
	return strikes[start:end + 1]


from datetime import datetime


def summary_for_csv(csv_path: Path) -> Dict[str, object]:
	rows = read_rows(csv_path)
	totals = read_overall_totals(rows)

	# get underlying value (prefer CSV field, fallback to JSON)
	underlying = get_underlying_from_rows(rows)
	if underlying == 0.0:
		underlying = get_underlying_from_json_for_csv(Path(csv_path))

	# build strike list and window around underlying
	strikes = strikes_from_rows(rows)
	center_idx = get_center_index_for_underlying(strikes, underlying)
	window = window_strikes(strikes, center_idx, window=10)

	# filter rows to only those strikes in window
	window_set = set(window)
	rows_in_window = [
		r for r in rows
		if (r.get("CE_strikePrice") and int(float(r.get("CE_strikePrice"))) in window_set)
		or (r.get("strikePrice") and int(float(r.get("strikePrice"))) in window_set)
	]

	top3_ce = top_n_by_oi(rows_in_window, "CE", 3)
	top3_pe = top_n_by_oi(rows_in_window, "PE", 3)

	return {
		"file": str(csv_path),
		"underlyingValue": underlying,
		"window_strikes": window,
		"top3_ce": top3_ce,
		"top3_pe": top3_pe,
		"totals": totals,
	}


def summary_for_latest() -> Dict[str, object]:
	return summary_for_csv(get_latest_csv())


def list_to_string(items) -> str:
	if items is None:
		return ""
	if isinstance(items, list):
		return ";".join(str(x) for x in items)
	return str(items)


def format_top_entries(entries: List[Tuple[int, float]], prefix: str) -> Dict[str, str]:
	row = {}
	for i in range(3):
		strike_key = f"top{i + 1}{prefix}_strike"
		value_key = f"top{i + 1}{prefix}_oi_value"
		if i < len(entries):
			strike, oi = entries[i]
			row[strike_key] = str(strike)
			row[value_key] = str(int(oi) if oi == int(oi) else oi)
		else:
			row[strike_key] = ""
			row[value_key] = ""
	return row


def write_summary_csv(summary: Dict[str, object], output_dir: Path = OUTPUT_DIR) -> Path:
	output_dir.mkdir(exist_ok=True)
	output_path = output_dir / "preprocessed.csv"
	fieldnames = [
		"timestamp",
		"input_csv",
		"underlyingValue",
		"top1ce_strike",
		"top1ce_oi_value",
		"top2ce_strike",
		"top2ce_oi_value",
		"top3ce_strike",
		"top3ce_oi_value",
		"top1pe_strike",
		"top1pe_oi_value",
		"top2pe_strike",
		"top2pe_oi_value",
		"top3pe_strike",
		"top3pe_oi_value",
		"Overall_CE_openInterest",
		"Overall_PE_openInterest",
		"Overall_CE_totalTradedVolume",
		"Overall_PE_totalTradedVolume",
	]
	top_ce = format_top_entries(summary.get("top3_ce", []), "ce")
	top_pe = format_top_entries(summary.get("top3_pe", []), "pe")
	row = {
		"timestamp": datetime.now().isoformat(),
		"input_csv": summary.get("file", ""),
		"underlyingValue": summary.get("underlyingValue", ""),
		**top_ce,
		**top_pe,
		"Overall_CE_openInterest": summary.get("totals", {}).get("Overall_CE_openInterest", 0.0),
		"Overall_PE_openInterest": summary.get("totals", {}).get("Overall_PE_openInterest", 0.0),
		"Overall_CE_totalTradedVolume": summary.get("totals", {}).get("Overall_CE_totalTradedVolume", 0.0),
		"Overall_PE_totalTradedVolume": summary.get("totals", {}).get("Overall_PE_totalTradedVolume", 0.0),
	}
	write_header = not output_path.exists()
	with output_path.open("a", encoding="utf-8", newline="") as f:
		writer = csv.DictWriter(f, fieldnames=fieldnames)
		if write_header:
			writer.writeheader()
		writer.writerow(row)
	return output_path


if __name__ == "__main__":
	import sys
	if len(sys.argv) > 1:
		csv_path = Path(sys.argv[1])
		if not csv_path.exists():
			raise FileNotFoundError(f"CSV file not found: {csv_path}")
		summary = summary_for_csv(csv_path)
	else:
		summary = summary_for_latest()
	output_path = write_summary_csv(summary)
	print("Latest CSV:", summary["file"])
	print("Underlying value:", summary["underlyingValue"])
	print("Top 3 CE by OI (strike:oi):")
	for s, oi in summary["top3_ce"]:
		print(f"  {s}:{int(oi) if oi == int(oi) else oi}")
	print("Top 3 PE by OI (strike:oi):")
	for s, oi in summary["top3_pe"]:
		print(f"  {s}:{int(oi) if oi == int(oi) else oi}")
	print("Overall totals:")
	for k, v in summary["totals"].items():
		print(f"  {k}: {int(v) if v == int(v) else v}")
	print(f"Saved preprocessing CSV: {output_path}")

