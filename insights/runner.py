"""Insight job queue consumer and persistence."""
from __future__ import annotations

import logging
import os
from datetime import date, datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import psycopg
from psycopg.types.json import Json

from core.db import connect, get_instrument_id
from insights.agent import run_agent
from insights.config import InsightsSettings, get_insights_settings
from insights.llm import build_client
from insights.router import select_model
from insights.schemas import AgentRunResult, InsightOutput, TaskType

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


def _session_date(now: datetime | None = None) -> date:
    ts = now or datetime.now(tz=IST)
    return ts.astimezone(IST).date()


def _ensure_database_url(settings: InsightsSettings) -> None:
    os.environ["DATABASE_URL"] = settings.database_url


def enqueue_job(
    conn: psycopg.Connection,
    *,
    symbol: str,
    trigger_type: str,
    user_id: UUID | None,
    session_date: date | None = None,
) -> UUID | None:
    """Insert a queued job; returns None if duplicate (idempotent)."""
    instrument_id = get_instrument_id(conn, symbol.upper())
    day = session_date or _session_date()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into insight_jobs
                  (instrument_id, symbol, user_id, trigger_type, session_date, status)
                values (%s, %s, %s, %s, %s, 'queued')
                returning id
                """,
                (instrument_id, symbol.upper(), user_id, trigger_type, day),
            )
            row = cur.fetchone()
        return row[0] if row else None
    except psycopg.errors.UniqueViolation:
        conn.rollback()
        logger.info(
            "insight_job_duplicate symbol=%s trigger=%s session_date=%s user=%s",
            symbol,
            trigger_type,
            day,
            user_id,
        )
        return None


def insight_already_written(
    conn: psycopg.Connection,
    *,
    instrument_id: int,
    session_date: date,
    trigger_type: str,
    user_id: UUID | None,
) -> bool:
    with conn.cursor() as cur:
        if trigger_type == "session_close":
            cur.execute(
                """
                select 1 from insights
                where instrument_id = %s
                  and user_id is null
                  and (time at time zone 'Asia/Kolkata')::date = %s
                limit 1
                """,
                (instrument_id, session_date),
            )
        else:
            cur.execute(
                """
                select 1 from insights
                where instrument_id = %s
                  and user_id = %s
                  and (time at time zone 'Asia/Kolkata')::date = %s
                limit 1
                """,
                (instrument_id, user_id, session_date),
            )
        return cur.fetchone() is not None


def write_insight(
    conn: psycopg.Connection,
    *,
    instrument_id: int,
    output: InsightOutput,
    model_id: str,
    user_id: UUID | None,
    expiry: date | None = None,
) -> UUID:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into insights
              (instrument_id, expiry, title, narrative, sentiment_label,
               confidence, cited_metrics, model, user_id)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            returning id
            """,
            (
                instrument_id,
                expiry,
                output.title,
                output.narrative,
                output.sentiment_label,
                output.confidence,
                Json(output.cited_metrics),
                model_id,
                user_id,
            ),
        )
        row = cur.fetchone()
    if row is None:
        raise RuntimeError("failed to insert insight")
    return row[0]


def reset_job_for_retry(conn: psycopg.Connection, job_id: UUID) -> bool:
    """Reset a stale/failed/done job to queued so process_job can run again."""
    with conn.cursor() as cur:
        cur.execute(
            """
            update insight_jobs
            set status = 'queued',
                error = null,
                started_at = null,
                completed_at = null
            where id = %s
              and status in ('running', 'failed', 'done')
            returning id
            """,
            (job_id,),
        )
        return cur.fetchone() is not None


def reset_job_for_retry_by_id(job_id: UUID) -> bool:
    """Service-role wrapper for API retry before background processing."""
    cfg = get_insights_settings()
    _ensure_database_url(cfg)
    with connect() as conn:
        return reset_job_for_retry(conn, job_id)


def _mark_job(
    conn: psycopg.Connection,
    job_id: UUID,
    *,
    status: str,
    error: str | None = None,
) -> None:
    with conn.cursor() as cur:
        if status == "running":
            cur.execute(
                """
                update insight_jobs
                set status = %s, started_at = now(), error = null
                where id = %s
                """,
                (status, job_id),
            )
        else:
            cur.execute(
                """
                update insight_jobs
                set status = %s, completed_at = now(), error = %s
                where id = %s
                """,
                (status, error, job_id),
            )


