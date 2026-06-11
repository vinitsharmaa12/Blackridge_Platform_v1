# PRD 003a — Frontend: Read-only Dashboard

**Status:** Ready · **Implements:** Cursor · **Reviews:** Claude · **Depends on:** PRD 002, PRD 002.5

First usable screen: a single-instrument dashboard that renders metrics + **signals** + chain
from the API. No auth flows beyond a basic gate, no watchlist, no live WebSocket (→ 003b).

## Goal / Non-goals
**Goal:** Render, for one instrument (default NIFTY), the KPIs, charts, option-chain table, and
the deterministic **Signals panel** (PRD 002.5) from the API, with a date/time picker (polled, not
live). **Non-goals:** auth/watchlist/live/personal insights (003b); any client-side metric math.

## Functional requirements
1. **Stack.** Next.js App Router + **TypeScript strict** + Tailwind + shadcn/ui + TanStack Query
   + `lightweight-charts` + Recharts. Server components by default; client components for charts.
2. **Typed API client** generated from the API's OpenAPI (`openapi-typescript`) — field names match
   the backend/DB exactly. Never recompute metrics in the browser.
3. **Sections:**
   - **KPI header** — underlying (+day change), sentiment gauge, PCR (OI & vol), max pain,
     expected move, DTE. From `/instruments/{symbol}/latest`.
   - **Signals panel (PRIMARY interpretation surface)** — render `/signals` (or the `signals`
     embedded in `/latest`) as ranked cards: title, plain-language `text`, direction color,
     strength, evidence on hover. `overall` shown on top. This is the headline read, not a chart.
   - **Price & levels chart** (lightweight-charts) — underlying over the session with immediate/
     major S/R bands.
   - **OI-by-strike** (Recharts) — CE vs PE OI across strikes, ATM marked.
   - **PCR & sentiment trend** (Recharts) — over the selected range.
   - **IV skew** — IV across strikes (CE vs PE), ATM IV + skew highlighted.
   - **Option-chain table** — per-strike `/chain` at the selected timestamp, OI heat-mapped, ATM row highlighted.
4. **Time controls.** Date/session picker + snapshot scrubber. Data fetched via TanStack Query.
5. **States.** Loading skeletons, empty (market closed / no data), error toasts. Null metrics
   (`india_vix`, early `cog_shift`) render as "—".
6. **Access.** A simple auth gate is acceptable (full auth UX is 003b); no service-role key in client.

## Acceptance criteria
- [x] Dashboard renders all sections for NIFTY from live API data (no mock data in the prod path).
- [x] **Signals panel is the primary read**, sourced from `/signals` (or `/latest.signals`); cards
      show direction/strength/evidence; `overall` first.
- [x] No metric recomputed client-side; types derived from the API OpenAPI contract.
- [x] Charts interactive; loading/empty/error states present; null values render gracefully.
- [x] Strict TS passes; `next build` clean.

## Out of scope (→ 003b)
Auth flows, instrument switcher + watchlist, live WebSocket, personal insights, "Generate insight".
