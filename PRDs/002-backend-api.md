# PRD 002 — Backend API (FastAPI)

**Status:** Ready · **Implements:** Cursor · **Reviews:** Claude · **Depends on:** PRD 001 (data in DB)

## 1. Context
The Next.js dashboard (PRD 003) and insights engine (PRD 004) need a typed contract over
the data, plus live updates. We expose a FastAPI service for reads, auth verification, and
a WebSocket. (Supabase PostgREST exists, but a thin API gives us typed models, WebSocket
fan-out, and a place for insight orchestration without leaking service-role keys to the client.)

## 2. Goal / Non-goals
**Goal:** A read-focused FastAPI app serving instruments, metrics time-series, option-chain
snapshots, and insights, with Supabase-JWT auth and a WebSocket that pushes new metrics.

**Non-goals:** No writes to market data from the API (workers own that). No UI. No insight
generation logic (PRD 004) — the API only *reads* the `insights` table (and may expose an
on-demand trigger endpoint that enqueues a job).

## 3. Functional requirements
1. **App skeleton.** FastAPI under `apps/api/`. ASGI via uvicorn. CORS for the web origin.
   Settings via `pydantic-settings`. Health endpoint `GET /health` (checks DB connectivity).
2. **DB access.** Async connection pool (`psycopg_pool` or asyncpg). Read queries only.
   Use a least-privilege role (anon/authenticated semantics); never expose service-role.
3. **Auth.** Verify Supabase JWT (Authorization: Bearer). Reject unauthenticated requests
   to data endpoints. Resolve `user_id` for personal endpoints (watchlists, personal insights).
4. **Endpoints** (all JSON, Pydantic response models):
   - `GET /instruments` → list of instruments.
   - `GET /instruments/{symbol}/latest` → latest `metrics` row + light snapshot summary
     (underlying, atm, top OI strikes).
   - `GET /instruments/{symbol}/metrics?from=&to=&fields=` → time-series of metrics rows
     (used by charts). Support down-sampling/limit; default last trading day.
   - `GET /instruments/{symbol}/chain?at=latest|<ts>` → per-strike option chain
     (`option_snapshots`) for one timestamp, ordered by strike.
   - `GET /instruments/{symbol}/insights?limit=` → recent insights (system + caller's own).
   - `GET /me/watchlist` / `POST` / `DELETE` → manage the caller's watchlist.
   - `POST /instruments/{symbol}/insights:generate` → enqueue an on-demand insight job
     (PRD 004 worker consumes it). Returns 202 + job id. (Stub the queue if 004 not built yet.)
5. **WebSocket.** `WS /ws/instruments/{symbol}` → emits a message whenever a new `metrics`
   row lands for that symbol. Implement via Postgres `LISTEN/NOTIFY` (worker `NOTIFY`s after
   write) or short-interval polling of `max(time)` as a fallback. Auth the socket via token.
6. **Pagination & validation.** Time params validated; sane defaults and max ranges to
   protect the DB. 404 for unknown symbol; 422 for bad params.

## 4. File layout
```
apps/api/main.py            # app factory, CORS, router include, lifespan (pool)
apps/api/config.py          # settings (DB url, supabase jwt secret/jwks, web origin)
apps/api/db.py              # async pool + query helpers (read-only)
apps/api/auth.py            # Supabase JWT verification dependency
apps/api/models.py          # Pydantic response models (Instrument, MetricsРow, ChainRow, Insight)
apps/api/routers/instruments.py
apps/api/routers/metrics.py
apps/api/routers/chain.py
apps/api/routers/insights.py
apps/api/routers/watchlist.py
apps/api/ws.py              # websocket + LISTEN/NOTIFY
tests/api/                  # endpoint tests with a seeded test DB or fixtures
```

## 5. Data contracts
Response models mirror the DB columns (PRD 000 §5). Example `MetricsRow` fields: `time,
underlying, pcr_oi, pcr_volume, ce_cog, pe_cog, cog_shift, atm_strike, atm_iv, iv_skew,
india_vix, atm_straddle, expected_move, max_pain, total_ce_oi, total_pe_oi,
net_ce_oi_change, net_pe_oi_change, buy_sell_imbalance, buildup, immediate_support,
major_support, immediate_resistance, major_resistance, sentiment_score, sentiment_label,
drivers`. Keep field names identical to the DB so the frontend and agent share one vocabulary.
Document the contract via FastAPI's auto OpenAPI (`/docs`); the agent (PRD 004) and web
(PRD 003) both consume it.

## 6. Edge cases & guardrails
- Unknown/inactive symbol → 404. Empty range → empty list, not error.
- Very large ranges → enforce max window + row cap; encourage `from/to`.
- WS reconnection: client may reconnect; server must not leak listeners/connections.
- Auth: expired/invalid JWT → 401; never fall back to service-role for user requests.
- Read endpoints must not be able to mutate market data.

## 7. Acceptance criteria (reviewer checklist)
- [ ] `GET /health` returns ok and verifies DB connectivity.
- [ ] All endpoints return typed models; `/docs` (OpenAPI) is complete and accurate.
- [ ] Auth enforced; unauthenticated data requests are 401; personal endpoints scoped to `auth.uid()`.
- [ ] Metrics/chain queries are parameterized, indexed (use existing indexes), and bounded.
- [ ] WebSocket emits on new metrics within a few seconds of a worker write.
- [ ] No service-role key reachable by clients; CORS limited to the web origin.
- [ ] Tests pass; `ruff` clean; env vars documented.

## 8. Out of scope / future
Rate limiting/quotas, caching layer (Redis), GraphQL, server-driven aggregation beyond
what `metrics`/`metrics_5m` already provide.
