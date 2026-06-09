import csv
import json
import sys
from pathlib import Path

INPUT_DIR = Path("nifty_data")
OUTPUT_DIR = Path("nifty_data_csv")
OUTPUT_DIR.mkdir(exist_ok=True)


def load_json_data(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "records" in data and isinstance(data["records"], dict):
        data = data["records"].get("data", [])
    elif isinstance(data, dict) and "data" in data:
        data = data["data"]

    if not isinstance(data, list):
        raise ValueError(f"Unexpected JSON format in {path}")

    return data


# Requested per-strike columns
COLUMNS = [
    "CE_change",
    "CE_changeinOpenInterest",
    "CE_pChange",
    "CE_pchangeinOpenInterest",
    "CE_impliedVolatility",
    "CE_lastPrice",
    "CE_openInterest",
    "CE_totalBuyQuantity",
    "CE_totalSellQuantity",
    "CE_strikePrice",
    "CE_totalTradedVolume",
    "underlyingValue",
    "PE_change",
    "PE_changeinOpenInterest",
    "PE_pChange",
    "PE_pchangeinOpenInterest",
    "PE_impliedVolatility",
    "PE_lastPrice",
    "PE_openInterest",
    "PE_totalBuyQuantity",
    "PE_totalSellQuantity",
    "PE_totalTradedVolume",
    # Overall totals (same value repeated on every row for the file)
    "Overall_CE_openInterest",
    "Overall_CE_totalTradedVolume",
    "Overall_PE_openInterest",
    "Overall_PE_totalTradedVolume",
]


def safe_num(v):
    try:
        if v is None or v == "":
            return 0
        return float(v)
    except Exception:
        return 0


def extract_columns_from_record(rec, totals):
    ce = rec.get("CE") or {}
    pe = rec.get("PE") or {}

    out = {
        "CE_change": ce.get("change", ""),
        "CE_changeinOpenInterest": ce.get("changeinOpenInterest", ""),
        "CE_pChange": ce.get("pChange", ce.get("PChange", "")),
        "CE_pchangeinOpenInterest": ce.get("pchangeinOpenInterest", ""),
        "CE_impliedVolatility": ce.get("impliedVolatility", ""),
        "CE_lastPrice": ce.get("lastPrice", ""),
        "CE_openInterest": ce.get("openInterest", ""),
        "CE_totalBuyQuantity": ce.get("totalBuyQuantity", ""),
        "CE_totalSellQuantity": ce.get("totalSellQuantity", ""),
        "CE_strikePrice": ce.get("strikePrice") or rec.get("strikePrice", ""),
        "CE_totalTradedVolume": ce.get("totalTradedVolume", ""),
        "underlyingValue": ce.get("underlyingValue") or pe.get("underlyingValue") or rec.get("underlyingValue", ""),
        "PE_change": pe.get("change", ""),
        "PE_changeinOpenInterest": pe.get("changeinOpenInterest", ""),
        "PE_pChange": pe.get("pChange", pe.get("PChange", "")),
        "PE_pchangeinOpenInterest": pe.get("pchangeinOpenInterest", ""),
        "PE_impliedVolatility": pe.get("impliedVolatility", ""),
        "PE_lastPrice": pe.get("lastPrice", ""),
        "PE_openInterest": pe.get("openInterest", ""),
        "PE_totalBuyQuantity": pe.get("totalBuyQuantity", ""),
        "PE_totalSellQuantity": pe.get("totalSellQuantity", ""),
        "PE_totalTradedVolume": pe.get("totalTradedVolume", ""),
        "Overall_CE_openInterest": totals.get("ce_oi", 0),
        "Overall_CE_totalTradedVolume": totals.get("ce_vol", 0),
        "Overall_PE_openInterest": totals.get("pe_oi", 0),
        "Overall_PE_totalTradedVolume": totals.get("pe_vol", 0),
    }

    return out


def compute_totals(rows):
    ce_oi = 0.0
    ce_vol = 0.0
    pe_oi = 0.0
    pe_vol = 0.0

    for rec in rows:
        ce = rec.get("CE") or {}
        pe = rec.get("PE") or {}
        ce_oi += safe_num(ce.get("openInterest"))
        ce_vol += safe_num(ce.get("totalTradedVolume"))
        pe_oi += safe_num(pe.get("openInterest"))
        pe_vol += safe_num(pe.get("totalTradedVolume"))

    # Use integers when values are whole numbers
    def maybe_int(x):
        if abs(x - int(x)) < 1e-9:
            return int(x)
        return x

    return {
        "ce_oi": maybe_int(ce_oi),
        "ce_vol": maybe_int(ce_vol),
        "pe_oi": maybe_int(pe_oi),
        "pe_vol": maybe_int(pe_vol),
    }


def convert_file(json_path):
    rows = load_json_data(json_path)
    if not rows:
        print(f"Skipping empty file: {json_path}")
        return

    totals = compute_totals(rows)

    csv_path = OUTPUT_DIR / (json_path.stem + ".csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for rec in rows:
            writer.writerow(extract_columns_from_record(rec, totals))

    print(f"Converted {json_path.name} -> {csv_path}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args:
        json_paths = [Path(arg) for arg in args]
    else:
        json_paths = sorted(INPUT_DIR.glob("*.json"))

    if not json_paths:
        raise SystemExit(f"No JSON files found to convert")

    for json_path in json_paths:
        if not json_path.exists():
            print(f"JSON file not found: {json_path}")
            continue
        try:
            convert_file(json_path)
        except Exception as exc:
            print(f"Error converting {json_path.name}: {exc}")
