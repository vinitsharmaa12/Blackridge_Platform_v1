# Blackridge Platform — Architecture & Stack Recommendation

> Goal: turn the current single-user, CSV+HTML Nifty50 option-chain scripts into a
> multi-user platform that (1) stores time-series data properly, (2) generates
> agentic insights, and (3) visualizes metrics with a modern UX. Nifty50 is the
> first instrument; design assumes many more.

---

## 1. What exists today (and why it caps the product)

```
Nifty_option.py ──> nifty_data/*.json ──> convert_*.py ──> nifty_data_csv/*.csv
                                                                │
                                              Preprocessing.py ─┤──> preprocessed_output/*.csv
                                                                │
                                       metrics.py (COG, PCR, OI-flow, sentiment)
                                                                │
                                    latest_preprocessed_html.py ──> static *.html
        orchestrator.py = subprocess loop tying the above during market hours
```

**Limits:** CSVs can't be queried or joined across time; HTML is regenerated per run
(no interactivity, no per-user state); the scheduler is a fragile subprocess loop;
adding a second instrument means duplicating files. The *logic* in `metrics.py` is
solid and reusable — it just needs a real data + serving layer underneath it.

---

## 2. Recommended target architecture

```
 ┌─────────────┐   ┌──────────────────────┐   ┌─────────────────────────────┐
 │ Data sources│──>│ Ingestion workers     │──>│ Supabase Postgres           │
 │ NSE (+more) │   │ (FastAPI + scheduler) │   │  • raw snapshots             │
 └─────────────┘   │  fetch→normalize→store│   │  • computed metrics          │
                   └──────────┬───────────┘   │  • insights, users (RLS)     │
                              │               └──────────────┬──────────────┘
                   metrics.py (as a library)                 │
                              │                               │
                   ┌──────────▼───────────┐        ┌──────────▼──────────┐
                   │ Insights engine       │        │ FastAPI             │
                   │ (Agno/Claude + SQL     │        │ REST + WebSocket    │
                   │  tools over the DB)    │        │ + auth              │
                   └──────────┬───────────┘        └──────────┬──────────┘
                              └───────────writes insights─────┘
                                                              │
                                              ┌───────────────▼───────────────┐
                                              │ Next.js (App Router)           │
                                              │ shadcn/ui + Tailwind           │
                                              │ TradingView Lightweight Charts │
                                              │ + Recharts/visx                │
                                              └────────────────────────────────┘
```

---

## 3. Stack decisions (with the "why")

### Backend language — **Python 3 / FastAPI** ✅ (keep your preference)
Your scraping + all of `metrics.py` are already Python and *good*. FastAPI gives
typed Pydantic models, async I/O, auto OpenAPI docs (handy for the agent + frontend),
and native WebSocket for live updates. No reason to rewrite in Node.

### Data store — **Supabase (plain Postgres)**  (the most important choice)
The data is textbook time-series: one snapshot per (timestamp, symbol, strike, side).
- **Why not keep CSVs:** no querying, no cross-time joins, no concurrency, no multi-tenant.
- **Why Postgres over InfluxDB:** one DB for time-series **and** relational data
  (users, watchlists, insights), plus row-level security for multi-tenant, plus
  plain SQL — exactly what an agent can generate. InfluxDB would force a second
  store and a worse query story for joins/auth.
- **Why NOT TimescaleDB:** Supabase deprecated the `timescaledb` extension on
  Postgres 17 (the default for new projects); using it means pinning to PG15 and
  dropping it before any upgrade — a dead end. At our volume (~9M rows/yr for one
  instrument at 1-min cadence) plain Postgres with good indexes is plenty. The one
  thing Timescale uniquely offers — columnar compression — only matters at hundreds
  of millions of rows; if we ever get there, the answer is a dedicated Timescale
  Cloud instance for raw ticks, *not* pinning Supabase to old Postgres.
