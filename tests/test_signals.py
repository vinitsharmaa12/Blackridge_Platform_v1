"""Tests for deterministic signal cards (PRD 002.5)."""
from __future__ import annotations

from datetime import date, datetime

from core.enrich import MetricsRow, compute_metrics
from core.normalize import normalize
from core.signals import (
    PCR_BEAR_THRESHOLD,
    PCR_BULL_THRESHOLD,
    DayContext,
    build_signals,
)


def _minimal_metrics(**overrides: object) -> MetricsRow:
    defaults: dict[str, object] = {
        "time": datetime(2026, 6, 8, 10, 0),
        "expiry": date(2026, 6, 9),
        "dte": 1,
        "underlying": 25000.0,
        "pcr_oi": 1.0,
        "pcr_volume": 1.0,
        "ce_cog": 25000.0,
        "pe_cog": 24900.0,
        "cog_shift": None,
        "atm_strike": 25000.0,
        "atm_iv": 12.0,
        "iv_skew": 0.0,
        "india_vix": None,
        "atm_straddle": 200.0,
        "expected_move": 200.0,
        "max_pain": 24900.0,
        "total_ce_oi": 1000000,
        "total_pe_oi": 1000000,
        "net_ce_oi_change": 0,
        "net_pe_oi_change": 0,
        "total_ce_volume": 100000,
        "total_pe_volume": 100000,
        "buy_sell_imbalance": 1.0,
        "buildup": None,
        "immediate_support": 24800.0,
        "major_support": 24500.0,
        "immediate_resistance": 25100.0,
        "major_resistance": 25500.0,
        "sentiment_score": 0,
        "sentiment_label": "Neutral",
        "drivers": ["PCR 1.0 (neutral)."],
    }
    defaults.update(overrides)
    return MetricsRow(**defaults)


def test_build_signals_real_fixture(sample_chain_json: dict) -> None:
    snap = normalize(sample_chain_json, source_name="fixture.json")
    curr = compute_metrics(snap)
    signals = build_signals(curr)
    assert len(signals) <= 6
    assert signals[0].key == "overall_read"
    assert all(s.strength >= 1 and s.strength <= 3 for s in signals)
    assert all(s.evidence for s in signals)


def test_overall_read_always_present() -> None:
    m = _minimal_metrics(sentiment_score=None, sentiment_label=None, drivers=[])
    signals = build_signals(m)
    overall = [s for s in signals if s.key == "overall_read"]
    assert len(overall) == 1
    assert signals[0].key == "overall_read"


def test_pcr_bias_bullish() -> None:
    m = _minimal_metrics(pcr_oi=1.25, total_pe_oi=1250000, total_ce_oi=1000000)
    sig = next(s for s in build_signals(m, max_signals=20) if s.key == "pcr_bias")
    assert sig.direction == "bullish"
    assert sig.strength == 2
    assert sig.evidence == {"pcr_oi": 1.25}


def test_pcr_bias_bearish() -> None:
    m = _minimal_metrics(pcr_oi=0.75, total_pe_oi=750000, total_ce_oi=1000000)
    sig = next(s for s in build_signals(m, max_signals=20) if s.key == "pcr_bias")
    assert sig.direction == "bearish"
    assert sig.evidence["pcr_oi"] == 0.75


def test_max_pain_pull_pinned() -> None:
    m = _minimal_metrics(underlying=25000.0, max_pain=25000.0)
    sig = next(s for s in build_signals(m, max_signals=20) if s.key == "max_pain_pull")
    assert sig.direction == "neutral"
    assert "pinned" in sig.text.lower()


def test_max_pain_pull_bullish_below_pain() -> None:
    m = _minimal_metrics(underlying=24800.0, max_pain=25000.0, dte=1)
    sig = next(s for s in build_signals(m, max_signals=20) if s.key == "max_pain_pull")
    assert sig.direction == "bullish"
    assert sig.strength >= 2


def test_oi_buildup_omits_null() -> None:
    m = _minimal_metrics(buildup=None)
    keys = {s.key for s in build_signals(m, max_signals=20)}
    assert "oi_buildup" not in keys


def test_oi_buildup_long() -> None:
    m = _minimal_metrics(buildup="long_buildup")
    sig = next(s for s in build_signals(m, max_signals=20) if s.key == "oi_buildup")
    assert sig.direction == "bullish"
    assert sig.strength == 2


def test_support_migration_omits_small_shift() -> None:
    m = _minimal_metrics(cog_shift=1.0)
    keys = {s.key for s in build_signals(m, max_signals=20)}
    assert "support_migration" not in keys


def test_support_migration_bullish() -> None:
    prev = _minimal_metrics(pe_cog=24800.0)
    m = _minimal_metrics(pe_cog=24950.0, cog_shift=150.0)
    sig = next(
        s for s in build_signals(m, prev=prev, max_signals=20) if s.key == "support_migration"
    )
    assert sig.direction == "bullish"
    assert sig.strength == 3


def test_oi_flow_bullish() -> None:
    m = _minimal_metrics(net_pe_oi_change=50000, net_ce_oi_change=-30000)
    sig = next(s for s in build_signals(m, max_signals=20) if s.key == "oi_flow")
    assert sig.direction == "bullish"
    assert sig.strength == 3


def test_pcr_divergence() -> None:
    m = _minimal_metrics(pcr_oi=1.2, pcr_volume=0.85)
    sig = next(s for s in build_signals(m, max_signals=20) if s.key == "pcr_divergence")
    assert sig.direction == "neutral"
    assert sig.strength == 1


def test_iv_skew_put_rich() -> None:
    m = _minimal_metrics(iv_skew=3.0)
    sig = next(s for s in build_signals(m, max_signals=20) if s.key == "iv_skew")
    assert sig.direction == "bearish"
    assert sig.strength == 2


def test_expected_move_with_day_context() -> None:
    m = _minimal_metrics(expected_move=100.0, atm_straddle=100.0)
    day = DayContext(open=25000.0, high=25150.0, low=24900.0)
    sig = next(s for s in build_signals(m, day=day, max_signals=20) if s.key == "expected_move")
    assert sig.direction == "neutral"
    assert sig.evidence["day_high"] == 25150.0
    assert sig.evidence["day_low"] == 24900.0


def test_null_sparse_metrics_no_crash() -> None:
    m = _minimal_metrics(
        underlying=None,
        pcr_oi=None,
        pcr_volume=None,
        max_pain=None,
        iv_skew=None,
        cog_shift=None,
        buildup=None,
        immediate_support=None,
        immediate_resistance=None,
        sentiment_score=None,
        sentiment_label=None,
        drivers=[],
        atm_straddle=None,
        expected_move=None,
    )
    signals = build_signals(m)
    assert signals[0].key == "overall_read"
    assert len(signals) <= 6


def test_ranking_caps_at_six() -> None:
    m = _minimal_metrics(
        pcr_oi=1.35,
        iv_skew=4.0,
        buildup="long_buildup",
        cog_shift=50.0,
        net_pe_oi_change=100000,
        net_ce_oi_change=-50000,
        pcr_volume=0.8,
        sentiment_score=70,
        sentiment_label="Strong Bullish",
    )
    assert len(build_signals(m)) == 6


def test_pcr_threshold_constants() -> None:
    assert PCR_BULL_THRESHOLD == 1.10
    assert PCR_BEAR_THRESHOLD == 0.90
