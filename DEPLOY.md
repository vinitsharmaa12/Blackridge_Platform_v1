# Deployment — Blackridge Platform

Topology: **Supabase** (Postgres + Auth) · **Railway** (API + worker) · **Vercel** (web).

## Prerequisites

- Supabase project with `db/migrations/0001_init.sql` applied
- Migrations `0003_insight_jobs.sql` + `0004_insight_jobs_drop_user_fk.sql` applied
  (`python -m scripts.verify_db_schema --smoke-insert`)
- Railway project linked: `railway link --project BlackRidge-Platform`
- Railway CLI authenticated: `railway whoami`

## Worker (Railway) — slice 1

Long-running ingestion scheduler. No public HTTP port.

### 1. Create the service

```bash
railway add --service worker
railway service link worker
```

In the Railway dashboard for **worker**:

- **Settings → Config file path:** `worker/railway.toml`
- **Settings → Source:** connect this GitHub repo (or deploy with `railway up` from repo root)

Or apply build config via CLI (service already created as `worker`):

```bash
railway service link worker
railway environment link production
railway environment edit --json <<'JSON'
{"services":{"3ac203e4-29ab-48b1-a90c-77946dd542f1":{"build":{"builder":"DOCKERFILE","dockerfilePath":"worker/Dockerfile"},"deploy":{"startCommand":"python -m worker","restartPolicyType":"ON_FAILURE","restartPolicyMaxRetries":10}}}}
JSON
```

Replace the service UUID if you recreate the service (`railway service list --json`).

### 2. Set environment variables

Use the **service-role** Supabase Postgres URI for `DATABASE_URL`. Never commit secrets.

| Variable | Required | Notes |
|----------|----------|-------|
| `DATABASE_URL` | yes | Direct Postgres URI (service role) |
| `INGEST_INTERVAL_SECONDS` | no | Default `180` |
| `MARKET_OPEN` / `MARKET_CLOSE` | no | IST, default `09:15` / `15:35` |
| `INSTRUMENTS` | no | Default `NIFTY` |
| `ARCHIVE_RAW` | no | Keep `false` in prod |
| `NSE_TIMEOUT` / `NSE_MAX_RETRIES` | no | Defaults `15` / `3` |
| `OPENROUTER_API_KEY` | for session-close insights | Worker enqueues + runs insights after close |
| `INSIGHTS_MODEL_CHEAP` / `INSIGHTS_MODEL_PREMIUM` | for session-close insights | See `.env.example` |
| `ANTHROPIC_API_KEY` | optional | Native premium path |

Set from local `.env` (secrets via stdin):

```bash
railway service link worker
set -a && source .env && set +a
printf '%s' "$DATABASE_URL" | railway variable set DATABASE_URL --stdin
railway variable set INGEST_INTERVAL_SECONDS="$INGEST_INTERVAL_SECONDS"
railway variable set MARKET_OPEN="$MARKET_OPEN" MARKET_CLOSE="$MARKET_CLOSE"
railway variable set INSTRUMENTS="$INSTRUMENTS" ARCHIVE_RAW=false
# Repeat for insight keys if session-close insights are enabled
```

### 3. Deploy

From repo root (linked to **worker** service):

```bash
railway service link worker
railway up --detach -m "worker: initial deploy"
```

Or push to the connected GitHub branch if CI deploy is enabled.

### 4. Verify

**Build locally (optional):**

```bash
docker build -f worker/Dockerfile -t blackridge-worker .
docker run --rm --env-file .env blackridge-worker python -m worker --once
```

**Production smoke test** (Railway shell or one-off run):

```bash
railway run --service worker python -m worker --once
```

**During market hours (IST, Mon–Fri):** Railway logs should show `scheduler_tick` every
`INGEST_INTERVAL_SECONDS`. Confirm new rows in Supabase `metrics`.

**Outside market hours:** logs show idle; no crash loop.

### 5. Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| Build fails on `pip wheel` | Pin mismatch — image uses Python 3.13 |
| `401/403` from NSE | Datacenter IP blocked — test with `railway run … --once` |
| No ticks during market hours | Wrong `TZ` (image sets `Asia/Kolkata`) or bad `DATABASE_URL` |
| Session-close insights fail | Missing `OPENROUTER_API_KEY` / model env vars |

---

## API (Railway) — slice 2

FastAPI read API with `/health` for Railway health checks. Public HTTPS domain required for
the web dashboard (slice 3).

### 1. Create the service

```bash
railway add --service api
railway service link api
```

In the Railway dashboard for **api**:

- **Settings → Config file path:** `apps/api/railway.toml`
- **Settings → Networking:** generate a public domain (e.g. `api-production.up.railway.app`)

Or apply build config via CLI:

```bash
railway service link api
railway environment link production
API_ID=$(railway service list --json | python3 -c "import json,sys; print(next(s['id'] for s in json.load(sys.stdin) if s['name']=='api'))")
railway environment edit --json <<JSON
{"services":{"${API_ID}":{"build":{"builder":"DOCKERFILE","dockerfilePath":"apps/api/Dockerfile"},"deploy":{"startCommand":"python -m apps.api","healthcheckPath":"/health","healthcheckTimeout":30,"restartPolicyType":"ON_FAILURE","restartPolicyMaxRetries":10}}}}
JSON
```

The JSON patch requires the **service UUID**, not the name `api`. UUID for `api` in this project:
`d2ed2efc-0a6d-451c-8e04-e8844702a75f` (re-run `railway service list --json` if you recreate the service).

### 2. Set environment variables

