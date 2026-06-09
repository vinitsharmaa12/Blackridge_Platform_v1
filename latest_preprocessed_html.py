import csv
import sys
import webbrowser
import json
from datetime import datetime, timedelta, time as dtime
from pathlib import Path

from metrics import (
    calculate_cog,
    calculate_cog_shift,
    calculate_pcr,
    calculate_market_sentiment,
    analyze_migration,
    safe_int,
    to_number,
    calculate_price_change,
    compute_market_structure,
)

PREPROCESSED_CSV = Path("preprocessed_output/preprocessed.csv")
OUTPUT_HTML = Path("preprocessed_output/latest_preprocessed.html")
AUX_DATA_DIR = Path("nifty_data_csv")
OUTPUT_DIR = Path("preprocessed_output")
SNAPSHOT_DIR = Path("snapshot_output")
AUTO_REFRESH_SECONDS = 30

# Snapshot windows (inclusive start, exclusive end)
MORNING_WINDOW_START = dtime(9, 21)
MORNING_WINDOW_END = dtime(9, 22)
MIDDAY_WINDOW_START = dtime(12, 30)
MIDDAY_WINDOW_END = dtime(12, 31)
CLOSE_WINDOW_START = dtime(15, 0)
CLOSE_WINDOW_END = dtime(15, 1)

def read_preprocessed_rows(csv_path: Path):
    if not csv_path.exists():
        raise FileNotFoundError(f"Preprocessed CSV not found: {csv_path}")
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def latest_row(rows):
    if not rows:
        raise ValueError("No rows found in preprocessed CSV")
    return max(rows, key=lambda r: r.get("timestamp", ""))


def previous_row(rows):
    if not rows or len(rows) < 2:
        return None
    sorted_rows = sorted(rows, key=lambda r: r.get("timestamp", ""))
    return sorted_rows[-2]


