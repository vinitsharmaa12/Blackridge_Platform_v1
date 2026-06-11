# PRD 000 — System Overview & Conventions

> Shared context for all PRDs. Read before implementing any other PRD.

## 1. What the platform is
A multi-user analytics platform for NSE index-option data. It ingests option-chain
snapshots on a schedule, computes a rich set of metrics per snapshot, stores both in
Postgres, serves them through an API to a Next.js dashboard, and generates narrative
insights with an LLM agent. Nifty50 is instrument #1; the design generalizes to many
instruments (`symbol` is a column, not a file).

## 2. Current state (already built — DO NOT rewrite)
| Area | Files | Status |
|------|-------|--------|
| Schema | `db/migrations/0001_init.sql` | **applied to Supabase** |
| Scale path | `db/migrations/0002_partitioning.sql` | staged, not applied |
| Normalization | `core/normalize.py` | done, validated |
| Metric enrichment | `core/enrich.py` (+ reuses `metrics.py`) | done, validated |
| DB writer | `core/db.py` | done (needs live DB to exercise) |
| Backfill | `scripts/backfill.py` | done; dry-run passes (127 files) |
| Dev runner | `scripts/process_json.py` | done |
| Legacy (reference only) | `Nifty_option.py`, `orchestrator.py`, `convert_nifty_json_to_csv.py`, `Preprocessing.py`, `latest_preprocessed_*`, `session_snap*` | to be retired by PRD 001/002 |

## 3. Core API surface to build on
```python
# core/normalize.py
normalize(raw: dict, source_name: str = "") -> Snapshot
normalize_file(path) -> Snapshot
#   Snapshot(time: datetime, underlying: float|None, expiry: date|None, rows: list[StrikeRow])
#   Snapshot.dte -> int|None

# core/enrich.py
compute_metrics(snap: Snapshot, prev: Snapshot|None = None,
                india_vix: float|None = None) -> MetricsRow
#   MetricsRow.as_dict() -> dict matching the `metrics` table columns

# core/db.py
connect() -> context manager yielding psycopg.Connection   # uses DATABASE_URL
get_instrument_id(conn, symbol) -> int
write(conn, instrument_id, snap, metrics_row) -> int        # idempotent
```
`prev` is the previous snapshot for the same instrument — required for `cog_shift`
and `buildup` to be meaningful. The ingestion worker must load it from the DB.

## 4. Target stack (decided — see `ARCHITECTURE.md`)
- **DB:** Supabase (plain Postgres 17). No TimescaleDB (deprecated on PG17). Scale via
  `pg_partman` later. RLS on.
- **Backend:** Python 3.13, FastAPI, psycopg 3, APScheduler.
- **Frontend:** Next.js (App Router) + TypeScript + Tailwind + shadcn/ui +
  TradingView Lightweight Charts + Recharts + TanStack Query + supabase-js (auth).
- **Insights:** Anthropic SDK (Claude), optionally Agno; tools query Postgres.
- **Hosting:** Supabase (DB/auth) + Railway (Python services) + Vercel/Railway (web).

## 5. Data model (from 0001_init.sql)
- `instruments(id, symbol, name, type, ...)` — seeded with NIFTY.
- `option_snapshots(time, instrument_id, expiry, strike, underlying, ce_*, pe_*, source)`
  — raw per-strike grain. PK `(instrument_id, expiry, strike, time)`.
- `metrics(time, instrument_id, expiry, dte, underlying, pcr_oi, pcr_volume, ce_cog,
  pe_cog, cog_shift, atm_strike, atm_iv, iv_skew, india_vix, atm_straddle, expected_move,
  max_pain, total_*_oi, net_*_oi_change, total_*_volume, buy_sell_imbalance, buildup,
  immediate/major support/resistance, sentiment_score, sentiment_label, drivers jsonb)`
  — PK `(instrument_id, time)`.
- `insights(id, time, instrument_id, expiry, title, narrative, sentiment_label,
  confidence, cited_metrics jsonb, model, user_id)`.
- `profiles`, `watchlists` — per-user, RLS on `auth.uid()`.

**RLS contract:** market data (`instruments`, `option_snapshots`, `metrics`, `insights`)
is read-only to authenticated users; only the **service role** writes (workers use the
service-role connection). `profiles`/`watchlists` are owner-scoped.

## 6. Conventions (all PRDs)
- **Python:** full type hints; `ruff` clean; `pytest` for logic; functions in `core/`
  stay pure (no I/O). Config from env via `pydantic-settings`. Never print secrets.
- **TypeScript:** strict mode; server components by default; data fetching via TanStack
  Query; no business logic duplicated from the backend — consume the API.
- **DB writes:** always idempotent (ON CONFLICT). Workers connect with the service role.
- **Time:** store UTC-aware where possible; NSE timestamps are IST — keep them consistent
  and document the choice in code.
- **Errors:** ingestion and insight jobs must fail soft per-item and continue; log and move on.
- **Secrets/env:** `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
  `SUPABASE_ANON_KEY`, `ANTHROPIC_API_KEY`. Provide `.env.example` updates per PRD.

## 7. Definition of Done (every PRD)
- [ ] Meets all Functional Requirements and Acceptance Criteria in its PRD.
- [ ] Reuses `core/`/`metrics.py`; no duplicated logic.
- [ ] Typed, `ruff`-clean (Python) / strict-TS-clean (web); builds with no errors.
- [ ] Tests for new non-trivial logic; happy path + at least one edge case.
- [ ] No secrets committed; new env vars documented in `.env.example`.
- [ ] README/ARCHITECTURE updated if behavior or layout changed.
- [ ] PR is small and scoped to the PRD.
