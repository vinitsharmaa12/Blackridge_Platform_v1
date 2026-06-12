"""Tests for _ref/metrics.py wiring in core/enrich.py."""
from __future__ import annotations

from core.enrich import compute_metrics
from core.normalize import Snapshot, StrikeRow


def _snap(
    time_label: str,
    underlying: float,
    rows: list[StrikeRow],
) -> Snapshot:
    from datetime import date, datetime

    return Snapshot(
        time=datetime.fromisoformat(time_label),
        underlying=underlying,
        expiry=date(2026, 6, 12),
        rows=rows,
    )


def _strike(strike: float, *, ce_oi: int, pe_oi: int, underlying: float) -> StrikeRow:
    from datetime import date, datetime

    return StrikeRow(
        time=datetime(2026, 6, 12, 10, 0),
        expiry=date(2026, 6, 12),
        strike=strike,
        underlying=underlying,
        ce_oi=ce_oi,
        pe_oi=pe_oi,
        ce_oi_change=0,
        pe_oi_change=0,
    )


def _chain(center: float, n: int = 11) -> list[StrikeRow]:
    return [
        _strike(
            center + i * 50,
            ce_oi=1000 - abs(i) * 10,
            pe_oi=900 - abs(i) * 5,
            underlying=center,
        )
        for i in range(-(n // 2), n // 2 + 1)
    ]


def test_sentiment_includes_cog_and_migration_drivers_with_prev() -> None:
    prev_rows = _chain(24500.0)
    curr_rows = _chain(24550.0)
    prev = _snap("2026-06-12T10:00:00", 24500.0, prev_rows)
    curr = _snap("2026-06-12T10:01:00", 24550.0, curr_rows)

    row = compute_metrics(curr, prev=prev)
    drivers = " ".join(row.drivers)

    assert "CE COG shifted" in drivers
    assert "PE COG shifted" in drivers
    assert "CE migration" in drivers
    assert "PE migration" in drivers
    assert row.sentiment_score is not None


def test_sentiment_without_prev_uses_neutral_migration() -> None:
    curr = _snap("2026-06-12T10:00:00", 24500.0, _chain(24500.0))
    row = compute_metrics(curr, prev=None)
    drivers = " ".join(row.drivers)

    assert "CE migration is neutral" in drivers
    assert "PE migration is neutral" in drivers