def read_csv_rows(path: Path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def parse_date_from_csv_name(path: Path) -> str:
    # expect name like nifty_YYYYMMDD_HHMMSS.csv
    name = path.stem
    parts = name.split("_")
    if len(parts) >= 3:
        return parts[1]
    return ""


def find_baseline_csv_for_date(date_str: str) -> Path:
    if not AUX_DATA_DIR.exists():
        return None
    candidates = list(AUX_DATA_DIR.glob(f"nifty_{date_str}_*.csv"))
    if not candidates:
        return None
    def extract_time(p: Path):
        name = p.stem
        parts = name.split("_")
        if len(parts) < 3:
            return float("inf")
        hhmmss = parts[2]
        try:
            hh = int(hhmmss[0:2])
            mm = int(hhmmss[2:4])
            secs = int(hhmmss[4:6]) if len(hhmmss) >= 6 else 0
            return hh * 3600 + mm * 60 + secs
        except Exception:
            return float("inf")
    candidates.sort(key=extract_time)
    return candidates[0]


def get_metrics_for_strike(rows, strike: int, side: str):
    # side: 'CE' or 'PE'
    strike_keys = ["CE_strikePrice", "strikePrice"]
    for r in rows:
        s = None
        for k in strike_keys:
            try:
                if r.get(k) is None:
                    continue
                s = int(float(r.get(k)))
                break
            except Exception:
                s = None
        if s is None:
            continue
        if s == strike:
            oi = to_number(r.get(f"{side}_openInterest", "0"))
            last = to_number(r.get(f"{side}_lastPrice", "0"))
            return oi, last
    return 0.0, 0.0


def get_overall_totals(rows):
    if not rows:
        return {
            "Overall_CE_openInterest": 0.0,
            "Overall_PE_openInterest": 0.0,
            "Overall_CE_totalTradedVolume": 0.0,
            "Overall_PE_totalTradedVolume": 0.0,
        }
    first = rows[0]
    return {
        "Overall_CE_openInterest": to_number(first.get("Overall_CE_openInterest", "0")),
        "Overall_PE_openInterest": to_number(first.get("Overall_PE_openInterest", "0")),
        "Overall_CE_totalTradedVolume": to_number(first.get("Overall_CE_totalTradedVolume", "0")),
        "Overall_PE_totalTradedVolume": to_number(first.get("Overall_PE_totalTradedVolume", "0")),
    }


# Small utility helpers used by HTML builder and other functions
def as_int(s):
    try:
        return int(float(s))
    except Exception:
        return None


def to_num(v):
    try:
        return float(str(v).replace(",", ""))
    except Exception:
        return 0.0


def format_list(values):
    return ", ".join(str(v) for v in values) if values else "None"


def format_cog_value(cog):
    return f"{cog:.0f}" if cog is not None else "N/A"


def make_fmt_delta(ce_deltas_start, ce_deltas_prev, pe_deltas_start, pe_deltas_prev):
    def fmt_delta(idx, side, period):
        if side == "CE":
            if period == "start" and ce_deltas_start and idx < len(ce_deltas_start):
                return ce_deltas_start[idx]
            if period == "prev" and ce_deltas_prev and idx < len(ce_deltas_prev):
                return ce_deltas_prev[idx]
        else:
            if period == "start" and pe_deltas_start and idx < len(pe_deltas_start):
                return pe_deltas_start[idx]
            if period == "prev" and pe_deltas_prev and idx < len(pe_deltas_prev):
                return pe_deltas_prev[idx]
        return ""

    return fmt_delta


def format_cog_insight(side, current_cog, previous_cog):
    if current_cog is None or previous_cog is None:
        return "No previous COG available."
    shift = current_cog - previous_cog
    points = abs(round(shift))
    if side == "CE":
        if shift < 0:
            return f"Resistance migrated {points} points lower. CE positioning is shifting downward. Bearish indication."
        if shift > 0:
            return f"Resistance migrated {points} points higher. CE positioning is shifting upward. Bullish indication."
        return "CE COG is unchanged."
    if side == "PE":
        if shift > 0:
            return f"Support is building at higher strikes by {points} points. PE positioning is shifting upward. Bullish indication."
        if shift < 0:
            return f"Support is weakening and moving lower by {points} points. PE positioning is shifting downward. Bearish indication."
        return "PE COG is unchanged."
    return ""


def write_daily_csv(date_str: str, latest, ce_deltas_start, ce_deltas_prev, pe_deltas_start, pe_deltas_prev, overall_deltas_start=None, overall_deltas_prev=None):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"preprocessed_{date_str}.csv"
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
        "CE_delta1_since_start",
        "CE_delta2_since_start",
        "CE_delta3_since_start",
        "CE_delta1_from_previous",
        "CE_delta2_from_previous",
        "CE_delta3_from_previous",
        "PE_delta1_since_start",
        "PE_delta2_since_start",
        "PE_delta3_since_start",
        "PE_delta1_from_previous",
        "PE_delta2_from_previous",
        "PE_delta3_from_previous",
        "Overall_CE_openInterest_delta_since_start",
        "Overall_PE_openInterest_delta_since_start",
        "Overall_CE_totalTradedVolume_delta_since_start",
        "Overall_PE_totalTradedVolume_delta_since_start",
        "Overall_CE_openInterest_delta_from_previous",
        "Overall_PE_openInterest_delta_from_previous",
        "Overall_CE_totalTradedVolume_delta_from_previous",
        "Overall_PE_totalTradedVolume_delta_from_previous",
    ]
    row = {
        "timestamp": latest.get("timestamp", ""),
        "input_csv": latest.get("input_csv", ""),
        "underlyingValue": latest.get("underlyingValue", ""),
        "top1ce_strike": latest.get("top1ce_strike", ""),
        "top1ce_oi_value": latest.get("top1ce_oi_value", ""),
        "top2ce_strike": latest.get("top2ce_strike", ""),
        "top2ce_oi_value": latest.get("top2ce_oi_value", ""),
        "top3ce_strike": latest.get("top3ce_strike", ""),
        "top3ce_oi_value": latest.get("top3ce_oi_value", ""),
        "top1pe_strike": latest.get("top1pe_strike", ""),
        "top1pe_oi_value": latest.get("top1pe_oi_value", ""),
        "top2pe_strike": latest.get("top2pe_strike", ""),
        "top2pe_oi_value": latest.get("top2pe_oi_value", ""),
        "top3pe_strike": latest.get("top3pe_strike", ""),
        "top3pe_oi_value": latest.get("top3pe_oi_value", ""),
        "Overall_CE_openInterest": latest.get("Overall_CE_openInterest", ""),
        "Overall_PE_openInterest": latest.get("Overall_PE_openInterest", ""),
        "Overall_CE_totalTradedVolume": latest.get("Overall_CE_totalTradedVolume", ""),
        "Overall_PE_totalTradedVolume": latest.get("Overall_PE_totalTradedVolume", ""),
        "CE_delta1_since_start": ce_deltas_start[0] if len(ce_deltas_start) > 0 else "",
        "CE_delta2_since_start": ce_deltas_start[1] if len(ce_deltas_start) > 1 else "",
        "CE_delta3_since_start": ce_deltas_start[2] if len(ce_deltas_start) > 2 else "",
        "CE_delta1_from_previous": ce_deltas_prev[0] if len(ce_deltas_prev) > 0 else "",
        "CE_delta2_from_previous": ce_deltas_prev[1] if len(ce_deltas_prev) > 1 else "",
        "CE_delta3_from_previous": ce_deltas_prev[2] if len(ce_deltas_prev) > 2 else "",
        "PE_delta1_since_start": pe_deltas_start[0] if len(pe_deltas_start) > 0 else "",
        "PE_delta2_since_start": pe_deltas_start[1] if len(pe_deltas_start) > 1 else "",
        "PE_delta3_since_start": pe_deltas_start[2] if len(pe_deltas_start) > 2 else "",
        "PE_delta1_from_previous": pe_deltas_prev[0] if len(pe_deltas_prev) > 0 else "",
        "PE_delta2_from_previous": pe_deltas_prev[1] if len(pe_deltas_prev) > 1 else "",
        "PE_delta3_from_previous": pe_deltas_prev[2] if len(pe_deltas_prev) > 2 else "",
        "Overall_CE_openInterest_delta_since_start": overall_deltas_start.get("Overall_CE_openInterest", "") if overall_deltas_start else "",
        "Overall_PE_openInterest_delta_since_start": overall_deltas_start.get("Overall_PE_openInterest", "") if overall_deltas_start else "",
        "Overall_CE_totalTradedVolume_delta_since_start": overall_deltas_start.get("Overall_CE_totalTradedVolume", "") if overall_deltas_start else "",
        "Overall_PE_totalTradedVolume_delta_since_start": overall_deltas_start.get("Overall_PE_totalTradedVolume", "") if overall_deltas_start else "",
        "Overall_CE_openInterest_delta_from_previous": overall_deltas_prev.get("Overall_CE_openInterest", "") if overall_deltas_prev else "",
        "Overall_PE_openInterest_delta_from_previous": overall_deltas_prev.get("Overall_PE_openInterest", "") if overall_deltas_prev else "",
        "Overall_CE_totalTradedVolume_delta_from_previous": overall_deltas_prev.get("Overall_CE_totalTradedVolume", "") if overall_deltas_prev else "",
        "Overall_PE_totalTradedVolume_delta_from_previous": overall_deltas_prev.get("Overall_PE_totalTradedVolume", "") if overall_deltas_prev else "",
    }
    write_header = not out_path.exists()
    with out_path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)
    return out_path




