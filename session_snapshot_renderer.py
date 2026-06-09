import json
from pathlib import Path
from datetime import datetime

TEMPLATE_PATH = Path("templates/session_snapshot_template.html")


def format_number(value):
    """Format a number value for display."""
    try:
        num = float(str(value).replace(",", ""))
        if num >= 1_000_000:
            return f"{num/1_000_000:.2f}M"
        elif num >= 1_000:
            return f"{num/1_000:.1f}K"
        else:
            return f"{num:.0f}"
    except Exception:
        return str(value)


def format_full_number(value):
    """Return full integer representation without K/M shortening."""
    try:
        num = float(str(value).replace(",", ""))
        # If it's effectively integer, show without decimals
        if abs(num - round(num)) < 1e-6:
            return str(int(round(num)))
        return str(int(round(num)))
    except Exception:
        return str(value)


def extract_timestamp_time(timestamp_str):
    """Extract just the time portion from ISO timestamp."""
    try:
        dt = datetime.fromisoformat(timestamp_str)
        return dt.strftime("%H:%M:%S")
    except Exception:
        return ""


def render_session_snapshot_html(snapshots_data: dict) -> str:
    """Render the session snapshot HTML from template and snapshot data."""
    tpl = TEMPLATE_PATH.read_text(encoding="utf-8")
    
    # Extract snapshots for each session
    morning = snapshots_data.get("morning", {})
    midday = snapshots_data.get("midday", {})
    evening = snapshots_data.get("evening", {})
    
    # Build replacement mapping
    mapping = {
        # Morning session
        "morning_timestamp": extract_timestamp_time(morning.get("timestamp", "")),
        "morning_underlying": format_full_number(morning.get("underlyingValue", "N/A")),
        "morning_ce1_strike": str(morning.get("top1ce_strike", "N/A")),
        "morning_ce1_oi": format_full_number(morning.get("top1ce_oi", "N/A")),
        "morning_ce2_strike": str(morning.get("top2ce_strike", "N/A")),
        "morning_ce2_oi": format_full_number(morning.get("top2ce_oi", "N/A")),
        "morning_ce3_strike": str(morning.get("top3ce_strike", "N/A")),
        "morning_ce3_oi": format_full_number(morning.get("top3ce_oi", "N/A")),
        "morning_pe1_strike": str(morning.get("top1pe_strike", "N/A")),
        "morning_pe1_oi": format_full_number(morning.get("top1pe_oi", "N/A")),
        "morning_pe2_strike": str(morning.get("top2pe_strike", "N/A")),
        "morning_pe2_oi": format_full_number(morning.get("top2pe_oi", "N/A")),
        "morning_pe3_strike": str(morning.get("top3pe_strike", "N/A")),
        "morning_pe3_oi": format_full_number(morning.get("top3pe_oi", "N/A")),
        "morning_pcr": str(morning.get("pcr", "N/A")),
        "morning_ce_oi": format_full_number(morning.get("overall_ce_oi", "N/A")),
        "morning_ce_volume": format_full_number(morning.get("overall_ce_volume", "N/A")),
        "morning_pe_oi": format_full_number(morning.get("overall_pe_oi", "N/A")),
        "morning_pe_volume": format_full_number(morning.get("overall_pe_volume", "N/A")),
        
        # Midday session
        "midday_timestamp": extract_timestamp_time(midday.get("timestamp", "")),
        "midday_underlying": format_full_number(midday.get("underlyingValue", "N/A")),
        "midday_ce1_strike": str(midday.get("top1ce_strike", "N/A")),
        "midday_ce1_oi": format_full_number(midday.get("top1ce_oi", "N/A")),
        "midday_ce2_strike": str(midday.get("top2ce_strike", "N/A")),
        "midday_ce2_oi": format_full_number(midday.get("top2ce_oi", "N/A")),
        "midday_ce3_strike": str(midday.get("top3ce_strike", "N/A")),
        "midday_ce3_oi": format_full_number(midday.get("top3ce_oi", "N/A")),
        "midday_pe1_strike": str(midday.get("top1pe_strike", "N/A")),
        "midday_pe1_oi": format_full_number(midday.get("top1pe_oi", "N/A")),
        "midday_pe2_strike": str(midday.get("top2pe_strike", "N/A")),
        "midday_pe2_oi": format_full_number(midday.get("top2pe_oi", "N/A")),
        "midday_pe3_strike": str(midday.get("top3pe_strike", "N/A")),
        "midday_pe3_oi": format_full_number(midday.get("top3pe_oi", "N/A")),
        "midday_pcr": str(midday.get("pcr", "N/A")),
        "midday_ce_oi": format_full_number(midday.get("overall_ce_oi", "N/A")),
        "midday_ce_volume": format_full_number(midday.get("overall_ce_volume", "N/A")),
        "midday_pe_oi": format_full_number(midday.get("overall_pe_oi", "N/A")),
        "midday_pe_volume": format_full_number(midday.get("overall_pe_volume", "N/A")),
        
        # Evening session
        "evening_timestamp": extract_timestamp_time(evening.get("timestamp", "")),
        "evening_underlying": format_full_number(evening.get("underlyingValue", "N/A")),
        "evening_ce1_strike": str(evening.get("top1ce_strike", "N/A")),
        "evening_ce1_oi": format_full_number(evening.get("top1ce_oi", "N/A")),
        "evening_ce2_strike": str(evening.get("top2ce_strike", "N/A")),
        "evening_ce2_oi": format_full_number(evening.get("top2ce_oi", "N/A")),
        "evening_ce3_strike": str(evening.get("top3ce_strike", "N/A")),
        "evening_ce3_oi": format_full_number(evening.get("top3ce_oi", "N/A")),
        "evening_pe1_strike": str(evening.get("top1pe_strike", "N/A")),
        "evening_pe1_oi": format_full_number(evening.get("top1pe_oi", "N/A")),
        "evening_pe2_strike": str(evening.get("top2pe_strike", "N/A")),
        "evening_pe2_oi": format_full_number(evening.get("top2pe_oi", "N/A")),
        "evening_pe3_strike": str(evening.get("top3pe_strike", "N/A")),
        "evening_pe3_oi": format_full_number(evening.get("top3pe_oi", "N/A")),
        "evening_pcr": str(evening.get("pcr", "N/A")),
        "evening_ce_oi": format_full_number(evening.get("overall_ce_oi", "N/A")),
        "evening_ce_volume": format_full_number(evening.get("overall_ce_volume", "N/A")),
        "evening_pe_oi": format_full_number(evening.get("overall_pe_oi", "N/A")),
        "evening_pe_volume": format_full_number(evening.get("overall_pe_volume", "N/A")),
        
        # Metadata
        "generated_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    
    # Replace all placeholders
    html = tpl
    for key, value in mapping.items():
        placeholder = "{{" + key + "}}"
        html = html.replace(placeholder, str(value))
    
    return html


def write_html(path: Path, content: str) -> Path:
    """Write HTML content to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(content)
    return path


def main():
    """Test the renderer with sample data."""
    sample_data = {
        "morning": {
            "timestamp": "2026-06-05T09:21:17.000000",
            "underlyingValue": "23500.2",
            "top1ce_strike": "24000",
            "top1ce_oi": "179205",
            "top2ce_strike": "23500",
            "top2ce_oi": "106943",
            "top3ce_strike": "23800",
            "top3ce_oi": "86669",
            "top1pe_strike": "23000",
            "top1pe_oi": "122993",
            "top2pe_strike": "23300",
            "top2pe_oi": "117679",
            "top3pe_strike": "23400",
            "top3pe_oi": "83373",
            "pcr": "0.96",
            "overall_ce_oi": "2086361.0",
            "overall_ce_volume": "25055683.0",
            "overall_pe_oi": "2010733.0",
            "overall_pe_volume": "23882531.0",
        },
        "midday": {
            "timestamp": "2026-06-05T12:30:30.000000",
            "underlyingValue": "23450.5",
            "top1ce_strike": "23500",
            "top1ce_oi": "250000",
            "top2ce_strike": "23800",
            "top2ce_oi": "180000",
            "top3ce_strike": "24000",
            "top3ce_oi": "150000",
            "top1pe_strike": "23000",
            "top1pe_oi": "200000",
            "top2pe_strike": "23300",
            "top2pe_oi": "180000",
            "top3pe_strike": "23400",
            "top3pe_oi": "150000",
            "pcr": "1.02",
            "overall_ce_oi": "3500000.0",
            "overall_ce_volume": "50000000.0",
            "overall_pe_oi": "3600000.0",
            "overall_pe_volume": "52000000.0",
        },
        "evening": {
            "timestamp": "2026-06-05T15:00:45.000000",
            "underlyingValue": "23480.8",
            "top1ce_strike": "23500",
            "top1ce_oi": "220000",
            "top2ce_strike": "23700",
            "top2ce_oi": "190000",
            "top3ce_strike": "23800",
            "top3ce_oi": "160000",
            "top1pe_strike": "23000",
            "top1pe_oi": "210000",
            "top2pe_strike": "23200",
            "top2pe_oi": "190000",
            "top3pe_strike": "23300",
            "top3pe_oi": "170000",
            "pcr": "0.98",
            "overall_ce_oi": "4000000.0",
            "overall_ce_volume": "70000000.0",
            "overall_pe_oi": "3900000.0",
            "overall_pe_volume": "68000000.0",
        },
    }
    
    html = render_session_snapshot_html(sample_data)
    output_path = write_html(Path("snapshot_output/session_snapshot_20260605.html"), html)
    print(f"Rendered HTML to: {output_path}")


if __name__ == "__main__":
    main()
