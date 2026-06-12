"""Session phase snapshots matching _ref/session_snap.py windows and fields."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from datetime import time as dtime
from typing import Any, Literal
from zoneinfo import ZoneInfo

from core.strike_window import DEFAULT_TOP_N, DEFAULT_WINDOW, top_oi_from_chain_dicts

IST = ZoneInfo("Asia/Kolkata")
PhaseStatus = Literal["populated", "pending", "missed"]

# Inclusive start, exclusive end — IST wall-clock labels on stored timestamps.
MORNING_START = dtime(9, 21)
MORNING_END = dtime(9, 22)
MIDDAY_START = dtime(12, 30)
MIDDAY_END = dtime(12, 45)
EVENING_START = dtime(15, 0)
EVENING_END = dtime(15, 30)

SESSION_WINDOWS: dict[str, tuple[dtime, dtime]] = {
    "morning": (MORNING_START, MORNING_END),
    "midday": (MIDDAY_START, MIDDAY_END),
    "evening": (EVENING_START, EVENING_END),
}

WINDOW_LABELS: dict[str, str] = {
    "morning": "09:21–09:22 IST",
    "midday": "12:30–12:45 IST",
    "evening": "15:00–15:30 IST",
}

PHASE_OPEN_LABELS: dict[str, str] = {
    "morning": "09:21 IST",
    "midday": "12:30 IST",
    "evening": "15:00 IST",
}


@dataclass(frozen=True)
class SessionPhaseSnapshot:
    timestamp: str
    underlying: str
    top1ce_strike: str
    top1ce_oi: str
    top2ce_strike: str
    top2ce_oi: str
    top3ce_strike: str
    top3ce_oi: str
    top1pe_strike: str
    top1pe_oi: str
    top2pe_strike: str
    top2pe_oi: str
    top3pe_strike: str
    top3pe_oi: str
    pcr: str
    overall_ce_oi: str
    overall_pe_oi: str
    overall_ce_volume: str
    overall_pe_volume: str

    def as_dict(self) -> dict[str, str]:
        return {
            "timestamp": self.timestamp,
            "underlying": self.underlying,
            "top1ce_strike": self.top1ce_strike,
            "top1ce_oi": self.top1ce_oi,
            "top2ce_strike": self.top2ce_strike,
            "top2ce_oi": self.top2ce_oi,
            "top3ce_strike": self.top3ce_strike,
            "top3ce_oi": self.top3ce_oi,
            "top1pe_strike": self.top1pe_strike,
            "top1pe_oi": self.top1pe_oi,
            "top2pe_strike": self.top2pe_strike,
            "top2pe_oi": self.top2pe_oi,
            "top3pe_strike": self.top3pe_strike,
            "top3pe_oi": self.top3pe_oi,
            "pcr": self.pcr,
            "overall_ce_oi": self.overall_ce_oi,
            "overall_pe_oi": self.overall_pe_oi,
            "overall_ce_volume": self.overall_ce_volume,
            "overall_pe_volume": self.overall_pe_volume,
        }


@dataclass(frozen=True)
class SessionPhaseResult:
    snapshot: SessionPhaseSnapshot
    status: PhaseStatus
    window_label: str


_EMPTY = SessionPhaseSnapshot(
    timestamp="N/A",
    underlying="N/A",
    top1ce_strike="N/A",
    top1ce_oi="N/A",
    top2ce_strike="N/A",
    top2ce_oi="N/A",
    top3ce_strike="N/A",
    top3ce_oi="N/A",
    top1pe_strike="N/A",
    top1pe_oi="N/A",
    top2pe_strike="N/A",
    top2pe_oi="N/A",
    top3pe_strike="N/A",
    top3pe_oi="N/A",
    pcr="N/A",
    overall_ce_oi="N/A",
    overall_pe_oi="N/A",
    overall_ce_volume="N/A",
    overall_pe_volume="N/A",
)


def _row_time(ts: datetime) -> dtime:
    return ts.time()


def pick_metrics_in_window(
    rows: Sequence[dict[str, Any]],
    window_start: dtime,
    window_end: dtime,
) -> dict[str, Any] | None:
    """Return the last metrics row whose clock time falls in [start, end)."""
    matching = [
        row
        for row in rows
        if window_start <= _row_time(row["time"]) < window_end
    ]
    return matching[-1] if matching else None


def phase_status(
    metrics_row: dict[str, Any] | None,
    window_start: dtime,
    session_date: date,
    *,
    now: datetime | None = None,
) -> PhaseStatus:
    if metrics_row is not None:
        return "populated"
    now_ist = (now or datetime.now(tz=IST)).astimezone(IST)
    if session_date > now_ist.date():
        return "pending"
    if session_date < now_ist.date():
        return "missed"
    if now_ist.time() < window_start:
        return "pending"
    return "missed"


def count_populated_phases(metrics_rows: Sequence[dict[str, Any]]) -> int:
    return sum(
        1
        for start, end in SESSION_WINDOWS.values()
        if pick_metrics_in_window(metrics_rows, start, end) is not None
    )


def _format_top(entries: list[dict[str, float | int]], prefix: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for i in range(3):
        strike_key = f"top{i + 1}{prefix}_strike"
        oi_key = f"top{i + 1}{prefix}_oi"
        if i < len(entries):
            out[strike_key] = str(int(entries[i]["strike"]))
            out[oi_key] = str(int(entries[i]["oi"]))
        else:
            out[strike_key] = "N/A"
            out[oi_key] = "N/A"
    return out


def _simple_pcr(pe_oi: int, ce_oi: int) -> str:
    if ce_oi == 0:
        return "N/A"
    return f"{pe_oi / ce_oi:.2f}"


def build_phase_snapshot(
    metrics_row: dict[str, Any] | None,
    chain_rows: Sequence[dict[str, object]],
) -> SessionPhaseSnapshot:
    if metrics_row is None:
        return _EMPTY

    underlying = metrics_row.get("underlying")
    top_ce = top_oi_from_chain_dicts(
        chain_rows,
        float(underlying) if underlying is not None else None,
        side="ce",
        n=DEFAULT_TOP_N,
        window=DEFAULT_WINDOW,
    )
    top_pe = top_oi_from_chain_dicts(
        chain_rows,
        float(underlying) if underlying is not None else None,
        side="pe",
        n=DEFAULT_TOP_N,
        window=DEFAULT_WINDOW,
    )

    ce_oi = int(metrics_row.get("total_ce_oi") or 0)
    pe_oi = int(metrics_row.get("total_pe_oi") or 0)
    ts = metrics_row["time"]
    timestamp = ts.isoformat() if isinstance(ts, datetime) else str(ts)

    fields: dict[str, str] = {
        "timestamp": timestamp,
        "underlying": str(metrics_row.get("underlying", "N/A")),
        "pcr": _simple_pcr(pe_oi, ce_oi),
        "overall_ce_oi": str(ce_oi),
        "overall_pe_oi": str(pe_oi),
        "overall_ce_volume": str(int(metrics_row.get("total_ce_volume") or 0)),
        "overall_pe_volume": str(int(metrics_row.get("total_pe_volume") or 0)),
    }
    fields.update(_format_top(top_ce, "ce"))
    fields.update(_format_top(top_pe, "pe"))
    return SessionPhaseSnapshot(**fields)


def build_session_snapshots(
    metrics_rows: Sequence[dict[str, Any]],
    chain_by_time: dict[datetime, list[dict[str, object]]],
    *,
    session_date: date | None = None,
    now: datetime | None = None,
) -> dict[str, dict[str, str | PhaseStatus]]:
    """Build morning/midday/evening snapshots from a day's metrics + chain rows."""
    phases: dict[str, dict[str, str | PhaseStatus]] = {}
    for name, (start, end) in SESSION_WINDOWS.items():
        metrics_row = pick_metrics_in_window(metrics_rows, start, end)
        chain_rows: list[dict[str, object]] = []
        if metrics_row is not None:
            chain_rows = chain_by_time.get(metrics_row["time"], [])
        snapshot = build_phase_snapshot(metrics_row, chain_rows)
        status = phase_status(
            metrics_row,
            start,
            session_date or date.today(),
            now=now,
        )
        phases[name] = {
            **snapshot.as_dict(),
            "status": status,
            "window_label": WINDOW_LABELS[name],
        }
    return phases


def parse_session_date(value: str) -> date:
    """Parse YYYYMMDD session date."""
    if len(value) != 8 or not value.isdigit():
        raise ValueError("date must be YYYYMMDD")
    return date(int(value[:4]), int(value[4:6]), int(value[6:8]))


def format_session_date(value: date) -> str:
    return value.strftime("%Y%m%d")


def day_bounds(session_day: date) -> tuple[datetime, datetime]:
    """Naive datetime bounds for one IST-labeled calendar day."""
    day_start = datetime(session_day.year, session_day.month, session_day.day)
    return day_start, day_start + timedelta(days=1)
