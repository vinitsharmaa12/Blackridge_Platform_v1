# PRD 005 — Deployment & Ops

**Status:** Ready · **Implements:** Cursor · **Reviews:** Claude · **Depends on:** PRD 001–004

## 1. Context
Pull the pieces (DB, worker, API, web, insights) into a deployable, observable system with
sane secrets, CI, and a documented path to scale storage.

## 2. Goal / Non-goals
**Goal:** Reproducible deployment of all services with managed config/secrets, basic CI,
scheduled insight runs, and a runbook for the `pg_partman` scale step.

**Non-goals:** No multi-region/HA, no autoscaling tuning, no k8s. Keep it simple and cheap.

## 3. Functional requirements
1. **Topology.**
   - **Supabase** — Postgres + Auth (already). Apply `0001_init.sql`; `0002_partitioning.sql`
     only when needed.
   - **Railway** — the Python **ingestion worker** (long-running) and **insights runner**
     (scheduled/queue) and the **FastAPI** service. (Railway MCP is available.)
   - **Web** — Next.js on Vercel (or Railway). Env: API base URL, Supabase anon key/url.
2. **Config & secrets.** All via platform env vars; nothing committed. Document the full
   matrix in `.env.example` and a `DEPLOY.md`: `DATABASE_URL` (service role for workers),
   `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `ANTHROPIC_API_KEY`,
   `WEB_ORIGIN`, market-hours/interval flags. Workers use service-role; API uses least-priv.
3. **Scheduling.** Worker self-schedules (APScheduler, PRD 001). Insight session-close runs
   via the runner's scheduler or Supabase `pg_cron` calling the API trigger. Pick one and document.
4. **CI.** GitHub Actions: on PR run `ruff` + `pytest` (Python) and `tsc --noEmit` + `next build`
   (web). Block merge on failure. Optional: build Docker images for the Python services.
5. **Containerization.** Multi-stage Dockerfiles for `apps/api` and `worker`/`insights`
   (slim base, non-root, pinned deps). Web uses the platform's native build.
6. **Observability & health.** `/health` wired to platform health checks. Structured logs
   shipped to the platform log view. Minimal uptime alert on worker (no ticks in market hours = alert).
7. **Backups & data.** Rely on Supabase backups; document retention. Keep raw-JSON archive
   policy (PRD 001 `ARCHIVE_RAW`) and the `option_snapshots` retention story (ties to 0002).

## 4. File layout
```
apps/api/Dockerfile
worker/Dockerfile            # also runs insights runner (or a separate image)
.github/workflows/ci.yml
DEPLOY.md                    # topology, env matrix, deploy steps, runbooks
railway.json / service config (as needed)
```

## 5. Runbooks (document in DEPLOY.md)
- **First deploy:** apply schema → set secrets → deploy worker → verify ticks → deploy API →
  deploy web → smoke test.
- **Backfill prod:** run `python -m scripts.backfill` once against prod `DATABASE_URL`.
- **Scale storage:** when `option_snapshots` is large, follow `0002_partitioning.sql` in a
  maintenance window on a branch/staging first (it swaps the table).
- **Add an instrument:** add to the worker's instrument config; no deploy code change.

## 6. Edge cases & guardrails
- Never put service-role keys in the web app or client bundles.
- Migration `0002` is destructive (table swap) — staging + backup first; never run blind on prod.
- Worker timezone must match market hours (IST); verify on the host.
- CI must run on the same Python (3.13) and Node versions as prod.

## 7. Acceptance criteria (reviewer checklist)
- [ ] All services deploy from the repo with only env config; no secrets in git.
- [ ] CI runs lint + tests + web build on PRs and blocks on failure.
- [ ] Worker runs on schedule in prod and writes to Supabase; `/health` green on API.
- [ ] Insight session-close job runs on schedule and writes `insights`.
- [ ] `DEPLOY.md` documents env matrix + all runbooks (incl. the 0002 scale step).
- [ ] Service-role usage confined to workers; web/API use least-privilege keys.

## 8. Out of scope / future
HA/multi-region, autoscaling, blue-green deploys, cost dashboards, dedicated Timescale Cloud
for raw ticks (only if volume ever demands it).
