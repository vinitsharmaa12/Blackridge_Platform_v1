# PRD 003 — Frontend Dashboard (Next.js)

**Status:** Ready · **Implements:** Cursor · **Reviews:** Claude · **Depends on:** PRD 002

## 1. Context
The current UX is regenerated static HTML — no interactivity, no per-user state, no live
data. This replaces it with a multi-user Next.js dashboard that visualizes the metrics
and option-chain data and surfaces agent insights.

## 2. Goal / Non-goals
**Goal:** A logged-in, multi-user dashboard that, per instrument, shows live + historical
metrics as interactive charts, the option chain, and narrative insights.

**Non-goals:** No data computation in the frontend (consume the API; never re-derive
metrics). No direct service-role DB access. No charting of things the API doesn't serve.

## 3. Functional requirements
1. **Stack.** Next.js (App Router) + TypeScript (strict) + Tailwind + shadcn/ui +
   TanStack Query + `lightweight-charts` (price/levels/OI candles) + Recharts (metric
   panels) + `@supabase/supabase-js` (auth only). Server components by default; client
   components for charts/live.
2. **Auth.** Supabase Auth (email/OAuth). Protected routes; unauthenticated → login.
   Attach the Supabase JWT to API calls. On signup, a `profiles` row already auto-creates (DB trigger).
3. **Instrument switcher / watchlist.** Pick the active instrument; manage watchlist via
   the API (`/me/watchlist`). Default: NIFTY.
4. **Dashboard (per instrument).** Sections:
   - **Header KPIs:** underlying (+day change), sentiment gauge (`sentiment_score`/label),
     PCR (OI & volume), max pain, expected move (ATM straddle), DTE.
   - **Price & levels chart** (Lightweight Charts): underlying over the session with
     immediate/major support & resistance as horizontal bands.
   - **OI-by-strike** (Recharts bar): CE vs PE OI across strikes for the selected timestamp,
     ATM marked.
   - **PCR & sentiment over time** (Recharts lines) for the session/date range.
   - **IV skew / smile**: IV across strikes (CE vs PE), ATM IV + skew highlighted.
   - **Option-chain table:** per-strike `option_snapshots` for the selected timestamp,
     OI heat-mapped, sortable; ATM row highlighted.
   - **Insights panel:** cards from `/insights` (title, narrative, sentiment, confidence,
     timestamp). "Generate insight" button → calls the on-demand trigger (202).
5. **Time controls.** Date / session picker + a scrubber over snapshots; a **Live** toggle
   that subscribes to `WS /ws/instruments/{symbol}` and updates KPIs/charts on new metrics.
6. **States.** Loading skeletons, empty states (no data / market closed), and error toasts.
   Responsive; usable on a laptop first, tolerable on tablet.

## 4. File layout
```
apps/web/                       # Next.js app
  app/(auth)/login/page.tsx
  app/(app)/layout.tsx          # auth guard + shell (nav, instrument switcher)
  app/(app)/i/[symbol]/page.tsx # main dashboard
  components/kpis/*             # KpiHeader, SentimentGauge
  components/charts/PriceLevelsChart.tsx     # lightweight-charts
  components/charts/OiByStrike.tsx           # recharts
  components/charts/PcrSentimentTrend.tsx    # recharts
  components/charts/IvSkew.tsx               # recharts
  components/chain/OptionChainTable.tsx
  components/insights/InsightsPanel.tsx
  lib/api.ts                    # typed fetch client (from OpenAPI or hand-typed)
  lib/supabase.ts               # auth client
  lib/ws.ts                     # websocket hook
  hooks/useMetrics.ts, useChain.ts, useInsights.ts   # TanStack Query
```

## 5. Data contracts
Types mirror PRD 002 response models; generate from the API's OpenAPI if possible
(`openapi-typescript`) so field names stay identical to the DB vocabulary. Never invent
fields the API doesn't return.

## 6. Edge cases & guardrails
- Market closed / no data for range → clear empty state, not spinners forever.
- Missing metric values (e.g. `india_vix` null, early-session `cog_shift` null) → render
  gracefully ("—"), don't crash.
- WS drops → auto-reconnect with backoff; fall back to polling the latest endpoint.
- Auth expiry mid-session → refresh token or redirect to login.
- Large chains/long ranges → paginate/limit via the API; don't fetch everything.

## 7. Acceptance criteria (reviewer checklist)
- [ ] Auth works; unauthenticated users can't reach the dashboard; JWT attached to API calls.
- [ ] Dashboard renders all sections for NIFTY from live API data (no mock data in prod path).
- [ ] Charts are interactive (hover/zoom where applicable) and read only API-served fields.
- [ ] Live toggle updates KPIs/charts via WebSocket within seconds of a worker write.
- [ ] Instrument switcher + watchlist function against the API.
- [ ] No metric is recomputed client-side; types derived from the API contract.
- [ ] Strict TS passes; `next build` clean; loading/empty/error states present.

## 8. Out of scope / future
Alerts/notifications, multi-instrument comparison view, mobile-first redesign, theming,
saved layouts. (Capture as later PRDs.)
