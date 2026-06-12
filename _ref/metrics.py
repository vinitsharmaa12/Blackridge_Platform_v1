from typing import Dict, Iterable, List, Optional


def safe_int(value) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except Exception:
        return None


def to_number(value) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(str(value).replace(",", ""))
    except Exception:
        return 0.0


def calculate_cog(strikes: Iterable, oi_values: Iterable) -> Dict[str, Optional[float]]:
    total_weight = 0.0
    total_oi = 0.0
    for strike, oi in zip(strikes, oi_values):
        strike_value = safe_int(strike)
        oi_value = to_number(oi)
        if strike_value is None or oi_value <= 0:
            continue
        total_weight += strike_value * oi_value
        total_oi += oi_value
    if total_oi == 0:
        return {"cog": None}
    return {"cog": total_weight / total_oi}


def calculate_cog_shift(current_cog: Optional[float], previous_cog: Optional[float]) -> Dict[str, Optional[object]]:
    if current_cog is None or previous_cog is None:
        return {
            "shift": None,
            "direction": "flat",
            "comment": "No previous COG available.",
        }

    shift = current_cog - previous_cog
    if shift > 0:
        direction = "up"
    elif shift < 0:
        direction = "down"
    else:
        direction = "flat"

    points = abs(round(shift))
    if current_cog is None or previous_cog is None:
        comment = "No previous COG available."
    elif direction == "up":
        comment = f"Resistance migrated {points} points higher. COG is shifting upward. Bullish indication."
    elif direction == "down":
        comment = f"Resistance migrated {points} points lower. COG is shifting downward. Bearish indication."
    else:
        comment = "COG is unchanged."

    return {
        "shift": shift,
        "direction": direction,
        "comment": comment,
    }


def calculate_pcr(overall_pe_oi, overall_ce_oi) -> Dict[str, Optional[object]]:
    pe_oi = to_number(overall_pe_oi)
    ce_oi = to_number(overall_ce_oi)
    if ce_oi == 0:
        return {"pcr": None, "label": "unknown", "score": None}

    pcr = pe_oi / ce_oi
    if pcr > 1.10:
        label = "bullish"
        score = 15
    elif pcr < 0.90:
        label = "bearish"
        score = -15
    else:
        label = "neutral"
        score = 0

    return {"pcr": round(pcr, 2), "label": label, "score": score}


def _score_cog_side(cog_data: dict, side: str) -> dict:
    current = cog_data.get("current")
    previous = cog_data.get("previous")
    shift = cog_data.get("shift")
    if shift is None and current is not None and previous is not None:
        shift = current - previous

    if shift is None:
        return {"score": 0, "driver": f"{side} COG change unavailable."}

    magnitude = min(abs(round(shift)), 20)
    score = int(magnitude * 2) if shift > 0 else -int(magnitude * 2)
    trend = "bullish" if shift > 0 else "bearish" if shift < 0 else "neutral"
    driver = f"{side} COG shifted {shift:+.0f} points ({trend})."
    return {"score": score, "driver": driver}


def _score_migration_side(migration_data: dict, side: str) -> dict:
    direction = str(migration_data.get("direction", "")).lower()
    if direction == "up":
        score = 15
        note = f"{side} migration is upward bullish."
    elif direction == "down":
        score = -15
        note = f"{side} migration is downward bearish."
    else:
        score = 0
        note = f"{side} migration is neutral or unchanged."
    return {"score": score, "driver": note}


def _score_oi_flow(ce_oi_change, pe_oi_change) -> dict:
    ce = to_number(ce_oi_change)
    pe = to_number(pe_oi_change)
    if ce == 0 and pe == 0:
        return {"score": 0, "driver": "OI flow data unavailable."}

    if pe > 0 and ce < 0:
        score = 30
        note = "PE OI is rising while CE OI is falling: bullish flow."
    elif pe < 0 and ce > 0:
        score = -30
        note = "PE OI is falling while CE OI is rising: bearish flow."
    elif pe > 0 and ce > 0:
        score = 10 if pe >= ce else -10
        note = "Both PE and CE OI are rising; flow favors the larger side."
    elif pe < 0 and ce < 0:
        score = 10 if abs(pe) <= abs(ce) else -10
        note = "Both PE and CE OI are falling; weaker directional flow."
    else:
        score = 0
        note = "OI flow is mixed."
    return {"score": score, "driver": note}


