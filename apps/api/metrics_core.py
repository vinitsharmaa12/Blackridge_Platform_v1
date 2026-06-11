"""Bridge DB metrics rows to core.enrich.MetricsRow for pure signal logic."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from core.enrich import MetricsRow

_CORE_FIELDS = frozenset(MetricsRow.__dataclass_fields__)

_FLOAT_FIELDS = frozenset({
    "underlying", "pcr_oi", "pcr_volume", "ce_cog", "pe_cog", "cog_shift",
    "atm_strike", "atm_iv", "iv_skew", "india_vix", "atm_straddle",
    "expected_move", "max_pain", "buy_sell_imbalance",
    "immediate_support", "major_support", "immediate_resistance", "major_resistance",
})
_INT_FIELDS = frozenset({
    "dte", "total_ce_oi", "total_pe_oi", "net_ce_oi_change", "net_pe_oi_change",
    "total_ce_volume", "total_pe_volume", "sentiment_score",
})


def _coerce_db_value(key: str, value: Any) -> Any:
    if value is None or not isinstance(value, Decimal):
        return value
    if key in _INT_FIELDS:
        return int(value)
    if key in _FLOAT_FIELDS:
        return float(value)
    return value


def metrics_row_from_db(row: dict[str, Any]) -> MetricsRow:
    data = {k: _coerce_db_value(k, row.get(k)) for k in _CORE_FIELDS}
    if data.get("drivers") is None:
        data["drivers"] = []
    return MetricsRow(**data)
