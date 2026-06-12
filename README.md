# Blackridge Platform

Multi-user analytics for NSE index-option data: scheduled ingestion, computed metrics in
Supabase Postgres, a read-focused FastAPI backend, a Next.js dashboard (KPIs, signals,
charts, chain), and (planned) LLM-generated insights.

Nifty50 is instrument #1; `symbol` is a column — more instruments add rows, not files.

## Docs

| Doc | Contents |
|-----|----------|
| [docs/api.md](docs/api.md) | Backend API: auth, endpoints, WebSocket, **dev token mint** |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Stack decisions and data model |
| [AGENTS.md](AGENTS.md) | Quick brief for coding agents |
| [PRDs/](PRDs/) | Implementation specs (build order 001 → 005) |

## Prerequisites

- Python 3.13+
- Supabase project with `db/migrations/0001_init.sql` applied
- Copy [`.env.example`](.env.example) → `.env` and fill in `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_JWT_SECRET`

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run locally

**Backfill historical JSONs (optional):**

```bash
python -m scripts.backfill --dry-run   # parse only
python -m scripts.backfill             # write to DATABASE_URL
```

**Ingestion worker (live NSE → DB):**

```bash
python -m worker
```

**Backend API:**

```bash
uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000/docs](http://localhost:8000/docs) for OpenAPI.

### Dev auth token

Protected routes require a Supabase JWT. For local testing, enable the dev mint endpoint
(see [docs/api.md#dev-token-local-testing-only](docs/api.md#dev-token-local-testing-only)):

```bash
# .env
ENABLE_DEV_TOKEN=true
```

```bash
curl -s -X POST http://localhost:8000/dev/token \
  -H 'Content-Type: application/json' \
  -d '{"email":"dev@local.test"}' | jq -r .access_token
```

Use the token as `Authorization: Bearer <token>` on API calls or `?token=` on the WebSocket.
**Never set `ENABLE_DEV_TOKEN=true` in production.**

**Web dashboard (PRD 003a):**

```bash
cd apps/web
cp .env.local.example .env.local   # Supabase + NEXT_PUBLIC_API_URL
npm install
npm run dev
```

Integration gate: `npm run verify` in `apps/web`. See [apps/web/README.md](apps/web/README.md).

## Session snapshots (strategy spec)

Phase cards on the dashboard follow [`_ref/session_snap.py`](_ref/session_snap.py) IST windows:

| Phase | Window |
|-------|--------|
| Morning | 09:21 – 09:22 |
| Midday | 12:30 – 12:45 |
| Evening | 15:00 – 15:30 |

A phase is **populated** only when at least one metrics tick falls inside its window (last
tick wins). The morning window is one minute wide — the worker runs a **10s burst** from
`09:21–09:25` IST (`MORNING_BURST_*` in `.env`) plus a `09:21` anchor cron, matching
[`_ref/orchestrator.py`](_ref/orchestrator.py).

API: `GET /instruments/{symbol}/session-snapshots?date=YYYYMMDD` returns per-phase
`status` (`populated` / `pending` / `missed`). If the requested day has no captured phases,
the API falls back to the latest day with data (`date_fallback: true`).

## Test

```bash
pytest
ruff check core worker apps tests scripts metrics.py
```