def calculate_market_sentiment(
    ce_cog_data,
    pe_cog_data,
    ce_migration,
    pe_migration,
    pcr_data,
    ce_oi_change,
    pe_oi_change,
) -> Dict[str, object]:
    pcr_score = int(pcr_data.get("score", 0) or 0)
    pcr_driver = f"PCR {pcr_data.get('pcr', 'N/A')} ({pcr_data.get('label', 'unknown')})."

    ce_cog_score_data = _score_cog_side(ce_cog_data, "CE")
    pe_cog_score_data = _score_cog_side(pe_cog_data, "PE")
    ce_migration_score_data = _score_migration_side(ce_migration, "CE")
    pe_migration_score_data = _score_migration_side(pe_migration, "PE")
    oi_flow_score_data = _score_oi_flow(ce_oi_change, pe_oi_change)

    total_score = (
        pcr_score
        + ce_cog_score_data["score"]
        + pe_cog_score_data["score"]
        + ce_migration_score_data["score"]
        + pe_migration_score_data["score"]
        + oi_flow_score_data["score"]
    )
    total_score = max(min(total_score, 100), -100)

    if total_score >= 60:
        label = "Strong Bullish"
    elif total_score >= 25:
        label = "Bullish"
    elif total_score <= -60:
        label = "Strong Bearish"
    elif total_score <= -25:
        label = "Bearish"
    else:
        label = "Neutral"

    drivers = [
        pcr_driver,
        ce_cog_score_data["driver"],
        pe_cog_score_data["driver"],
        ce_migration_score_data["driver"],
        pe_migration_score_data["driver"],
        oi_flow_score_data["driver"],
    ]

    return {
        "score": total_score,
        "label": label,
        "drivers": drivers,
    }


def analyze_migration(previous_strikes: Iterable, current_strikes: Iterable) -> Dict[str, object]:
    previous_set = {safe_int(s) for s in previous_strikes if safe_int(s) is not None}
    current_set = {safe_int(s) for s in current_strikes if safe_int(s) is not None}

    added = sorted(current_set - previous_set)
    removed = sorted(previous_set - current_set)
    common = sorted(current_set & previous_set)

    avg_previous = sum(previous_set) / len(previous_set) if previous_set else None
    avg_current = sum(current_set) / len(current_set) if current_set else None

    if avg_current is None or avg_previous is None:
        direction = "no shift"
        arrow = "→"
    elif avg_current > avg_previous:
        direction = "up"
        arrow = "↑"
    elif avg_current < avg_previous:
        direction = "down"
        arrow = "↓"
    else:
        direction = "no shift"
        arrow = "→"

    return {
        "added": added,
        "removed": removed,
        "common": common,
        "direction": direction,
        "arrow": arrow,
    }


def calculate_price_change(current_underlying: float, previous_underlying: float) -> Dict[str, object]:
    """Calculate price change between current and previous underlying values."""
    if current_underlying is None or previous_underlying is None:
        return {
            "change": None,
            "direction": "flat",
            "comment": "No previous underlying price available.",
            "points": 0,
        }
    change = current_underlying - previous_underlying
    if change > 0:
        direction = "up"
    elif change < 0:
        direction = "down"
    else:
        direction = "flat"
    points = abs(round(change))
    if direction == "up":
        comment = f"Underlying rose {points} points. Bullish indication."
    elif direction == "down":
        comment = f"Underlying fell {points} points. Bearish indication."
    else:
        comment = "Underlying price unchanged."
    return {
        "change": change,
        "direction": direction,
        "comment": comment,
        "points": points,
    }


def compute_market_structure(ce_items: Iterable, pe_items: Iterable, underlying) -> Dict[str, object]:
    """Compute immediate and major support/resistance levels.

    - `ce_items` and `pe_items` are iterables of (strike, oi) pairs.
    - `underlying` is the current underlying price (number or numeric string).

    Returns a dict with keys: immediate_resistance, major_resistance, immediate_support, major_support.
    """
    try:
        u = float(str(underlying))
        u_int = int(round(u))
    except Exception:
        u_int = None

    ce_strikes = sorted({safe_int(s) for s, _ in ce_items if safe_int(s) is not None})
    pe_strikes = sorted({safe_int(s) for s, _ in pe_items if safe_int(s) is not None})

    def im_resistance():
        if not ce_strikes:
            return "N/A"
        if u_int is None:
            return ce_strikes[-1]
        for s in ce_strikes:
            if s > u_int:
                return s
        return ce_strikes[-1]

    def maj_resistance():
        return ce_strikes[-1] if ce_strikes else "N/A"

    def im_support():
        if not pe_strikes:
            return "N/A"
        if u_int is None:
            return pe_strikes[0]
        for s in reversed(pe_strikes):
            if s < u_int:
                return s
        return pe_strikes[0]

    def maj_support():
        return pe_strikes[0] if pe_strikes else "N/A"

    return {
        "immediate_resistance": im_resistance(),
        "major_resistance": maj_resistance(),
        "immediate_support": im_support(),
        "major_support": maj_support(),
    }
