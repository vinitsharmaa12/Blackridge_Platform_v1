# Backend API (PRD 002)

FastAPI read service under `apps/api/`. Serves instruments, metrics time-series, option chains,
insights, and watchlists. Workers own all market-data writes; the API verifies Supabase JWTs
and queries Postgres with `role=authenticated` so RLS applies.

**Interactive docs:** [http://localhost:8000/docs](http://localhost:8000/docs) (when running)

## Environment

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | yes | Supabase Postgres connection string (same as workers) |
| `SUPABASE_URL` | yes | Project URL, e.g. `https://<ref>.supabase.co` |
| `SUPABASE_JWT_SECRET` | yes | JWT secret from Supabase → Project Settings → API |
| `WEB_ORIGIN` | no | CORS origin (default `http://localhost:3000`) |
| `ENABLE_DEV_TOKEN` | no | `true` to mount `POST /dev/token` (local only; default `false`) |
| `DEV_TOKEN_TTL_SECONDS` | no | Dev token lifetime in seconds (default `3600`) |

See [`.env.example`](../.env.example) for the full list.

## Authentication

All data endpoints require:

```
Authorization: Bearer <supabase_jwt>
```

The API validates `aud=authenticated`, `iss={SUPABASE_URL}/auth/v1`, and signature via
`SUPABASE_JWT_SECRET`. Personal routes (watchlist) are scoped by `auth.uid()` through
Postgres RLS.

In production, the Next.js app (PRD 003) obtains tokens from **Supabase Auth** via
supabase-js — not from this API.

---

## Dev token (local testing only)

When `ENABLE_DEV_TOKEN=true`, the API mounts an unauthenticated endpoint that mints
Supabase-compatible JWTs for `/docs`, curl, and WebSocket testing.

**Security:** The route is **not registered** when `ENABLE_DEV_TOKEN` is `false` (default).
Do not enable in production.

### `POST /dev/token`

Mint a bearer token. No auth required (only available when dev mode is on).

**Request body (optional):**

```json
{
  "user_id": "11111111-1111-1111-1111-111111111111",
  "email": "dev@local.test"
}
```

Defaults match the values above if the body is omitted or `{}`.

**Response:**

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### Examples

**Mint and call a protected route:**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/dev/token \
  -H 'Content-Type: application/json' \
  -d '{"email":"dev@local.test"}' | jq -r .access_token)

curl -s http://localhost:8000/instruments \
  -H "Authorization: Bearer $TOKEN" | jq
```

**Swagger UI:** Click **Authorize**, paste `Bearer <access_token>` (or just the token,
depending on the UI version).

**WebSocket:**

```
ws://localhost:8000/ws/instruments/NIFTY?token=<access_token>
```

**Custom user (e.g. watchlist RLS tests):**

```bash
curl -s -X POST http://localhost:8000/dev/token \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"22222222-2222-2222-2222-222222222222","email":"alice@local.test"}'
```

---

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | no | DB connectivity check |
| `POST` | `/dev/token` | no | Mint dev JWT (`ENABLE_DEV_TOKEN=true` only) |
| `GET` | `/instruments` | yes | List active instruments |
| `GET` | `/instruments/{symbol}/latest` | yes | Latest metrics + OI summary |
| `GET` | `/instruments/{symbol}/signals` | yes | Ranked signal cards (`at=latest` or ISO timestamp) |
| `GET` | `/instruments/{symbol}/metrics` | yes | Metrics time-series (`from`, `to`, `fields`) |
| `GET` | `/instruments/{symbol}/chain` | yes | Option chain at `at=latest` or ISO timestamp |
| `GET` | `/instruments/{symbol}/insights` | yes | Recent insights (`limit`) |
| `GET` | `/instruments/{symbol}/insights/job` | yes | Today's on-demand job status (`queued`/`running`/`done`/`failed`) |
| `POST` | `/instruments/{symbol}/insights:generate` | yes | Start async insight generation (202; runs in API process) |
| `GET` | `/me/watchlist` | yes | Caller's watchlist |
| `POST` | `/me/watchlist` | yes | Add symbol to watchlist |
| `DELETE` | `/me/watchlist/{symbol}` | yes | Remove symbol from watchlist |
| `WS` | `/ws/instruments/{symbol}?token=` | token query | Live metrics push |

Field names on response models match DB columns (see PRD 002 / OpenAPI).

## Run

```bash
uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000
```

## Live updates

After each metrics write, the ingestion worker emits `NOTIFY metrics_new` on Postgres.
The WebSocket listener fans out to subscribed clients; if LISTEN fails, it falls back to
polling `max(time)` every few seconds.
