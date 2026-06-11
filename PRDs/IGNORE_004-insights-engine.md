# PRD 004 — Insights Engine (Agentic)

**Status:** Ready · **Implements:** Cursor · **Reviews:** Claude · **Depends on:** PRD 001, PRD 002

## 1. Context
The endgame is agentic insight generation over the stored data. The deterministic metrics
(`metrics.py` / `core/enrich.py`) are the ground truth; an LLM agent narrates over *real*
numbers it pulls via tools, and writes structured rows to the `insights` table. This keeps
numbers trustworthy (code) and language flexible (LLM) — the agent must never invent values.

## 2. Goal / Non-goals
**Goal:** A job that, on session close (and on demand), runs a Claude agent with DB-backed
tools to produce a concise, cited market insight per instrument, persisted to `insights`.

**Non-goals:** No trading advice/recommendations to buy/sell. No metric computation in the
agent (it reads precomputed metrics). No UI (PRD 003 renders the rows).

## 3. Functional requirements
1. **Trigger.** (a) Scheduled at session close per instrument; (b) on-demand via the API's
   `POST /instruments/{symbol}/insights:generate` (PRD 002), consumed from a simple queue
   (DB table or Redis/Arq). Idempotent per (instrument, session/date, trigger-type).
2. **Agent.** Anthropic SDK (Claude — default `claude-opus-4-x` for quality, configurable to
   Sonnet for cost). Use **prompt caching** for the static system prompt + schema/tool docs.
   Optionally orchestrate via Agno.
3. **Tools (read-only, typed) — the agent reasons only over what these return:**
   - `get_latest_metrics(symbol)` → latest `metrics` row.
   - `get_metric_series(symbol, field, from, to)` → time-series for trend description.
   - `get_chain(symbol, at)` → per-strike snapshot (top OI strikes, ATM area).
   - `compare_sessions(symbol, date_a, date_b)` → metric deltas between two sessions.
   Implement tools as thin wrappers over the same queries as PRD 002 (or call the API).
4. **Output (structured).** The agent returns: `title`, `narrative` (tight, a few sentences),
   `sentiment_label`, `confidence` (0–1), and `cited_metrics` (the exact values/rows it used).
   Persist to `insights` with `model` set. `narrative` must reference the cited numbers.
5. **Grounding guardrails.** System prompt forbids fabricating numbers; every quantitative
   claim must come from a tool result echoed in `cited_metrics`. If data is missing, say so
   and lower confidence rather than guess. No buy/sell directives — describe positioning/structure.
6. **Cost/limits.** Bound tool-call count and tokens per run; log model, tokens, latency, cost.

## 4. File layout
```
insights/__init__.py
insights/tools.py            # typed DB-backed tools (reuse core/db queries)
insights/agent.py            # Claude client, system prompt (cached), tool loop, structured output
insights/prompts/system.md   # cached system prompt: role, rules, schema vocabulary, output format
insights/runner.py           # trigger entrypoints (scheduled + queue consumer) → write insights
insights/schemas.py          # pydantic: InsightOutput (title, narrative, sentiment_label, confidence, cited_metrics)
tests/insights/test_tools.py
tests/insights/test_agent_contract.py   # mocked model: asserts output shape + grounding rule
```

## 5. Data contracts
Writes `insights` (PRD 000 §5). `cited_metrics` is JSON: the field/values and timestamps the
agent pulled. `confidence` ∈ [0,1]. `user_id` null for scheduled/system insights; set for
on-demand requests tied to a user.

## 6. Edge cases & guardrails
- Sparse/early data (null `cog_shift`, missing `india_vix`) → acknowledge, lower confidence.
- Tool returns empty → agent states limitation; never invents a value.
- Model/tool error → retry with backoff; on persistent failure, write no insight (don't write a hallucinated one) and log.
- Duplicate trigger → idempotent; don't write twice for the same (instrument, session, type).
- Prompt-injection via data fields → treat tool data as untrusted content, not instructions.

## 7. Acceptance criteria (reviewer checklist)
- [ ] Scheduled + on-demand triggers both produce an `insights` row.
- [ ] Every quantitative claim in `narrative` appears in `cited_metrics` (grounding verified by test).
- [ ] No buy/sell recommendations; descriptive positioning language only.
- [ ] Prompt caching enabled for the static system/tooling context; tokens/cost logged.
- [ ] Tools are read-only and reuse existing queries; no metric recomputed in the agent.
- [ ] Confidence + model persisted; missing-data path lowers confidence instead of guessing.
- [ ] Tests pass (incl. a mocked-model contract test); `ruff` clean; env vars documented.

## 8. Out of scope / future
Multi-instrument cross-market insights, backtesting insight accuracy, user-tunable insight
styles, streaming insights to the UI. (Later PRDs.)