def write_html(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(content)
    return path


def open_in_browser(path: Path, force: bool = False):
    """Open the given HTML file in the default browser, but avoid opening multiple tabs on repeated runs.

    A marker file `.latest_preprocessed_opened` is created in the same folder after the first open.
    Subsequent runs will not open a new tab unless `force=True` or `--force-open` is passed.
    """
    marker = path.parent / ".latest_preprocessed_opened"
    if marker.exists() and not force:
        print(f"Browser already opened for {path}. Use '--force-open' to reopen.")
        return
    try:
        webbrowser.open(path.resolve().as_uri(), new=0, autoraise=False)
        try:
            marker.write_text(datetime.now().isoformat())
        except Exception:
            pass
    except Exception:
        print(f"Unable to open browser automatically. Please open {path} manually.")


def write_snapshot_if_needed(date_str: str, latest: dict, pcr_data: dict, market_sentiment: dict,
                             ce_cog: float, pe_cog: float, ce_list: list, pe_list: list) -> None:
    """Write snapshot files for morning, midday, and close if current time matches window and snapshot not yet written today."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now().time()
    today_str = date_str  # already YYYYMMDD

    def should_write(window_start, window_end):
        return window_start <= now < window_end

    def snapshot_file(name):
        return SNAPSHOT_DIR / f"{name}_{today_str}.json"

    # Morning snapshot
    if should_write(MORNING_WINDOW_START, MORNING_WINDOW_END):
        morning_file = snapshot_file("morning")
        if not morning_file.exists():
            snapshot_data = {
                "timestamp": latest.get("timestamp"),
                "underlyingValue": latest.get("underlyingValue"),
                "pcr": pcr_data.get("pcr"),
                "pcr_label": pcr_data.get("label"),
                "pcr_score": pcr_data.get("score"),
                "market_sentiment_label": market_sentiment.get("label"),
                "market_sentiment_score": market_sentiment.get("score"),
                "ce_cog": ce_cog,
                "pe_cog": pe_cog,
                "top_ce": [{"strike": s, "oi": oi} for s, oi in ce_list],
                "top_pe": [{"strike": s, "oi": oi} for s, oi in pe_list],
            }
            with morning_file.open("w", encoding="utf-8") as f:
                json.dump(snapshot_data, f, indent=2)
            print(f"Wrote morning snapshot: {morning_file}")

    # Midday snapshot
    if should_write(MIDDAY_WINDOW_START, MIDDAY_WINDOW_END):
        midday_file = snapshot_file("midday")
        if not midday_file.exists():
            snapshot_data = {
                "timestamp": latest.get("timestamp"),
                "underlyingValue": latest.get("underlyingValue"),
                "pcr": pcr_data.get("pcr"),
                "pcr_label": pcr_data.get("label"),
                "pcr_score": pcr_data.get("score"),
                "market_sentiment_label": market_sentiment.get("label"),
                "market_sentiment_score": market_sentiment.get("score"),
                "ce_cog": ce_cog,
                "pe_cog": pe_cog,
                "top_ce": [{"strike": s, "oi": oi} for s, oi in ce_list],
                "top_pe": [{"strike": s, "oi": oi} for s, oi in pe_list],
            }
            with midday_file.open("w", encoding="utf-8") as f:
                json.dump(snapshot_data, f, indent=2)
            print(f"Wrote midday snapshot: {midday_file}")

    # Close snapshot
    if should_write(CLOSE_WINDOW_START, CLOSE_WINDOW_END):
        close_file = snapshot_file("close")
        if not close_file.exists():
            snapshot_data = {
                "timestamp": latest.get("timestamp"),
                "underlyingValue": latest.get("underlyingValue"),
                "pcr": pcr_data.get("pcr"),
                "pcr_label": pcr_data.get("label"),
                "pcr_score": pcr_data.get("score"),
                "market_sentiment_label": market_sentiment.get("label"),
                "market_sentiment_score": market_sentiment.get("score"),
                "ce_cog": ce_cog,
                "pe_cog": pe_cog,
                "top_ce": [{"strike": s, "oi": oi} for s, oi in ce_list],
                "top_pe": [{"strike": s, "oi": oi} for s, oi in pe_list],
            }
            with close_file.open("w", encoding="utf-8") as f:
                json.dump(snapshot_data, f, indent=2)
            print(f"Wrote close snapshot: {close_file}")


def load_snapshot(date_str: str, snapshot_type: str) -> dict:
    """Load snapshot JSON file if exists, else return empty dict."""
    file_path = SNAPSHOT_DIR / f"{snapshot_type}_{date_str}.json"
    if file_path.exists():
        try:
            with file_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading snapshot {file_path}: {e}")
            return {}
    return {}


def main():
    rows = read_preprocessed_rows(PREPROCESSED_CSV)
    latest = latest_row(rows)

    # build top3 lists similar to summary
    top3_ce = [
        (latest.get("top1ce_strike", ""), latest.get("top1ce_oi_value", "")),
        (latest.get("top2ce_strike", ""), latest.get("top2ce_oi_value", "")),
        (latest.get("top3ce_strike", ""), latest.get("top3ce_oi_value", "")),
    ]
    top3_pe = [
        (latest.get("top1pe_strike", ""), latest.get("top1pe_oi_value", "")),
        (latest.get("top2pe_strike", ""), latest.get("top2pe_oi_value", "")),
        (latest.get("top3pe_strike", ""), latest.get("top3pe_oi_value", "")),
    ]

    def as_int(s):
        try:
            return int(float(s))
        except Exception:
            return None

    ce_list = [item for item in top3_ce if as_int(item[0]) is not None]
    pe_list = [item for item in top3_pe if as_int(item[0]) is not None]
    ce_list.sort(key=lambda x: as_int(x[0]))
    pe_list.sort(key=lambda x: as_int(x[0]), reverse=True)

    # Market structure: compute via metrics.compute_market_structure
    try:
        today_underlying = to_number(latest.get("underlyingValue", 0))
    except Exception:
        today_underlying = None

    ms = compute_market_structure(ce_list, pe_list, today_underlying)
    immediate_resistance = ms.get("immediate_resistance", "N/A")
    major_resistance = ms.get("major_resistance", "N/A")
    immediate_support = ms.get("immediate_support", "N/A")
    major_support = ms.get("major_support", "N/A")

    # determine current csv path
    input_csv = latest.get("input_csv", "")
    curr_csv_path = Path(input_csv) if input_csv else None
    if not curr_csv_path or not curr_csv_path.exists():
        # fallback to latest in AUX_DATA_DIR
        files = list(AUX_DATA_DIR.glob("*.csv"))
        if files:
            curr_csv_path = max(files, key=lambda p: p.stat().st_mtime)

    # baseline is the first available raw sheet for the current day
    date_str = parse_date_from_csv_name(curr_csv_path) if curr_csv_path else datetime.now().strftime("%Y%m%d")
    baseline_path = find_baseline_csv_for_date(date_str)
    morning_snapshot = load_snapshot(date_str, "morning")
    midday_snapshot = load_snapshot(date_str, "midday")
    close_snapshot = load_snapshot(date_str, "close")

    current_rows = read_csv_rows(curr_csv_path) if curr_csv_path else []
    baseline_rows = read_csv_rows(baseline_path) if baseline_path else []

    previous = previous_row(rows)
    previous_csv_path = None
    if previous and previous.get("input_csv"):
        candidate = Path(previous["input_csv"])
        if candidate.exists():
            previous_csv_path = candidate
    previous_rows = read_csv_rows(previous_csv_path) if previous_csv_path else []

    previous_top3_ce = []
    previous_top3_pe = []
    if previous:
        previous_top3_ce = [
            (previous.get("top1ce_strike", ""), previous.get("top1ce_oi_value", "")),
            (previous.get("top2ce_strike", ""), previous.get("top2ce_oi_value", "")),
            (previous.get("top3ce_strike", ""), previous.get("top3ce_oi_value", "")),
        ]
        previous_top3_pe = [
            (previous.get("top1pe_strike", ""), previous.get("top1pe_oi_value", "")),
            (previous.get("top2pe_strike", ""), previous.get("top2pe_oi_value", "")),
            (previous.get("top3pe_strike", ""), previous.get("top3pe_oi_value", "")),
        ]

    # compute delta strings for CE and PE
    ce_deltas_start = []
    ce_deltas_prev = []
    for strike_s, oi_s in ce_list:
        strike = as_int(strike_s)
        curr_oi, _ = get_metrics_for_strike(current_rows, strike, "CE")
        base_oi, _ = get_metrics_for_strike(baseline_rows, strike, "CE") if baseline_rows else (0.0, 0.0)
        prev_oi, _ = get_metrics_for_strike(previous_rows, strike, "CE") if previous_rows else (0.0, 0.0)
        ce_deltas_start.append(f"{(curr_oi - base_oi):+.0f}")
        ce_deltas_prev.append(f"{(curr_oi - prev_oi):+.0f}")

    pe_deltas_start = []
    pe_deltas_prev = []
    for strike_s, oi_s in pe_list:
        strike = as_int(strike_s)
        curr_oi, _ = get_metrics_for_strike(current_rows, strike, "PE")
        base_oi, _ = get_metrics_for_strike(baseline_rows, strike, "PE") if baseline_rows else (0.0, 0.0)
        prev_oi, _ = get_metrics_for_strike(previous_rows, strike, "PE") if previous_rows else (0.0, 0.0)
        pe_deltas_start.append(f"{(curr_oi - base_oi):+.0f}")
        pe_deltas_prev.append(f"{(curr_oi - prev_oi):+.0f}")

    overall_current = get_overall_totals(current_rows)
    overall_baseline = get_overall_totals(baseline_rows)
    overall_previous = get_overall_totals(previous_rows)
    overall_deltas_start = {
        key: f"{(overall_current.get(key, 0.0) - overall_baseline.get(key, 0.0)):+.0f}"
        for key in [
            "Overall_CE_openInterest",
            "Overall_PE_openInterest",
            "Overall_CE_totalTradedVolume",
            "Overall_PE_totalTradedVolume",
        ]
    }
    overall_deltas_prev = {
        key: f"{(overall_current.get(key, 0.0) - overall_previous.get(key, 0.0)):+.0f}"
        for key in [
            "Overall_CE_openInterest",
            "Overall_PE_openInterest",
            "Overall_CE_totalTradedVolume",
            "Overall_PE_totalTradedVolume",
        ]
    }

    ce_migration = analyze_migration(
        [strike for strike, _ in previous_top3_ce],
        [strike for strike, _ in ce_list],
    )
    pe_migration = analyze_migration(
        [strike for strike, _ in previous_top3_pe],
        [strike for strike, _ in pe_list],
    )
    pcr_data = calculate_pcr(
        overall_current.get("Overall_PE_openInterest", 0.0),
        overall_current.get("Overall_CE_openInterest", 0.0),
    )
    ce_cog = calculate_cog([strike for strike, _ in ce_list], [oi for _, oi in ce_list])["cog"]
    prev_ce_cog = calculate_cog(
        [strike for strike, _ in previous_top3_ce],
        [oi for _, oi in previous_top3_ce],
    )["cog"]
    pe_cog = calculate_cog([strike for strike, _ in pe_list], [oi for _, oi in pe_list])["cog"]
    prev_pe_cog = calculate_cog(
        [strike for strike, _ in previous_top3_pe],
        [oi for _, oi in previous_top3_pe],
    )["cog"]

    ce_cog_data = {
        "current": ce_cog,
        "previous": prev_ce_cog,
        **calculate_cog_shift(ce_cog, prev_ce_cog),
    }
    pe_cog_data = {
        "current": pe_cog,
        "previous": prev_pe_cog,
        **calculate_cog_shift(pe_cog, prev_pe_cog),
    }
    # Get current, previous and start (baseline) underlying values for price change calculation
    current_underlying = to_number(latest.get("underlyingValue", "0"))
    previous_underlying = to_number(previous.get("underlyingValue", "0")) if previous else 0.0
    baseline_underlying = 0.0
    if baseline_rows:
        try:
            baseline_underlying = to_number(baseline_rows[0].get("underlyingValue", "0"))
        except Exception:
            baseline_underlying = 0.0

    # Calculate both variants: change from previous iteration and change from day-start (baseline)
    price_change_prev = calculate_price_change(current_underlying, previous_underlying)
    price_change_start = calculate_price_change(current_underlying, baseline_underlying)
    # Use start-based change for display (but we keep both available)
    price_change_data = price_change_start

    ce_oi_change = overall_current.get("Overall_CE_openInterest", 0.0) - overall_previous.get("Overall_CE_openInterest", 0.0)
    pe_oi_change = overall_current.get("Overall_PE_openInterest", 0.0) - overall_previous.get("Overall_PE_openInterest", 0.0)
    market_sentiment = calculate_market_sentiment(
        ce_cog_data,
        pe_cog_data,
        ce_migration,
        pe_migration,
        pcr_data,
        ce_oi_change,
        pe_oi_change,
    )
    prev_ce_cog = calculate_cog(
        [strike for strike, _ in previous_top3_ce],
        [oi for _, oi in previous_top3_ce],
    )["cog"]
    pe_cog = calculate_cog([strike for strike, _ in pe_list], [oi for _, oi in pe_list])["cog"]
    prev_pe_cog = calculate_cog(
        [strike for strike, _ in previous_top3_pe],
        [oi for _, oi in previous_top3_pe],
    )["cog"]

    # Write snapshots if time matches windows
    write_snapshot_if_needed(date_str, latest, pcr_data, market_sentiment, ce_cog, pe_cog, ce_list, pe_list)

    # Generate session snapshots for the day
    try:
        from session_snap import create_session_snapshots, get_todays_date_str
        snapshot_date = get_todays_date_str()
        session_snapshots = create_session_snapshots(rows, snapshot_date)
        
        # Render session snapshot HTML
        from session_snapshot_renderer import render_session_snapshot_html, write_html as write_snapshot_html
        snapshot_html = render_session_snapshot_html(session_snapshots)
        snapshot_output_path = SNAPSHOT_DIR / f"session_snapshot_{snapshot_date}.html"
        write_snapshot_html(snapshot_output_path, snapshot_html)
        print(f"Wrote session snapshot HTML: {snapshot_output_path}")
    except Exception as e:
        print(f"Warning: Could not generate session snapshot: {e}")
        snapshot_date = datetime.now().strftime("%Y%m%d")

    # render HTML with deltas using the template renderer (presentation separated)
    from latest_preprocessed_renderer import render_html

    ce_max_oi = max((to_num(x[1]) for x in ce_list), default=0)
    pe_max_oi = max((to_num(x[1]) for x in pe_list), default=0)
    fmt_delta = make_fmt_delta(ce_deltas_start, ce_deltas_prev, pe_deltas_start, pe_deltas_prev)

    html = render_html(
        latest,
        ce_list,
        pe_list,
        ce_max_oi,
        pe_max_oi,
        fmt_delta,
        ce_migration,
        pe_migration,
        ce_cog,
        prev_ce_cog,
        pe_cog,
        prev_pe_cog,
        overall_deltas_start,
        overall_deltas_prev,
        pcr_data,
        market_sentiment,
        price_change_data,
        morning_snapshot,
        midday_snapshot,
        close_snapshot,
        auto_refresh_seconds=AUTO_REFRESH_SECONDS,
        snapshot_date=snapshot_date,
        immediate_resistance=immediate_resistance,
        major_resistance=major_resistance,
        immediate_support=immediate_support,
        major_support=major_support,
    )
    output_path = write_html(OUTPUT_HTML, html)
    print(f"Wrote latest preprocessed HTML: {output_path}")

    # write a daily CSV file named by date
    csv_out = write_daily_csv(
        date_str,
        latest,
        ce_deltas_start,
        ce_deltas_prev,
        pe_deltas_start,
        pe_deltas_prev,
        overall_deltas_start=overall_deltas_start,
        overall_deltas_prev=overall_deltas_prev,
    )
    if csv_out:
        print(f"Wrote daily CSV: {csv_out}")

    force_open = "--force-open" in sys.argv
    if len(sys.argv) == 1 or "--open" in sys.argv:
        open_in_browser(output_path, force=force_open)
    else:
        print("Run with '--open' to open automatically in your browser.")


if __name__ == "__main__":
    main()
