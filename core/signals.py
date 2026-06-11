"""Deterministic signal cards from a MetricsRow — pure, no I/O."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import metrics
from core.enrich import MetricsRow

Direction = Literal["bullish", "bearish", "neutral"]
Category = Literal["bias", "levels", "flow", "structure", "volatility"]

# Tunable thresholds (v1)
PCR_BULL_THRESHOLD = 1.10
PCR_BEAR_THRESHOLD = 0.90
PCR_STRONG_DELTA = 0.30
PCR_MODERATE_DELTA = 0.15

MAX_PAIN_PINNED_PCT = 0.001
MAX_PAIN_STRONG_PCT = 0.01

LEVEL_PROXIMITY_MAX_PCT = 0.008
LEVEL_PROXIMITY_STRONG_PCT = 0.0015
LEVEL_PROXIMITY_MODERATE_PCT = 0.004

COG_SHIFT_STRONG = 30
COG_SHIFT_MODERATE = 10
COG_SHIFT_MIN = 2

IV_SKEW_STRONG = 2.0

SENTIMENT_STRONG = 60
SENTIMENT_MODERATE = 25

DEFAULT_MAX_SIGNALS = 6
CATEGORY_PRIORITY: list[Category] = ["bias", "levels", "flow", "structure", "volatility"]


@dataclass
class DayContext:
    """Optional intraday underlying context for expected-move comparison."""

    open: float | None = None
    high: float | None = None
    low: float | None = None


@dataclass
class Signal:
    key: str
    category: Category
    title: str
    text: str
    direction: Direction
    strength: int
    evidence: dict[str, object] = field(default_factory=dict)


def _pcr_strength(pcr: float) -> int:
    delta = abs(pcr - 1.0)
    if delta > PCR_STRONG_DELTA:
        return 3
    if delta > PCR_MODERATE_DELTA:
        return 2
    return 1


def _signal_pcr_bias(curr: MetricsRow) -> Signal | None:
    pcr = curr.pcr_oi
    if pcr is None:
        return None
    pcr_data = metrics.calculate_pcr(curr.total_pe_oi, curr.total_ce_oi)
    label = pcr_data.get("label", "unknown")
    if pcr > PCR_BULL_THRESHOLD:
        direction: Direction = "bullish"
        title = "PCR bias — bullish"
        text = f"Put-call ratio {pcr:.2f} is above {PCR_BULL_THRESHOLD} ({label})."
    elif pcr < PCR_BEAR_THRESHOLD:
        direction = "bearish"
        title = "PCR bias — bearish"
        text = f"Put-call ratio {pcr:.2f} is below {PCR_BEAR_THRESHOLD} ({label})."
    else:
        direction = "neutral"
        title = "PCR bias — neutral"
        text = f"Put-call ratio {pcr:.2f} is near parity ({label})."
    return Signal(
        key="pcr_bias",
        category="bias",
        title=title,
        text=text,
        direction=direction,
        strength=_pcr_strength(pcr),
        evidence={"pcr_oi": pcr},
    )


def _signal_max_pain_pull(curr: MetricsRow) -> Signal | None:
    u, mp = curr.underlying, curr.max_pain
    if u is None or mp is None or u == 0:
        return None
    d = u - mp
    pct = abs(d) / u
    evidence: dict[str, object] = {"underlying": u, "max_pain": mp, "dte": curr.dte}
    if pct < MAX_PAIN_PINNED_PCT:
        return Signal(
            key="max_pain_pull",
            category="levels",
            title="Max pain — pinned",
            text="Price is pinned near max pain.",
            direction="neutral",
            strength=1,
            evidence=evidence,
        )
    direction: Direction = "bearish" if d > 0 else "bullish"
    strength = 2 if pct > MAX_PAIN_STRONG_PCT else 1
    if curr.dte is not None and curr.dte <= 1:
        strength = min(strength + 1, 3)
    lean = "above" if d > 0 else "below"
    return Signal(
        key="max_pain_pull",
        category="levels",
        title="Max pain pull",
        text=f"Underlying is {lean} max pain; expiry gravity may pull toward {mp:.0f}.",
        direction=direction,
        strength=strength,
        evidence=evidence,
    )


def _proximity_strength(pct: float) -> int:
    if pct < LEVEL_PROXIMITY_STRONG_PCT:
        return 3
    if pct < LEVEL_PROXIMITY_MODERATE_PCT:
        return 2
    return 1


def _signal_level_proximity(curr: MetricsRow) -> Signal | None:
    u = curr.underlying
    if u is None or u == 0:
        return None
    candidates: list[tuple[str, float, Direction, str]] = []
    if curr.immediate_support is not None:
        pct = abs(u - curr.immediate_support) / u
        if pct < LEVEL_PROXIMITY_MAX_PCT:
            candidates.append(
                ("support", curr.immediate_support, "bullish", "immediate_support")
            )
    if curr.immediate_resistance is not None:
        pct = abs(u - curr.immediate_resistance) / u
        if pct < LEVEL_PROXIMITY_MAX_PCT:
            candidates.append(
                ("resistance", curr.immediate_resistance, "bearish", "immediate_resistance")
            )
    if not candidates:
        return None
    kind, level, direction, field_name = min(
        candidates, key=lambda c: abs(u - c[1]) / u
    )
    pct = abs(u - level) / u
    return Signal(
        key="level_proximity",
        category="levels",
        title=f"Near {kind}",
        text=f"Price is close to {kind} at {level:.0f}.",
        direction=direction,
        strength=_proximity_strength(pct),
        evidence={"underlying": u, field_name: level},
    )


def _signal_oi_buildup(curr: MetricsRow) -> Signal | None:
    buildup = curr.buildup
    if buildup is None:
        return None
    mapping: dict[str, tuple[Direction, int, str]] = {
        "long_buildup": ("bullish", 2, "Long buildup — price up with rising OI."),
        "short_buildup": ("bearish", 2, "Short buildup — price down with rising OI."),
        "short_covering": ("bullish", 1, "Short covering — price up with falling OI."),
        "long_unwinding": ("bearish", 1, "Long unwinding — price down with falling OI."),
    }
    if buildup not in mapping:
        return None
    direction, strength, text = mapping[buildup]
    return Signal(
        key="oi_buildup",
        category="flow",
        title="OI buildup",
        text=text,
        direction=direction,
        strength=strength,
        evidence={"buildup": buildup},
    )


def _signal_support_migration(curr: MetricsRow, prev: MetricsRow | None) -> Signal | None:
    shift = curr.cog_shift
    if shift is None:
        return None
    mag = abs(shift)
    if mag <= COG_SHIFT_MIN:
        return None
    if mag > COG_SHIFT_STRONG:
        strength = 3
    elif mag > COG_SHIFT_MODERATE:
        strength = 2
    else:
        strength = 1
    direction: Direction = "bullish" if shift > 0 else "bearish"
    cog_data = metrics.calculate_cog_shift(curr.pe_cog, prev.pe_cog if prev else None)
    text = cog_data.get("comment", f"COG shifted {shift:+.0f} points.")
    evidence: dict[str, object] = {"cog_shift": shift}
    if curr.pe_cog is not None:
        evidence["pe_cog"] = curr.pe_cog
    if prev is not None and prev.pe_cog is not None:
        evidence["prev_pe_cog"] = prev.pe_cog
    return Signal(
        key="support_migration",
        category="structure",
        title="Support migration",
        text=str(text),
        direction=direction,
        strength=strength,
        evidence=evidence,
    )


def _signal_expected_move(curr: MetricsRow, day: DayContext | None) -> Signal | None:
    em = curr.expected_move
    atm = curr.atm_straddle
    if em is None and atm is None:
        return None
    move = em if em is not None else atm
    evidence: dict[str, object] = {}
    if atm is not None:
        evidence["atm_straddle"] = atm
    if em is not None:
        evidence["expected_move"] = em
    text = f"ATM straddle implies ~{move:.0f} points expected move."
    if day is not None and day.high is not None and day.low is not None:
        realized = day.high - day.low
        evidence["day_high"] = day.high
        evidence["day_low"] = day.low
        if realized > move:
            text += f" Day range so far ({realized:.0f}) exceeds implied move."
        elif realized < move * 0.5:
            text += f" Day range ({realized:.0f}) is still inside implied move."
        else:
            text += f" Day range ({realized:.0f}) is within implied move."
    return Signal(
        key="expected_move",
        category="volatility",
        title="Expected move",
        text=text,
        direction="neutral",
        strength=1,
        evidence=evidence,
    )


def _signal_iv_skew(curr: MetricsRow) -> Signal | None:
    skew = curr.iv_skew
    if skew is None:
        return None
    strength = 2 if abs(skew) > IV_SKEW_STRONG else 1
    if skew > 0:
        direction: Direction = "bearish"
        text = f"IV skew {skew:.2f} — puts richer (downside fear)."
    elif skew < 0:
        direction = "bullish"
        text = f"IV skew {skew:.2f} — calls richer (upside bid)."
    else:
        direction = "neutral"
        text = "IV skew is flat."
    return Signal(
        key="iv_skew",
        category="volatility",
        title="IV skew",
        text=text,
        direction=direction,
        strength=strength,
        evidence={"iv_skew": skew},
    )


def _signal_oi_flow(curr: MetricsRow) -> Signal | None:
    ce = curr.net_ce_oi_change
    pe = curr.net_pe_oi_change
    flow = metrics._score_oi_flow(ce, pe)
    driver = str(flow.get("driver", "OI flow mixed."))
    if pe > 0 and ce < 0:
        direction: Direction = "bullish"
        strength = 3
    elif pe < 0 and ce > 0:
        direction = "bearish"
        strength = 3
    elif pe > 0 and ce > 0:
        direction = "bullish" if pe >= ce else "bearish"
        strength = 2
    elif pe < 0 and ce < 0:
        direction = "neutral"
        strength = 1
    else:
        direction = "neutral"
        strength = 1
    return Signal(
        key="oi_flow",
        category="flow",
        title="OI flow",
        text=driver,
        direction=direction,
        strength=strength,
        evidence={"net_ce_oi_change": ce, "net_pe_oi_change": pe},
    )


def _signal_pcr_divergence(curr: MetricsRow) -> Signal | None:
    pcr_o, pcr_v = curr.pcr_oi, curr.pcr_volume
    if pcr_o is None or pcr_v is None:
        return None
    sign_o = 1 if pcr_o > 1.0 else -1 if pcr_o < 1.0 else 0
    sign_v = 1 if pcr_v > 1.0 else -1 if pcr_v < 1.0 else 0
    if sign_o == 0 or sign_v == 0 or sign_o == sign_v:
        return None
    return Signal(
        key="pcr_divergence",
        category="bias",
        title="PCR divergence",
        text=f"PCR OI ({pcr_o:.2f}) and volume ({pcr_v:.2f}) disagree — treat bias with caution.",
        direction="neutral",
        strength=1,
        evidence={"pcr_oi": pcr_o, "pcr_volume": pcr_v},
    )


def _signal_overall_read(curr: MetricsRow) -> Signal:
    score = curr.sentiment_score
    label = curr.sentiment_label or "Unknown"
    drivers = curr.drivers or []
    if score is None:
        return Signal(
            key="overall_read",
            category="bias",
            title="Overall read",
            text="Sentiment data unavailable.",
            direction="neutral",
            strength=1,
            evidence={"sentiment_label": label},
        )
    mag = abs(score)
    strength = 3 if mag >= SENTIMENT_STRONG else 2 if mag >= SENTIMENT_MODERATE else 1
    if score > 0:
        direction: Direction = "bullish"
    elif score < 0:
        direction = "bearish"
    else:
        direction = "neutral"
    driver_text = drivers[0] if drivers else ""
    text = f"{label} (score {score})."
    if driver_text:
        text += f" {driver_text}"
    evidence: dict[str, object] = {
        "sentiment_score": score,
        "sentiment_label": label,
    }
    return Signal(
        key="overall_read",
        category="bias",
        title="Overall read",
        text=text,
        direction=direction,
        strength=strength,
        evidence=evidence,
    )


def _rank_signals(signals: list[Signal], max_signals: int) -> list[Signal]:
    overall = next((s for s in signals if s.key == "overall_read"), None)
    rest = [s for s in signals if s.key != "overall_read"]
    priority = {c: i for i, c in enumerate(CATEGORY_PRIORITY)}
    rest.sort(key=lambda s: (-s.strength, priority.get(s.category, 99)))
    ranked = ([overall] if overall else []) + rest
    return ranked[:max_signals]


def build_signals(
    curr: MetricsRow,
    prev: MetricsRow | None = None,
    day: DayContext | None = None,
    max_signals: int = DEFAULT_MAX_SIGNALS,
) -> list[Signal]:
    """Build ranked signal cards from current metrics (+ optional prev/day context)."""
    candidates: list[Signal] = []
    for fn in (
        _signal_pcr_bias,
        _signal_max_pain_pull,
        _signal_level_proximity,
        _signal_oi_buildup,
        lambda c: _signal_support_migration(c, prev),
        lambda c: _signal_expected_move(c, day),
        _signal_iv_skew,
        _signal_oi_flow,
        _signal_pcr_divergence,
    ):
        sig = fn(curr)
        if sig is not None:
            candidates.append(sig)
    candidates.append(_signal_overall_read(curr))
    return _rank_signals(candidates, max_signals)
