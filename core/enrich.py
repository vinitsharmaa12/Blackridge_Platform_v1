"""Compute one instrument-level `metrics` row from a normalized Snapshot.

Reuses the existing pure functions in metrics.py (COG, PCR, sentiment, market
structure) and adds the new metrics catalogued in ARCHITECTURE.md §7:
ATM IV, IV skew, max pain, ATM straddle / expected move, PCR-by-volume, totals,
net OI change, buy/sell imbalance, buildup, DTE.

Single-snapshot fields are always computable. Fields that need the *previous*
snapshot (COG shift, full sentiment, buildup) accept an optional `prev`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import metrics
from core.normalize import Snapshot, StrikeRow


def _sum(rows, attr) -> int:
    return int(sum(getattr(r, attr) or 0 for r in rows))


def _atm_row(rows: list[StrikeRow], underlying: float) -> Optional[StrikeRow]:
    cands = [r for r in rows if r.strike is not None]
    if not cands or underlying is None:
        return None
    return min(cands, key=lambda r: abs(r.strike - underlying))


def _atm_iv(atm: Optional[StrikeRow]) -> Optional[float]:
    if atm is None:
        return None
    ivs = [v for v in (atm.ce_iv, atm.pe_iv) if v]
    return round(sum(ivs) / len(ivs), 2) if ivs else None


def _iv_skew(rows: list[StrikeRow], underlying: float, atm: Optional[StrikeRow]) -> Optional[float]:
    """Basic 'risk reversal' skew: OTM put IV - OTM call IV at a symmetric offset.

    Picks the put one step below and the call one step above ATM by strike order.
    Positive skew => puts richer => downside fear.
    """
    if atm is None or underlying is None:
        return None
    strikes = sorted({r.strike for r in rows})
    if atm.strike not in strikes:
        return None
    i = strikes.index(atm.strike)
    by_strike = {r.strike: r for r in rows}
    put_leg = by_strike.get(strikes[max(0, i - 2)])
    call_leg = by_strike.get(strikes[min(len(strikes) - 1, i + 2)])
    if put_leg is None or call_leg is None or not put_leg.pe_iv or not call_leg.ce_iv:
        return None
    return round(put_leg.pe_iv - call_leg.ce_iv, 2)


def _max_pain(rows: list[StrikeRow]) -> Optional[float]:
    """Strike that minimizes total intrinsic payout to option holders."""
    strikes = sorted({r.strike for r in rows if r.strike is not None})
    if not strikes:
        return None
    oi = {r.strike: (r.ce_oi or 0, r.pe_oi or 0) for r in rows}
    best_strike, best_pain = None, None
    for settle in strikes:
        pain = 0.0
        for k in strikes:
            ce_oi, pe_oi = oi.get(k, (0, 0))
            if settle > k:
                pain += ce_oi * (settle - k)   # calls ITM
            if settle < k:
                pain += pe_oi * (k - settle)   # puts ITM
        if best_pain is None or pain < best_pain:
            best_pain, best_strike = pain, settle
    return best_strike


def _support_resistance(rows: list[StrikeRow], underlying: float) -> dict:
    """OI-based S/R: heaviest PE OI below spot = support, heaviest CE OI above = resistance."""
    out = {"immediate_support": None, "major_support": None,
           "immediate_resistance": None, "major_resistance": None}
    if underlying is None:
        return out
    below = [(r.strike, r.pe_oi or 0) for r in rows if r.strike < underlying]
    above = [(r.strike, r.ce_oi or 0) for r in rows if r.strike > underlying]
    if below:
        out["immediate_support"] = max(below, key=lambda x: x[1])[0]
        out["major_support"] = max((r.strike, r.pe_oi or 0) for r in rows)[0] \
            if rows else None
        out["major_support"] = max(rows, key=lambda r: r.pe_oi or 0).strike
    if above:
        out["immediate_resistance"] = max(above, key=lambda x: x[1])[0]
        out["major_resistance"] = max(rows, key=lambda r: r.ce_oi or 0).strike
    return out


def _buildup(price_change: Optional[float], net_oi_change: int) -> Optional[str]:
    """Classic price-vs-OI buildup classification. Flat price => neutral."""
    if price_change is None or abs(price_change) < 1e-6 or net_oi_change == 0:
        return None
    up = price_change > 0
    oi_up = net_oi_change > 0
    if up and oi_up:
        return "long_buildup"
    if not up and oi_up:
        return "short_buildup"
    if up and not oi_up:
        return "short_covering"
    return "long_unwinding"


@dataclass
class MetricsRow:
    time: object
    expiry: object
    dte: Optional[int]
    underlying: Optional[float]
    pcr_oi: Optional[float]
    pcr_volume: Optional[float]
    ce_cog: Optional[float]
    pe_cog: Optional[float]
    cog_shift: Optional[float]
    atm_strike: Optional[float]
    atm_iv: Optional[float]
    iv_skew: Optional[float]
    india_vix: Optional[float]
    atm_straddle: Optional[float]
    expected_move: Optional[float]
    max_pain: Optional[float]
    total_ce_oi: int
    total_pe_oi: int
    net_ce_oi_change: int
    net_pe_oi_change: int
    total_ce_volume: int
    total_pe_volume: int
    buy_sell_imbalance: Optional[float]
    buildup: Optional[str]
    immediate_support: Optional[float]
    major_support: Optional[float]
    immediate_resistance: Optional[float]
    major_resistance: Optional[float]
    sentiment_score: Optional[int]
    sentiment_label: Optional[str]
    drivers: list

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def compute_metrics(
    snap: Snapshot,
    prev: Optional[Snapshot] = None,
    india_vix: Optional[float] = None,
) -> MetricsRow:
    rows, u = snap.rows, snap.underlying

    total_ce_oi = _sum(rows, "ce_oi")
    total_pe_oi = _sum(rows, "pe_oi")
    total_ce_vol = _sum(rows, "ce_volume")
    total_pe_vol = _sum(rows, "pe_volume")
    net_ce_oi_change = _sum(rows, "ce_oi_change")
    net_pe_oi_change = _sum(rows, "pe_oi_change")

    pcr_data = metrics.calculate_pcr(total_pe_oi, total_ce_oi)
    pcr_vol = round(total_pe_vol / total_ce_vol, 3) if total_ce_vol else None

    ce_cog = metrics.calculate_cog(
        [r.strike for r in rows], [r.ce_oi for r in rows]).get("cog")
    pe_cog = metrics.calculate_cog(
        [r.strike for r in rows], [r.pe_oi for r in rows]).get("cog")

    cog_shift = None
    if prev is not None:
        prev_pe_cog = metrics.calculate_cog(
            [r.strike for r in prev.rows], [r.pe_oi for r in prev.rows]).get("cog")
        if pe_cog is not None and prev_pe_cog is not None:
            cog_shift = round(pe_cog - prev_pe_cog, 2)

    atm = _atm_row(rows, u)
    atm_straddle = None
    if atm is not None and atm.ce_ltp is not None and atm.pe_ltp is not None:
        atm_straddle = round(atm.ce_ltp + atm.pe_ltp, 2)

    price_change = None
    if prev is not None and prev.underlying is not None and u is not None:
        price_change = u - prev.underlying

    total_buy = _sum(rows, "ce_buy_qty") + _sum(rows, "pe_buy_qty")
    total_sell = _sum(rows, "ce_sell_qty") + _sum(rows, "pe_sell_qty")
    imbalance = round(total_buy / total_sell, 3) if total_sell else None

    sr = _support_resistance(rows, u)

    sentiment = metrics.calculate_market_sentiment(
        ce_cog_data={"current": ce_cog, "previous": None},
        pe_cog_data={"current": pe_cog, "previous": None},
        ce_migration={"direction": "flat"},
        pe_migration={"direction": "flat"},
        pcr_data=pcr_data,
        ce_oi_change=net_ce_oi_change,
        pe_oi_change=net_pe_oi_change,
    )

    return MetricsRow(
        time=snap.time,
        expiry=snap.expiry,
        dte=snap.dte,
        underlying=u,
        pcr_oi=pcr_data.get("pcr"),
        pcr_volume=pcr_vol,
        ce_cog=round(ce_cog, 2) if ce_cog is not None else None,
        pe_cog=round(pe_cog, 2) if pe_cog is not None else None,
        cog_shift=cog_shift,
        atm_strike=atm.strike if atm else None,
        atm_iv=_atm_iv(atm),
        iv_skew=_iv_skew(rows, u, atm),
        india_vix=india_vix,
        atm_straddle=atm_straddle,
        expected_move=atm_straddle,  # ATM straddle ≈ expected absolute move
        max_pain=_max_pain(rows),
        total_ce_oi=total_ce_oi,
        total_pe_oi=total_pe_oi,
        net_ce_oi_change=net_ce_oi_change,
        net_pe_oi_change=net_pe_oi_change,
        total_ce_volume=total_ce_vol,
        total_pe_volume=total_pe_vol,
        buy_sell_imbalance=imbalance,
        buildup=_buildup(price_change, net_ce_oi_change + net_pe_oi_change),
        sentiment_score=sentiment.get("score"),
        sentiment_label=sentiment.get("label"),
        drivers=sentiment.get("drivers", []),
        **sr,
    )