| Variable | Required | Notes |
|----------|----------|-------|
| `DATABASE_URL` | yes | Same Supabase Postgres URI as worker |
| `SUPABASE_URL` | yes | Project URL (JWT issuer validation) |
| `SUPABASE_JWT_SECRET` | yes | JWT secret from Supabase project settings |
| `WEB_ORIGIN` | yes | Production web origin for CORS (Vercel URL, slice 3) |
| `ENABLE_DEV_TOKEN` | yes | **`false` in production** |
| `OPENROUTER_API_KEY` | for on-demand insights | Background job processing on generate |
| `INSIGHTS_MODEL_*` | for on-demand insights | See `.env.example` |

Railway injects `PORT` at runtime; the API reads `PORT` first (falls back to `API_PORT` / 8000).
**Do not set `API_PORT` on the Railway `api` service** — it breaks health checks.

```bash
railway service link api
set -a && source .env && set +a
printf '%s' "$DATABASE_URL" | railway variable set DATABASE_URL --stdin
printf '%s' "$SUPABASE_JWT_SECRET" | railway variable set SUPABASE_JWT_SECRET --stdin
railway variable set SUPABASE_URL="$SUPABASE_URL"
railway variable set WEB_ORIGIN="https://your-app.vercel.app"
railway variable set ENABLE_DEV_TOKEN=false
```

### 3. Deploy

```bash
railway service link api
railway up --detach -m "api: initial deploy"
```

### 4. Verify

**Build locally (optional):**

```bash
docker build -f apps/api/Dockerfile -t blackridge-api .
docker run --rm -p 8000:8000 --env-file .env -e PORT=8000 blackridge-api
curl -s http://localhost:8000/health
```

**Production:**

```bash
curl -s https://<your-api-domain>/health
# {"status":"ok","db":"ok"}

curl -s -o /dev/null -w "%{http_code}" https://<your-api-domain>/instruments
# 401 without Authorization header
```

### 5. Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| Health check failing | `DATABASE_URL` wrong or Supabase unreachable from Railway |
| CORS errors from web | `WEB_ORIGIN` doesn't match exact Vercel URL (scheme + host) |
| 401 on all routes | Missing/invalid `Authorization: Bearer <supabase-jwt>` |
| Insight generate 500 | Missing `OPENROUTER_API_KEY` / model env on **api** service |

---

## Web (Vercel) — slice 3

Next.js dashboard in `apps/web/`. Uses Supabase Auth (anon key) and the Railway API
(`NEXT_PUBLIC_*` only — no service-role key in the browser).

### 1. Railway API public URL (prerequisite)

Generate a public domain for the **api** service if you do not have one yet:

```bash
railway service link api
# Railway dashboard → api → Settings → Networking → Generate Domain
```

Note the HTTPS URL (e.g. `https://api-production-xxxx.up.railway.app`).

### 2. Create the Vercel project

1. [vercel.com/new](https://vercel.com/new) → import this GitHub repo.
2. **Root Directory:** `apps/web` (required — monorepo).
3. Framework preset: **Next.js** (auto-detected).
4. **Build Command:** `npm run build` (default; see `apps/web/vercel.json`).
5. **Install Command:** `npm ci`.

Or link via CLI from repo root:

```bash
cd apps/web
npx vercel link
npx vercel env pull .env.local   # optional: sync dashboard vars locally
```

### 3. Environment variables (Vercel dashboard)

Set for **Production** (and Preview if you use PR previews):

| Variable | Example | Notes |
|----------|---------|-------|
| `NEXT_PUBLIC_SUPABASE_URL` | `https://vfzcctbxwezubhqyqcns.supabase.co` | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | `eyJ...` | Anon key only |
| `NEXT_PUBLIC_API_URL` | `https://<api>.up.railway.app` | Railway API HTTPS URL |

No trailing slash on `NEXT_PUBLIC_API_URL`. WebSocket live mode uses `wss://` automatically.

### 4. Supabase Auth redirect URLs

Supabase dashboard → **Authentication → URL Configuration**:

| Setting | Value |
|---------|-------|
| **Site URL** | `https://<your-app>.vercel.app` |
| **Redirect URLs** | `https://<your-app>.vercel.app/**` |

Add preview URLs if needed: `https://*.vercel.app/**`

### 5. Wire CORS on the API

After the first Vercel deploy, copy the production URL and update Railway **api**:

```bash
railway service link api
railway variable set WEB_ORIGIN="https://<your-app>.vercel.app"
```

Redeploy is automatic when variables change. `WEB_ORIGIN` must match exactly
(scheme + host, no trailing slash).

### 6. Deploy

Push to the connected branch, or:

```bash
cd apps/web
npx vercel --prod
```

Build fails fast if `NEXT_PUBLIC_*` vars are missing on Vercel (`next.config.ts` check).

### 7. Verify

```bash
cd apps/web && npm run verify   # local gate before push
```

Production smoke:

1. Open `https://<your-app>.vercel.app/login` — Supabase login loads.
2. After login → `/i/NIFTY` dashboard with KPIs/charts.
3. Browser devtools → Network: API calls go to Railway URL, not localhost.
4. Live toggle connects via `wss://` to the same API host.
5. Generate insight → 202 (requires insight env on **api** service).

### 8. Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| Build fails: missing env | Set all three `NEXT_PUBLIC_*` in Vercel |
| Login redirect loop | Supabase Site URL / Redirect URLs mismatch |
| CORS / blocked fetch | `WEB_ORIGIN` on API ≠ exact Vercel URL |
| API calls to localhost | `NEXT_PUBLIC_API_URL` not set on Vercel |
| WebSocket fails | API must be HTTPS; check Railway api domain + WSS |

---

## Scale storage

When `option_snapshots` is large, follow `db/migrations/0002_partitioning.sql` on a staging
branch first (destructive table swap). Never run blind on prod.
