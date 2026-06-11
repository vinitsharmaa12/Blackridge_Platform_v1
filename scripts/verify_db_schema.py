"""Verify Supabase schema for PRD 004 insight job queue (migrations 0003 + 0004).

    python -m scripts.verify_db_schema
    python -m scripts.verify_db_schema --smoke-insert
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_REQUIRED_COLUMNS = {
    "id",
    "instrument_id",
    "symbol",
    "user_id",
    "trigger_type",
    "session_date",
    "status",
    "created_at",
    "started_at",
    "completed_at",
    "error",
}
_REQUIRED_INDEXES = {
    "idx_insight_jobs_status_created",
    "idx_insight_jobs_session_close_dedup",
    "idx_insight_jobs_on_demand_dedup",
}
_REQUIRED_POLICIES = {
    "read own insight jobs",
    "enqueue on_demand jobs",
}


def verify(conn: psycopg.Connection, *, smoke_insert: bool) -> list[str]:
    errors: list[str] = []
    with conn.cursor() as cur:
        cur.execute(
            """
            select exists (
              select 1 from information_schema.tables
              where table_schema = 'public' and table_name = 'insight_jobs'
            )
            """
        )
        if not cur.fetchone()[0]:
            return ["missing table public.insight_jobs (apply db/migrations/0003_insight_jobs.sql)"]

        cur.execute(
            """
            select column_name from information_schema.columns
            where table_schema = 'public' and table_name = 'insight_jobs'
            """
        )
        columns = {row[0] for row in cur.fetchall()}
        missing_cols = _REQUIRED_COLUMNS - columns
        if missing_cols:
            errors.append(f"insight_jobs missing columns: {sorted(missing_cols)}")

        cur.execute(
            """
            select indexname from pg_indexes
            where schemaname = 'public' and tablename = 'insight_jobs'
            """
        )
        indexes = {row[0] for row in cur.fetchall()}
        missing_idx = _REQUIRED_INDEXES - indexes
        if missing_idx:
            errors.append(f"insight_jobs missing indexes: {sorted(missing_idx)}")

        cur.execute(
            """
            select relrowsecurity from pg_class
            where relname = 'insight_jobs'
              and relnamespace = 'public'::regnamespace
            """
        )
        if not cur.fetchone()[0]:
            errors.append("insight_jobs RLS is not enabled")

        cur.execute(
            """
            select policyname from pg_policies
            where schemaname = 'public' and tablename = 'insight_jobs'
            """
        )
        policies = {row[0] for row in cur.fetchall()}
        missing_policies = _REQUIRED_POLICIES - policies
        if missing_policies:
            errors.append(f"insight_jobs missing policies: {sorted(missing_policies)}")

        cur.execute(
            """
            select conname from pg_constraint
            where conrelid = 'public.insight_jobs'::regclass
              and contype = 'f'
              and pg_get_constraintdef(oid) like '%user_id%'
            """
        )
        if cur.fetchall():
            errors.append(
                "insight_jobs.user_id still has FK to auth.users "
                "(apply db/migrations/0004_insight_jobs_drop_user_fk.sql)"
            )

        if smoke_insert:
            cur.execute("select id from instruments where symbol = 'NIFTY' limit 1")
            row = cur.fetchone()
            if row is None:
                errors.append("instruments table missing NIFTY seed row")
            else:
                instrument_id = row[0]
                fake_user = uuid4()
                cur.execute(
                    """
                    insert into insight_jobs
                      (instrument_id, symbol, user_id, trigger_type, session_date, status)
                    values (%s, 'NIFTY', %s, 'on_demand', current_date, 'queued')
                    returning id
                    """,
                    (instrument_id, fake_user),
                )
                job_id = cur.fetchone()[0]
                cur.execute("delete from insight_jobs where id = %s", (job_id,))
                conn.rollback()

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify insight_jobs migrations 0003/0004")
    parser.add_argument(
        "--smoke-insert",
        action="store_true",
        help="Insert/delete an on_demand job with a synthetic user_id (no auth.users row)",
    )
    args = parser.parse_args(argv)
    load_dotenv()

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL is not set", file=sys.stderr)
        return 1

    with psycopg.connect(database_url) as conn:
        errors = verify(conn, smoke_insert=args.smoke_insert)

    if errors:
        for err in errors:
            print(f"FAIL: {err}", file=sys.stderr)
        return 1

    print("OK: insight_jobs schema matches migrations 0003 + 0004")
    if args.smoke_insert:
        print("OK: on_demand insert with synthetic user_id succeeded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