- **Scaling path:** when `option_snapshots` gets large, convert it to native
  Postgres range partitioning automated by **`pg_partman`** + **`pg_cron`**
  (Supabase's recommended replacement for hypertables). Staged in
  `db/migrations/0002_partitioning.sql` — not needed on day one.
- **Hosting:** Supabase (Postgres, auth, RLS, MCP already wired up).

Suggested core tables (see `db/migrations/0001_init.sql`):
- `option_snapshots`: ts, instrument, expiry, strike, CE/PE oi, oi_change, iv, ltp,
  volume, underlying — the raw per-strike grain.
- `metrics`: ts, instrument, pcr, ce_cog, pe_cog, atm_iv, max_pain, sentiment_score,
  support/resistance, … — the output of `metrics.py`, precomputed at ingest.
- `instruments`, `profiles`, `watchlists`, `insights`.

### Ingestion / scheduling — **APScheduler** now, **Arq + Redis** later
Replace `orchestrator.py`'s subprocess loop with a scheduled worker:
fetch → normalize → write `option_snapshots` → compute `metrics.py` → write `metrics`
→ push a WebSocket event. APScheduler is fine for one box; move to Arq (Redis) when
you fan out across many instruments. Wrap NSE calls in `tenacity` retries.

### Frontend — **Next.js + shadcn/ui + TradingView Lightweight Charts** ✅
- **Next.js (App Router)** as you wanted — multi-user, SSR for fast first paint,
  server actions/route handlers to talk to FastAPI.
- **shadcn/ui + Tailwind** for the app shell (dashboards, tables, filters).
- **Charts:** TradingView **Lightweight Charts** for price/OI candles & overlays
  (purpose-built for financial series, tiny, fast) + **Recharts** (or visx) for the
  general metric panels (PCR over time, sentiment gauge, OI-flow bars).
- **Live updates:** subscribe to the FastAPI WebSocket; revalidate on new snapshots.

### Auth & multi-tenancy
Supabase Auth or Clerk for users; enforce isolation with Postgres **row-level
security** keyed on `user_id`/`org_id`. Don't hand-roll JWT unless you must.

### Agentic insights — your endgame
Build an **insights engine** that treats the platform as tools, not as a chat bolt-on:
1. Deterministic layer: keep `metrics.py` as the ground truth (scores, S/R, COG).
2. Agent layer (Anthropic SDK / Agno): give the agent typed tools —
   `query_snapshots(sql)`, `get_metrics(symbol, window)`, `compare_sessions(...)` —
   so it reasons over real rows instead of hallucinating.
3. Output: agent writes a structured `insights` row (narrative + the metric values
   it cited + confidence). Frontend renders that next to the charts.
4. Schedule insight generation per session close (and on demand per user).
This keeps numbers trustworthy (code) and language flexible (LLM).

---

## 4. Suggested monorepo layout

```
blackridge/
├── apps/
│   ├── api/            # FastAPI: routes, ws, auth
│   └── web/            # Next.js frontend
├── packages/
│   ├── ingestion/      # scrapers + scheduler (was Nifty_option/orchestrator)
│   ├── metrics/        # metrics.py promoted to a tested library
│   └── insights/       # agentic insight generation
├── db/                 # SQL migrations (Supabase) + alembic for app tables
├── requirements.txt
└── ARCHITECTURE.md
```

---

## 5. Migration path (incremental, nothing thrown away)

1. **Stand up Supabase Postgres**; apply `db/migrations/0001_init.sql`.
2. **Backfill**: one-time script loads existing `nifty_data_csv/*.csv` into
   `option_snapshots` (your history is preserved, not lost).
3. **Refactor ingestion**: point the scraper at the DB instead of JSON/CSV files;
   compute `metrics.py` inline and store to `metrics`.
4. **FastAPI** read endpoints over the tables → kill the HTML renderers.
   See [docs/api.md](docs/api.md) for running the API and dev auth tokens.
5. **Next.js dashboard** consuming the API (this replaces the HTML UX).
6. **Insights engine** on top, writing to `insights`.
7. **Generalize to N instruments**: `symbol` is already a column — add rows, not files.

---

## 6. Why this is the right call (summary)

- **One DB (Supabase Postgres)** = time-series *and* relational *and* multi-tenant
  *and* SQL the agent can use. Single biggest unlock. `pg_partman` is the scale
  lever when needed — no vendor lock-in, no deprecated extension.
- **Python/FastAPI** keeps your existing, working logic and your stated preference.
- **Next.js + Lightweight Charts** gives the interactive, multi-user UX that static
  HTML can never reach.
- **metrics.py stays the source of truth**; the LLM narrates over real numbers, so
  insights are trustworthy and the platform scales to more instruments by adding
  rows, not files.

---

## 7. Metrics catalog (what to persist)

Two grains: **raw per-strike** (recompute anything later) + **one instrument-level
metrics row per snapshot** (fast reads, agent-friendly).

### Raw per-strike — `option_snapshots` (already collected)
OI, ΔOI, IV, LTP, volume, change, %change, buy/sell qty — for CE and PE — plus
underlying, expiry, strike.

### Instrument-level per snapshot — `metrics`
| Metric | Notes | Cost |
|---|---|---|
| PCR by OI | already computed | now |
| PCR by volume | divergence vs PCR-OI is a signal | now |
| CE/PE COG + COG shift | already computed | now |
| ATM strike + ATM IV | most-watched vol number | now |
| IV skew | `PE_IV − CE_IV` at equidistant OTM strikes; tail-risk | now |
| India VIX | NSE publishes separately; fear gauge | now (extra fetch) |
| ATM straddle / expected move | `ATM_CE_LTP + ATM_PE_LTP` → "market prices ±X" | now |
| Max Pain | strike minimizing writer payout | now |
| Net OI change (CE vs PE) | aggregate ΔOI | now |
| Total OI / volume (CE, PE) | index-level totals | now |
| Buildup label | price-vs-OI → Long/Short Buildup, Unwinding, Covering | now |
| Buy/sell qty imbalance | order-book pressure ratio | now |
| Support/Resistance (imm + major) | already computed | now |
| Sentiment score + label + drivers | already computed (`metrics.py`) | now |
| DTE | days-to-expiry — needed to normalize IV/straddle | now |
| IV rank / IV percentile | trailing-window — needs history | later |

### Next tier (not "basic")
Greeks (Delta/Gamma/Theta/Vega via Black-Scholes from IV+DTE), Gamma Exposure (GEX),
underlying OHLC + VWAP per interval (enables candlestick charts).

---

## 8. Supabase schema

See `db/migrations/`:
- `0001_init.sql` — core tables + RLS, runs on plain Postgres today.
- `0002_partitioning.sql` — converts `option_snapshots` to native Postgres range
  partitioning via `pg_partman` + `pg_cron`, with an optional `metrics_5m` rollup.
  Apply only when snapshot volume grows ("scale as we go"); not needed day one.

Market data tables (`instruments`, `option_snapshots`, `metrics`, `insights`) are
**shared, read-only to authenticated users**; only the service role (ingestion +
insights worker) writes. User-owned tables (`profiles`, `watchlists`) are isolated
per user via RLS on `auth.uid()`.
