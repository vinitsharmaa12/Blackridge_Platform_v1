from pathlib import Path
from typing import List, Tuple
from datetime import datetime

TEMPLATE_PATH = Path("templates/latest_preprocessed_template.html")


def _to_num(v):
    try:
        return float(str(v).replace(",", ""))
    except Exception:
        return 0.0


def _format_list(values):
    return ", ".join(str(v) for v in values) if values else "None"


def _format_cog_value(cog):
    return f"{cog:.0f}" if cog is not None else "N/A"


def _format_cog_insight(side, current_cog, previous_cog):
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


def _build_rows(list_items: List[Tuple[str, str]], max_oi: float, fmt_delta_func, side: str) -> str:
    rows = []
    for i, (strike, oi) in enumerate(list_items):
        highlight = "#dff0d8" if _to_num(oi) == max_oi and side == "CE" else ("#f2dede" if _to_num(oi) == max_oi and side == "PE" else "")
        row = f'<tr style="background:{highlight}"><td>{i + 1}</td><td>{strike}</td><td>{oi}</td><td>{fmt_delta_func(i, side, "start")}</td><td>{fmt_delta_func(i, side, "prev")}</td></tr>'
        rows.append(row)
    return "\n".join(rows)


def render_html(latest: dict, ce_list, pe_list, ce_max_oi, pe_max_oi, fmt_delta_func, ce_migration, pe_migration, ce_cog, prev_ce_cog, pe_cog, prev_pe_cog, overall_deltas_start, overall_deltas_prev, pcr_data, market_sentiment, price_change_data, morning_snapshot, midday_snapshot, close_snapshot, auto_refresh_seconds=30, snapshot_date=None, immediate_resistance="", major_resistance="", immediate_support="", major_support="") -> str:
    tpl = TEMPLATE_PATH.read_text(encoding="utf-8")

    ce_rows = _build_rows(ce_list, ce_max_oi, fmt_delta_func, "CE")
    pe_rows = _build_rows(pe_list, pe_max_oi, fmt_delta_func, "PE")

    mapping = {
        "AUTO_REFRESH_SECONDS": str(auto_refresh_seconds),
        "timestamp": latest.get("timestamp", ""),
        "input_csv": latest.get("input_csv", ""),
        "underlyingValue": latest.get("underlyingValue", ""),
        "ce_rows": ce_rows,
        "pe_rows": pe_rows,
        "ce_arrow": ce_migration.get("arrow", ""),
        "ce_direction": ce_migration.get("direction", ""),
        "ce_added": _format_list(ce_migration.get("added", [])),
        "ce_removed": _format_list(ce_migration.get("removed", [])),
        "ce_common": _format_list(ce_migration.get("common", [])),
        "ce_cog": _format_cog_value(ce_cog),
        "prev_ce_cog": _format_cog_value(prev_ce_cog),
        "ce_cog_delta": f"{(ce_cog - prev_ce_cog):+.0f}" if ce_cog is not None and prev_ce_cog is not None else "N/A",
        "ce_cog_comment": _format_cog_insight("CE", ce_cog, prev_ce_cog),
        "pe_arrow": pe_migration.get("arrow", ""),
        "pe_direction": pe_migration.get("direction", ""),
        "pe_added": _format_list(pe_migration.get("added", [])),
        "pe_removed": _format_list(pe_migration.get("removed", [])),
        "pe_common": _format_list(pe_migration.get("common", [])),
        "pe_cog": _format_cog_value(pe_cog),
        "prev_pe_cog": _format_cog_value(prev_pe_cog),
        "pe_cog_delta": f"{(pe_cog - prev_pe_cog):+.0f}" if pe_cog is not None and prev_pe_cog is not None else "N/A",
        "pe_cog_comment": _format_cog_insight("PE", pe_cog, prev_pe_cog),
        # price change
        "price_change": f"{price_change_data.get('change', 0):+.0f}" if price_change_data.get('change') is not None else "N/A",
        "price_direction": price_change_data.get("direction", "flat"),
        "price_points": price_change_data.get("points", 0),
        "price_comment": price_change_data.get("comment", "No price change data available."),
        # overall metrics
        "Overall_CE_openInterest": latest.get("Overall_CE_openInterest", ""),
        "Overall_PE_openInterest": latest.get("Overall_PE_openInterest", ""),
        "Overall_CE_totalTradedVolume": latest.get("Overall_CE_totalTradedVolume", ""),
        "Overall_PE_totalTradedVolume": latest.get("Overall_PE_totalTradedVolume", ""),
        "Overall_CE_openInterest_delta_since_start": overall_deltas_start.get("Overall_CE_openInterest", "") if overall_deltas_start else "",
        "Overall_PE_openInterest_delta_since_start": overall_deltas_start.get("Overall_PE_openInterest", "") if overall_deltas_start else "",
        "Overall_CE_totalTradedVolume_delta_since_start": overall_deltas_start.get("Overall_CE_totalTradedVolume", "") if overall_deltas_start else "",
        "Overall_PE_totalTradedVolume_delta_since_start": overall_deltas_start.get("Overall_PE_totalTradedVolume", "") if overall_deltas_start else "",
        "Overall_CE_openInterest_delta_from_previous": overall_deltas_prev.get("Overall_CE_openInterest", "") if overall_deltas_prev else "",
        "Overall_PE_openInterest_delta_from_previous": overall_deltas_prev.get("Overall_PE_openInterest", "") if overall_deltas_prev else "",
        "Overall_CE_totalTradedVolume_delta_from_previous": overall_deltas_prev.get("Overall_CE_totalTradedVolume", "") if overall_deltas_prev else "",
        "Overall_PE_totalTradedVolume_delta_from_previous": overall_deltas_prev.get("Overall_PE_totalTradedVolume", "") if overall_deltas_prev else "",
        "pcr": pcr_data.get("pcr", "N/A"),
        "pcr_label": pcr_data.get("label", "unknown"),
        "pcr_score": pcr_data.get("score", "N/A"),
        "market_sentiment_label": market_sentiment.get("label", "unknown"),
        "market_sentiment_score": market_sentiment.get("score", "N/A"),
        "market_sentiment_drivers": _format_list(market_sentiment.get("drivers", [])),
        # morning snapshot
        "morning_underlying": morning_snapshot.get("underlyingValue", "N/A"),
        "morning_pcr": morning_snapshot.get("pcr", "N/A"),
        "morning_pcr_label": morning_snapshot.get("pcr_label", "unknown"),
        "morning_market_sentiment": morning_snapshot.get("market_sentiment_label", "N/A"),
        "morning_ce_cog": morning_snapshot.get("ce_cog", "N/A"),
        "morning_pe_cog": morning_snapshot.get("pe_cog", "N/A"),
        # midday snapshot
        "midday_underlying": midday_snapshot.get("underlyingValue", "N/A"),
        "midday_pcr": midday_snapshot.get("pcr", "N/A"),
        "midday_pcr_label": midday_snapshot.get("pcr_label", "unknown"),
        "midday_market_sentiment": midday_snapshot.get("market_sentiment_label", "N/A"),
        "midday_ce_cog": midday_snapshot.get("ce_cog", "N/A"),
        "midday_pe_cog": midday_snapshot.get("pe_cog", "N/A"),
        # close snapshot
        "close_underlying": close_snapshot.get("underlyingValue", "N/A"),
        "close_pcr": close_snapshot.get("pcr", "N/A"),
        "close_pcr_label": close_snapshot.get("pcr_label", "unknown"),
        "close_market_sentiment": close_snapshot.get("market_sentiment_label", "N/A"),
        "close_ce_cog": close_snapshot.get("ce_cog", "N/A"),
        "close_pe_cog": close_snapshot.get("pe_cog", "N/A"),
        # snapshot date
        "snapshot_date": snapshot_date if snapshot_date else datetime.now().strftime("%Y%m%d"),
        # market structure
        "immediate_resistance": immediate_resistance,
        "major_resistance": major_resistance,
        "immediate_support": immediate_support,
        "major_support": major_support,
    }

    for key, val in mapping.items():
        tpl = tpl.replace(f"{{{{{key}}}}}", str(val))

    return tpl
