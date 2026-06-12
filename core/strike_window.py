"""ATM ±N strike window helpers matching _ref/Preprocessing.py."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from core.normalize import StrikeRow

DEFAULT_WINDOW = 10
DEFAULT_TOP_N = 3


def _as_float(value: object) -> float | None:
    """Coerce DB/API numerics (e.g. Decimal) to float for arithmetic."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sorted_strikes(rows: Sequence[StrikeRow]) -> list[float]:
    return sorted({r.strike for r in rows if r.strike is not None})


def window_strike_set(
    strikes: Sequence[float],
    underlying: object,
    *,
    window: int = DEFAULT_WINDOW,
) -> set[float]:
    underlying_f = _as_float(underlying)
    if not strikes or underlying_f is None:
        return set(strikes)
    center_idx = min(range(len(strikes)), key=lambda i: abs(strikes[i] - underlying_f))
    start = max(0, center_idx - window)
    end = min(len(strikes) - 1, center_idx + window)
    return set(strikes[start : end + 1])


def rows_in_window(
    rows: Sequence[StrikeRow],
    underlying: float | None,
    *,
    window: int = DEFAULT_WINDOW,
) -> list[StrikeRow]:
    win = window_strike_set(_sorted_strikes(rows), underlying, window=window)
    return [r for r in rows if r.strike in win]


def top_oi_strikes(
    rows: Sequence[StrikeRow],
    underlying: float | None,
    *,
    side: Literal["ce", "pe"],
    n: int = DEFAULT_TOP_N,
    window: int = DEFAULT_WINDOW,
) -> list[tuple[float, int]]:
    attr = "ce_oi" if side == "ce" else "pe_oi"
    filtered = rows_in_window(rows, underlying, window=window)
    ranked = sorted(
        [
            (r.strike, int(getattr(r, attr) or 0))
            for r in filtered
            if r.strike is not None
        ],
        key=lambda item: item[1],
        reverse=True,
    )
    return [(strike, oi) for strike, oi in ranked if oi > 0][:n]


def top_oi_strike_numbers(
    rows: Sequence[StrikeRow],
    underlying: float | None,
    *,
    side: Literal["ce", "pe"],
    n: int = DEFAULT_TOP_N,
    window: int = DEFAULT_WINDOW,
) -> list[float]:
    return [strike for strike, _ in top_oi_strikes(rows, underlying, side=side, n=n, window=window)]


def top_oi_from_chain_dicts(
    rows: Sequence[dict[str, object]],
    underlying: object,
    *,
    side: Literal["ce", "pe"],
    n: int = DEFAULT_TOP_N,
    window: int = DEFAULT_WINDOW,
) -> list[dict[str, float | int]]:
    """Rank top OI strikes from API/DB chain rows (strike, ce_oi, pe_oi dicts)."""
    strikes = sorted(
        {
            float(r["strike"])
            for r in rows
            if r.get("strike") is not None
        }
    )
    win = window_strike_set(strikes, underlying, window=window)
    attr = "ce_oi" if side == "ce" else "pe_oi"
    ranked = sorted(
        [
            (float(r["strike"]), int(r.get(attr) or 0))
            for r in rows
            if r.get("strike") is not None and float(r["strike"]) in win
        ],
        key=lambda item: item[1],
        reverse=True,
    )
    return [
        {"strike": strike, "oi": oi}
        for strike, oi in ranked
        if oi > 0
    ][:n]
