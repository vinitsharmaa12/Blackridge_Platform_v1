# Blackridge Web (PRD 003a)

Next.js dashboard for NSE index-option analytics: KPIs, deterministic signals, charts,
option chain, watchlist, live WebSocket updates, and AI insights panel.

## Prerequisites

- Node 20+
- Running API (`uvicorn apps.api.main:app` on port 8000)
- Supabase Auth user (login page) or dev token flow via API

## Setup

```bash
cp .env.local.example .env.local
# Fill NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, NEXT_PUBLIC_API_URL
npm install
```

Regenerate API types after backend OpenAPI changes:

```bash
# From repo root, export schema then:
npm run generate:api
```

## Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) — redirects to `/i/NIFTY` after login.

## Integration gate (003a-8)

```bash
npm run verify
```

Manual smoke (API + worker/backfill must have data):

1. API health: `curl -s http://localhost:8000/health`
2. Log in at `/login`
3. `/i/NIFTY` shows KPI header, signals panel, all charts, option chain table
4. Snapshot scrubber changes chain/signals; null metrics show as "—"
5. Stop API → error state with retry; partial chain failure shows section error + toast
6. Watchlist add/remove; switch instruments via sidebar
7. Live toggle connects to `WS /ws/instruments/{symbol}?token=`; KPIs refresh on worker write
8. Generate insight returns 202 queued job

## Stack

Next.js App Router · TypeScript strict · Tailwind · shadcn/ui · TanStack Query ·
lightweight-charts · Recharts · Supabase Auth (JWT attached to API calls).