def _load_job(conn: psycopg.Connection, job_id: UUID) -> dict[str, Any] | None:
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute("select * from insight_jobs where id = %s", (job_id,))
        return cur.fetchone()


def process_job(
    job_id: UUID,
    settings: InsightsSettings | None = None,
) -> AgentRunResult | None:
    """Run one queued insight job. Fail-soft — no hallucinated insight on error."""
    cfg = settings or get_insights_settings()
    _ensure_database_url(cfg)

    with connect() as conn:
        job = _load_job(conn, job_id)
        if job is None:
            logger.warning("insight_job_missing id=%s", job_id)
            return None
        if job["status"] not in ("queued", "failed"):
            logger.info("insight_job_skip id=%s status=%s", job_id, job["status"])
            return None

        instrument_id = int(job["instrument_id"])
        if insight_already_written(
            conn,
            instrument_id=instrument_id,
            session_date=job["session_date"],
            trigger_type=job["trigger_type"],
            user_id=job["user_id"],
        ):
            _mark_job(conn, job_id, status="done")
            logger.info("insight_already_exists job=%s", job_id)
            return None

        _mark_job(conn, job_id, status="running")
        task_type = (
            TaskType.SESSION_CLOSE
            if job["trigger_type"] == "session_close"
            else TaskType.SNAPSHOT_SUMMARY
        )
        primary = select_model(task_type, cfg)
        client = build_client(primary, cfg)

        try:
            result = run_agent(
                conn,
                job["symbol"],
                client,
                cfg,
                task_type=task_type,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("insight_job_error id=%s", job_id)
            _mark_job(conn, job_id, status="failed", error=str(exc))
            return None

        if result.output is None:
            _mark_job(conn, job_id, status="failed", error=result.error)
            return result

        expiry_val: date | None = None
        cited = result.output.cited_metrics
        metrics = cited.get("metrics") if isinstance(cited.get("metrics"), dict) else cited
        if isinstance(metrics, dict) and metrics.get("expiry"):
            try:
                expiry_val = date.fromisoformat(str(metrics["expiry"])[:10])
            except ValueError:
                expiry_val = None

        write_insight(
            conn,
            instrument_id=instrument_id,
            output=result.output,
            model_id=result.model_id,
            user_id=job["user_id"],
            expiry=expiry_val,
        )
        _mark_job(conn, job_id, status="done")
        logger.info(
            "insight_written job=%s symbol=%s model=%s escalated=%s",
            job_id,
            job["symbol"],
            result.model_id,
            result.escalated,
        )
        return result


def process_queued_jobs(settings: InsightsSettings | None = None, *, limit: int = 10) -> int:
    cfg = settings or get_insights_settings()
    _ensure_database_url(cfg)
    processed = 0
    with connect() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                """
                select id from insight_jobs
                where status = 'queued'
                order by created_at asc
                limit %s
                """,
                (limit,),
            )
            job_ids = [row["id"] for row in cur.fetchall()]

    for job_id in job_ids:
        process_job(job_id, cfg)
        processed += 1
    return processed


def run_session_close(settings: InsightsSettings | None = None) -> int:
    """Enqueue session-close jobs for all active instruments."""
    cfg = settings or get_insights_settings()
    _ensure_database_url(cfg)
    day = _session_date()
    enqueued = 0
    with connect() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute("select symbol from instruments where active = true order by symbol")
            symbols = [row["symbol"] for row in cur.fetchall()]
        for symbol in symbols:
            job_id = enqueue_job(
                conn,
                symbol=symbol,
                trigger_type="session_close",
                user_id=None,
                session_date=day,
            )
            if job_id:
                enqueued += 1
    logger.info("session_close_enqueued count=%d", enqueued)
    process_queued_jobs(cfg, limit=enqueued or 10)
    return enqueued


def is_session_close_window(
    now: datetime,
    *,
    market_close: str = "15:35",
    window_minutes: int = 5,
) -> bool:
    """True once per day in the first N minutes after market close (IST, weekdays)."""
    local = now.astimezone(IST)
    if local.weekday() >= 5:
        return False
    hour, minute = map(int, market_close.split(":"))
    close_minutes = hour * 60 + minute
    current_minutes = local.hour * 60 + local.minute
    return close_minutes <= current_minutes < close_minutes + window_minutes
