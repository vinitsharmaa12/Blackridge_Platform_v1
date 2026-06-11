# PRD 003b — Frontend: Auth, Watchlist & Live

**Status:** Ready · **Implements:** Cursor · **Reviews:** Claude · **Depends on:** PRD 003a, PRD 002 (WebSocket)

Layer multi-user + real-time onto the read-only dashboard from 003a.

## Goal / Non-goals
**Goal:** Add Supabase Auth, protected routes, an instrument switcher + watchlist, a Live toggle
(WebSocket), and the insights panel. **Non-goals:** new charts/metrics (those are 003a); alerts,
multi-instrument compare (later).

## Functional requirements
1. **Auth.** Supabase Auth (email/OAuth) via `@supabase/supabase-js` (auth only). Protected routes
   redirect unauthenticated users to login; attach the Supabase JWT to all API calls. `profiles`
   row auto-creates on signup (DB trigger). Handle token refresh / expiry mid-session.
2. **Instrument switcher + watchlist.** Pick active instrument; manage the caller's watchlist via
   `/me/watchlist` (GET/POST/DELETE). Default NIFTY.
3. **Live.** A **Live** toggle subscribes to `WS /ws/instruments/{symbol}`; on a new metrics event,
   refresh KPIs/signals/charts within seconds. Auto-reconnect with backoff; fall back to polling
   the `/latest` endpoint on drop.
4. **Insights panel.** Render `/insights` cards (system + the caller's own): title, narrative,
   sentiment, confidence, timestamp. Include a "Generate insight" button → `POST …/insights:generate`
   (202). This is the small **AI add-on** slot above the deterministic signals panel.
5. **States.** Reuse 003a loading/empty/error patterns for auth, watchlist, and live.

## Acceptance criteria
- [x] Unauthenticated users can't reach the dashboard; JWT attached to API calls; refresh/expiry handled.
- [x] Instrument switcher + watchlist work against the API and are scoped to the user.
- [x] Live toggle updates KPIs/signals/charts via WebSocket within seconds of a worker write;
      reconnects with backoff; falls back to polling.
- [x] Insights panel shows system + personal insights; generate button enqueues (202).
- [x] No service-role key in the client; strict TS passes; `next build` clean.

## Out of scope / future
Alerts/notifications, multi-instrument comparison, saved layouts, theming.
