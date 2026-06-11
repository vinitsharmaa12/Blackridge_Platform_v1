# AGENTS.md — Blackridge Platform

Portable context for AI coding agents (Cursor and others). Detailed specs live in `PRDs/`;
Cursor-specific rules live in `.cursor/rules/`. This file is the quick brief.

## What this is
A multi-user analytics platform for NSE index-option data. It ingests option-chain snapshots
on a schedule, computes metrics per snapshot, stores both in Supabase Postgres, serves them via
an API to a Next.js dashboard, and generates narrative insights with a Claude agent. Nifty50 is
instrument #1; `symbol` is a column — more instruments = more rows, not more files.

## Golden rules
1. **Reuse, don't rewrite.** `core/normalize.py`, `core/enrich.py`, `core/db.py`, `metrics.py`
   are built and validated. Never duplicate metric logic.
2. **Specs are authoritative.** Implement against the target PRD's Functional Requirements and
   Acceptance Criteria. Read `PRDs/000-overview-and-conventions.md` first.
3. **Secrets via env only.** The Supabase service-role key lives only in workers — never in the
   API or browser. Workers write; API/web read with least privilege. RLS is on.
4. **Idempotent + typed.** DB writes use ON CONFLICT. Python is fully type-hinted/`ruff`-clean;
   TypeScript is strict.
5. **Small slices.** Build incrementally; keep PRs scoped to one PRD/slice; test as you go.

## Current state (built — reuse base)
| Area | Files | Status |
|------|-------|--------|
| Schema | `db/migrations/0001_init.sql` | applied to Supabase |
| Scale path | `db/migrations/0002_partitioning.sql` | staged (pg_partman; **no TimescaleDB**) |
| Normalize | `core/normalize.py` | done |
| Enrich (metrics) | `core/enrich.py` (+ `metrics.py`) | done |
| DB writer | `core/db.py` | done |
| Backfill / dev runner | `scripts/backfill.py`, `scripts/process_json.py` | done |
| Backend API | `apps/api/` | done (PRD 002) |
| Deterministic signals | `core/signals.py`, `GET /signals` | done (PRD 002.5) |
| Web dashboard | `apps/web/` | done (PRD 003a + 003b auth/live) |
| Insights engine | `insights/`, `POST …/insights:generate` | done (PRD 004) |
| Legacy (reference, to retire) | `orchestrator.py`, `Nifty_option.py`, converters, HTML renderers | — |

## core/ API surface
```python
normalize(raw, source_name="") -> Snapshot          # core/normalize.py
compute_metrics(snap, prev=None, india_vix=None) -> MetricsRow   # core/enrich.py
connect(); get_instrument_id(conn, symbol); write(conn, instrument_id, snap, metrics_row)  # core/db.py
```
`prev` is the previous snapshot for the instrument — required for `cog_shift`/`buildup`.

## Stack
Supabase (Postgres 17 + Auth, RLS) · Python 3.13 + FastAPI + psycopg 3 + APScheduler ·
Next.js App Router + TS + Tailwind + shadcn/ui + TanStack Query + lightweight-charts + Recharts ·
Anthropic SDK (Claude) for insights · Railway + Vercel hosting.

## Build order
PRD 001 (ingestion) → 002 (API) → 003 (frontend) → 004 (insights) → 005 (deploy/ops).

## Verify locally
- `python -m scripts.process_json` — normalize + enrich real JSONs (no DB).
- `python -m scripts.backfill --dry-run` — parse all `nifty_data/` (no DB).
- `python -m scripts.verify_db_schema --smoke-insert` — confirm migrations 0003/0004 on Supabase.
- `docker build -f worker/Dockerfile -t blackridge-worker .` — worker image (PRD 005 slice 1).
- `docker build -f apps/api/Dockerfile -t blackridge-api .` — API image (PRD 005 slice 2).
- `python -m apps.api` — ASGI server (uses `API_PORT` or Railway `PORT`).
- `python -m worker --once` — single ingestion tick to DB (bypasses market-hours guard).
- `python -m insights --process-jobs` — drain queued insight jobs (needs `0003_insight_jobs.sql`).
- Apply `db/migrations/0003_insight_jobs.sql` before first generate; set `OPENROUTER_API_KEY` + model env vars.
- `uvicorn apps.api.main:app --reload` — API at :8000; see [docs/api.md](docs/api.md).
- Dev JWT: set `ENABLE_DEV_TOKEN=true`, then `POST /dev/token` (local only).
- Web: `cd apps/web && npm run dev` — see [apps/web/README.md](apps/web/README.md).
- Web gate: `cd apps/web && npm run verify`.
- Vercel deploy: root directory `apps/web`, env from `apps/web/.env.local.example` — see [DEPLOY.md](DEPLOY.md).
