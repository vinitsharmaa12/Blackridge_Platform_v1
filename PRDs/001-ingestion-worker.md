# PRD 001 — Ingestion Worker

**Status:** Ready · **Implements:** Cursor · **Reviews:** Claude · **Depends on:** PRD 000, `0001_init.sql` applied

## 1. Context
Today ingestion is three scripts glued by `orchestrator.py`: `Nifty_option.py` polls
NSE and writes JSON files, a converter makes CSVs, `Preprocessing.py` derives metrics,
and an HTML renderer runs. Output is flat files; the loop is a fragile subprocess chain.

We already have pure `core/` functions that turn a raw NSE JSON into DB rows. This PRD
replaces the whole file-based chain with **one scheduled worker** that writes straight
to Postgres.

## 2. Goal / Non-goals
**Goal:** A single long-running Python process that, on a schedule during market hours,
fetches the NSE option chain, normalizes + enriches it via `core/`, and writes
`option_snapshots` + `metrics` to Supabase — passing the previous snapshot so
`cog_shift`/`buildup` are real.

**Non-goals:** No API (PRD 002), no UI, no insight generation (PRD 004), no removal of
raw-JSON archival (keep it, see §3.6).

## 3. Functional requirements
1. **Scheduler.** Use APScheduler (`BackgroundScheduler` or `BlockingScheduler`). Run
   every `INGEST_INTERVAL_SECONDS` (default 180) only within market hours
   (`MARKET_OPEN`/`MARKET_CLOSE`, IST, configurable; default 09:15–15:35) on weekdays.
   Outside the window, idle (don't fetch).
2. **Fetch.** Move NSE fetching into `core/sources/nse.py`. Must:
   - Use a session that primes NSE cookies (GET the option-chain page before the API),
     realistic headers, timeout, and `tenacity` retry with backoff on 401/403/5xx/timeouts.
   - **Auto-resolve expiry**: call the chain, read `records.expiryDates`, pick the
     nearest expiry ≥ today (configurable to nearest weekly). Do **not** hardcode expiry.
   - Be instrument-parameterized: `fetch_chain(symbol: str, expiry: str | None) -> dict`.
3. **Process.** `normalize(raw)` → `Snapshot`; load the previous `Snapshot` for this
   instrument from the DB (most recent `option_snapshots` rows for the latest stored
   `time`) → `compute_metrics(snap, prev=prev)`.
4. **Persist.** `db.write(conn, instrument_id, snap, metrics_row)` — idempotent. Use the
   **service-role** DB connection. One transaction per snapshot.
5. **India VIX (optional, behind a flag).** If `FETCH_INDIA_VIX=true`, fetch India VIX
   and pass to `compute_metrics(india_vix=...)`. If it fails, log and continue with `None`.
6. **Raw archival (keep).** Optionally still write the raw JSON to `nifty_data/` (flag
   `ARCHIVE_RAW`, default true) as a cheap audit trail / replay source. Not the source of truth.
7. **Multi-instrument ready.** Driven by a config list of instruments (start: `["NIFTY"]`).
   Loop over instruments each tick. Adding one = adding a config entry, not code.
8. **Observability.** Structured logs per tick: symbol, expiry, ts, rows written, metrics
   summary (sentiment, pcr), duration. Increment simple counters for success/failure.

## 4. File layout
```
core/sources/__init__.py
core/sources/nse.py          # fetch_chain(), resolve_expiry(), cookie/session priming, retries
worker/__init__.py
worker/config.py             # pydantic-settings: intervals, market hours, instruments, flags
worker/ingest.py             # one tick: fetch→normalize→prev→enrich→write (per instrument)
worker/scheduler.py          # APScheduler wiring + market-hours guard; entrypoint `python -m worker`
worker/__main__.py           # runs scheduler.py
tests/test_nse_parsing.py    # parse a saved fixture from nifty_data/ → Snapshot
tests/test_ingest_tick.py    # tick logic with a fake source + fake/temp DB or mocked db.write
```
Retire after this lands (separate cleanup PR, not now): `orchestrator.py`,
`Nifty_option.py`, `convert_nifty_json_to_csv.py`, `Preprocessing.py`, HTML renderers.

## 5. Interfaces / contracts
- `fetch_chain(symbol, expiry=None) -> dict` returns the raw NSE JSON (same shape `core/normalize` expects: top-level `records.data`).
- `resolve_expiry(raw, mode="nearest") -> str` returns NSE-formatted expiry (e.g. `09-Jun-2026`).
- `load_prev_snapshot(conn, instrument_id) -> Snapshot | None` reconstructs the latest stored snapshot (or returns None on first run).
- Worker entrypoint: `python -m worker` starts the scheduler.

## 6. Edge cases & guardrails
- Empty/`{}` NSE response (seen in real data) → skip tick, log, no write.
- NSE rate-limiting/cookie expiry → retry with backoff; after N failures, skip tick.
- First ever run (no prev) → `prev=None`; `cog_shift`/`buildup` come out null (expected).
- Duplicate tick / same timestamp → idempotent writes make it a no-op.
- Clock/timezone: define and document whether stored `time` is IST or UTC; be consistent
  with what `core/normalize` already produces (NSE server timestamp).
- Worker must not crash on a single bad instrument/tick — fail soft, continue.

## 7. Acceptance criteria (reviewer checklist)
- [ ] `python -m worker` runs, ticks on schedule, idles outside market hours.
- [ ] Expiry is auto-resolved from `records.expiryDates`; nothing hardcoded.
- [ ] NSE fetch survives cookie priming + retries; verified against the live endpoint.
- [ ] Each tick writes `option_snapshots` + one `metrics` row; re-running is idempotent
      (row counts stable).
- [ ] `prev` is loaded from DB so `cog_shift`/`buildup` are non-null on the 2nd+ tick.
- [ ] Uses the service-role connection; respects RLS (authenticated read, service write).
- [ ] Adding a 2nd instrument is config-only (demonstrate with a second symbol, even if
      commented).
- [ ] Tests pass (`pytest`); `ruff` clean; new env vars in `.env.example`.

## 8. Out of scope / future
WebSocket push to clients (PRD 002 reads the DB), insight triggering (PRD 004 can be
invoked on session close), pg_partman migration (PRD 005 / when large).
