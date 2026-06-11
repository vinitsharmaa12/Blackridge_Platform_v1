"""DB write idempotency contract tests (no live Postgres required)."""
from __future__ import annotations

from datetime import date, datetime

from core.db import write_metrics, write_snapshot
from core.enrich import MetricsRow
from core.normalize import Snapshot, StrikeRow


class _RecordingCursor:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.rowcount = 1

    def __enter__(self) -> _RecordingCursor:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def executemany(self, sql: str, params: list[tuple]) -> None:
        self.statements.append(sql)
        self._last_params_len = len(params)

    def execute(self, sql: str, params: tuple | None = None) -> None:
        self.statements.append(sql)

    def fetchone(self) -> tuple | None:
        return None


class _RecordingConn:
    def __init__(self) -> None:
        self.cursor_obj = _RecordingCursor()

    def cursor(self) -> _RecordingCursor:
        return self.cursor_obj


def _sample_snap(ts: datetime) -> Snapshot:
    row = StrikeRow(
        time=ts,
        expiry=date(2026, 6, 9),
        strike=25000.0,
        underlying=25000.0,
        ce_oi=100,
        pe_oi=120,
        source="nse",
    )
    return Snapshot(time=ts, underlying=25000.0, expiry=date(2026, 6, 9), rows=[row])


def _sample_metrics(ts: datetime) -> MetricsRow:
    return MetricsRow(
        time=ts,
        expiry=date(2026, 6, 9),
        dte=1,
        underlying=25000.0,
        pcr_oi=1.1,
        pcr_volume=1.0,
        ce_cog=25000.0,
        pe_cog=24900.0,
        cog_shift=None,
        atm_strike=25000.0,
        atm_iv=12.0,
        iv_skew=1.0,
        india_vix=None,
        atm_straddle=200.0,
        expected_move=200.0,
        max_pain=24900.0,
        total_ce_oi=1000,
        total_pe_oi=1100,
        net_ce_oi_change=10,
        net_pe_oi_change=20,
        total_ce_volume=100,
        total_pe_volume=100,
        buy_sell_imbalance=1.0,
        buildup=None,
        immediate_support=24800.0,
        major_support=24500.0,
        immediate_resistance=25200.0,
        major_resistance=25500.0,
        sentiment_score=50,
        sentiment_label="Neutral",
        drivers=[],
    )


def test_write_snapshot_uses_on_conflict_do_nothing() -> None:
    conn = _RecordingConn()
    ts = datetime(2026, 6, 8, 10, 30)
    snap = _sample_snap(ts)

    write_snapshot(conn, instrument_id=1, snap=snap)
    write_snapshot(conn, instrument_id=1, snap=snap)

    sql = conn.cursor_obj.statements[0].lower()
    assert "on conflict" in sql
    assert "do nothing" in sql
    assert len(conn.cursor_obj.statements) == 2


def test_write_metrics_uses_on_conflict_do_update() -> None:
    conn = _RecordingConn()
    ts = datetime(2026, 6, 8, 10, 30)
    metrics = _sample_metrics(ts)

    write_metrics(conn, instrument_id=1, m=metrics)
    write_metrics(conn, instrument_id=1, m=metrics)

    sql = conn.cursor_obj.statements[0].lower()
    assert "on conflict" in sql
    assert "do update" in sql
    assert any("pg_notify" in s for s in conn.cursor_obj.statements)
