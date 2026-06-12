import csv
import json
import sys
from datetime import datetime, time as dtime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

PREPROCESSED_CSV = Path("preprocessed_output/preprocessed.csv")
PREPROCESSED_DIR = Path("preprocessed_output")
SNAPSHOT_DIR = Path("snapshot_output")

# Snapshot windows (inclusive start, exclusive end)
MORNING_WINDOW_START = dtime(9, 21)
MORNING_WINDOW_END = dtime(9, 22)
MIDDAY_WINDOW_START = dtime(12, 30)
MIDDAY_WINDOW_END = dtime(12, 45)
EVENING_WINDOW_START = dtime(15, 0)
EVENING_WINDOW_END = dtime(15, 30)


def to_number(s: Any) -> float:
    """Convert value to float safely."""
    try:
        return float(str(s).replace(",", ""))
    except Exception:
        return 0.0


def read_preprocessed_rows(csv_path: Path) -> List[Dict]:
    """Read all rows from preprocessed CSV."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Preprocessed CSV not found: {csv_path}")
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def extract_time_from_timestamp(timestamp_str: str) -> Optional[dtime]:
    """Extract time component from ISO timestamp string."""
    try:
        dt = datetime.fromisoformat(timestamp_str)
        return dt.time()
    except Exception:
        return None


def find_rows_in_window(rows: List[Dict], window_start: dtime, window_end: dtime) -> Optional[Dict]:
    """Find rows within a time window and return the closest one."""
    matching_rows = []
    for row in rows:
        timestamp = row.get("timestamp", "")
        row_time = extract_time_from_timestamp(timestamp)
        if row_time and window_start <= row_time < window_end:
            matching_rows.append(row)
    
    if not matching_rows:
        return None
    
    # Return the last row in the window (most recent)
    return matching_rows[-1]


def calculate_pcr(pe_oi: float, ce_oi: float) -> float:
    """Calculate Put-Call Ratio."""
    if ce_oi == 0:
        return 0.0
    return pe_oi / ce_oi


def extract_session_snapshot(row: Optional[Dict]) -> Dict[str, Any]:
    """Extract session snapshot from a preprocessed row."""
    if not row:
        return {
            "timestamp": "N/A",
            "underlyingValue": "N/A",
            "top1ce_strike": "N/A",
            "top1ce_oi": "N/A",
            "top2ce_strike": "N/A",
            "top2ce_oi": "N/A",
            "top3ce_strike": "N/A",
            "top3ce_oi": "N/A",
            "top1pe_strike": "N/A",
            "top1pe_oi": "N/A",
            "top2pe_strike": "N/A",
            "top2pe_oi": "N/A",
            "top3pe_strike": "N/A",
            "top3pe_oi": "N/A",
            "pcr": "N/A",
            "overall_ce_oi": "N/A",
            "overall_pe_oi": "N/A",
            "overall_ce_volume": "N/A",
            "overall_pe_volume": "N/A",
        }
    
    ce_oi = to_number(row.get("Overall_CE_openInterest", "0"))
    pe_oi = to_number(row.get("Overall_PE_openInterest", "0"))
    
    snapshot = {
        "timestamp": row.get("timestamp", "N/A"),
        "underlyingValue": row.get("underlyingValue", "N/A"),
        "top1ce_strike": row.get("top1ce_strike", "N/A"),
        "top1ce_oi": row.get("top1ce_oi_value", "N/A"),
        "top2ce_strike": row.get("top2ce_strike", "N/A"),
        "top2ce_oi": row.get("top2ce_oi_value", "N/A"),
        "top3ce_strike": row.get("top3ce_strike", "N/A"),
        "top3ce_oi": row.get("top3ce_oi_value", "N/A"),
        "top1pe_strike": row.get("top1pe_strike", "N/A"),
        "top1pe_oi": row.get("top1pe_oi_value", "N/A"),
        "top2pe_strike": row.get("top2pe_strike", "N/A"),
        "top2pe_oi": row.get("top2pe_oi_value", "N/A"),
        "top3pe_strike": row.get("top3pe_strike", "N/A"),
        "top3pe_oi": row.get("top3pe_oi_value", "N/A"),
        "pcr": f"{calculate_pcr(pe_oi, ce_oi):.2f}",
        "overall_ce_oi": row.get("Overall_CE_openInterest", "N/A"),
        "overall_pe_oi": row.get("Overall_PE_openInterest", "N/A"),
        "overall_ce_volume": row.get("Overall_CE_totalTradedVolume", "N/A"),
        "overall_pe_volume": row.get("Overall_PE_totalTradedVolume", "N/A"),
    }
    
    return snapshot


def create_session_snapshots(rows: List[Dict], date_str: str) -> Dict[str, Dict[str, Any]]:
    """Create session snapshots for morning, midday, and evening."""
    snapshots = {}
    
    # Find rows in each window
    morning_row = find_rows_in_window(rows, MORNING_WINDOW_START, MORNING_WINDOW_END)
    midday_row = find_rows_in_window(rows, MIDDAY_WINDOW_START, MIDDAY_WINDOW_END)
    evening_row = find_rows_in_window(rows, EVENING_WINDOW_START, EVENING_WINDOW_END)
    
    snapshots["morning"] = extract_session_snapshot(morning_row)
    snapshots["midday"] = extract_session_snapshot(midday_row)
    snapshots["evening"] = extract_session_snapshot(evening_row)
    
    return snapshots


def save_session_snapshots(snapshots: Dict[str, Dict[str, Any]], date_str: str) -> Path:
    """Save session snapshots to JSON file with date-based filename."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    
    file_path = SNAPSHOT_DIR / f"session_snapshot_{date_str}.json"
    
    with file_path.open("w", encoding="utf-8") as f:
        json.dump(snapshots, f, indent=2)
    
    return file_path


def get_todays_date_str() -> str:
    """Get today's date in YYYYMMDD format."""
    return datetime.now().strftime("%Y%m%d")


def main():
    """Main function to create and save session snapshots."""
    try:
        # select the latest preprocessed CSV: prefer newest preprocessed_*.csv, else fallback to preprocessed.csv
        csv_files = list(PREPROCESSED_DIR.glob("preprocessed_*.csv"))
        if csv_files:
            csv_path = max(csv_files, key=lambda p: p.stat().st_mtime)
        elif PREPROCESSED_CSV.exists() and PREPROCESSED_CSV.is_file():
            csv_path = PREPROCESSED_CSV
        else:
            raise FileNotFoundError(f"No preprocessed CSV found in {PREPROCESSED_DIR}")

        rows = read_preprocessed_rows(csv_path)
        date_str = get_todays_date_str()
        
        print(f"Processing {len(rows)} rows from {csv_path}")
        
        snapshots = create_session_snapshots(rows, date_str)
        
        file_path = save_session_snapshots(snapshots, date_str)
        print(f"Session snapshots saved to: {file_path}")
        
        # Print summary
        for session_name, snapshot in snapshots.items():
            print(f"\n{session_name.upper()} Snapshot:")
            print(f"  Timestamp: {snapshot['timestamp']}")
            print(f"  Underlying: {snapshot['underlyingValue']}")
            print(f"  PCR: {snapshot['pcr']}")
        
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
