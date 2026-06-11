# PRD 004 — Insights Engine (Agentic)

**Status:** Ready · **Implements:** Cursor · **Reviews:** Claude · **Depends on:** PRD 001, PRD 002

## 1. Context
The endgame is agentic insight generation over the stored data. The deterministic metrics
(`metrics.py` / `core/enrich.py`) are the ground truth; an LLM agent narrates over *real*
numbers it pulls via tools, and writes structured rows to the `insights` table. This keeps
numbers trustworthy (code) and language flexible (LLM) — the agent must never invent values.

## 2. Goal / Non-goals
**Goal:** A job that, on session close (and on demand), runs an LLM agent (tiered,
provider-agnostic models) with DB-backed tools to produce a concise, cited market insight per
instrument, persisted to `insights`.

**Non-goals:** No trading advice/recommendations to buy/sell. No metric computation in the
agent (it reads precomputed metrics). No UI (PRD 003 renders the rows). Not locked to a single
model/provider.

## 2.5 Model strategy — tiered & provider-agnostic
Start cheap; reserve premium (Claude) for genuinely complex reasoning. Route by task complexity
so cost tracks value as we scale.

- **Gateway:** default to **OpenRouter** (one key, OpenAI-compatible API) so models are swappable
  by **config, not code**. Keep an optional **Anthropic-native path** for the premium tier where
  Claude features matter (prompt caching, native tool-use) — chosen by a config flag.
- **Tiers (model ids live in env/config, never hardcoded):**
  - **`cheap`** — a fast inexpensive model (e.g. `google/gemini-flash` via OpenRouter). For
    simple/minimal tasks: per-snapshot one-liners, classification/tagging, short factual
    summaries, the triage/routing step.
  - **`premium`** — Claude (`anthropic/claude-sonnet…/opus…`) for complex multi-step synthesis:
    the session-close narrative, cross-session comparison, nuanced positioning reads.
- **Routing:** `select_model(task_type) -> ModelSpec` maps task → tier → configured model.
  **Cheap-first**, and **escalate to premium** when the cheap model's structured output fails
  schema validation or returns confidence below a configurable threshold.
- **Abstraction:** a thin `LLMClient` interface with `OpenRouterClient` (OpenAI-style tools) and
  `AnthropicClient` (native tools + caching) implementations. Agent code stays model-agnostic;
  the client normalizes tool-calling and structured output.
- **Trade-off (document in code):** OpenRouter gives cost control + flexibility but uneven
  prompt-caching support; use the Anthropic-native path for the premium tier when caching on the
  long static prompt matters.

## 3. Functional requirements
1. **Trigger.** (a) Scheduled at session close per instrument; (b) on-demand via the API's
   `POST /instruments/{symbol}/insights:generate` (PRD 002), consumed from a simple queue
   (DB table or Redis/Arq). Idempotent per (instrument, session/date, trigger-type).
2. **Agent.** Model-agnostic agent loop over the `LLMClient` (see §2.5). Selects the tier via
   `select_model(task_type)`; cheap-first with escalation. Premium tier uses **prompt caching**
   (Anthropic-native path) for the static system prompt + schema/tool docs. Optionally Agno.
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
6. **Cost/limits.** Bound tool-call count and tokens per run; log **model id + tier**, tokens,
   latency, and cost **per run and per tier** (so cheap-vs-premium spend is visible).
7. **Config/env.** All model selection via env: `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`,
   `INSIGHTS_MODEL_CHEAP`, `INSIGHTS_MODEL_PREMIUM`, `INSIGHTS_PREMIUM_NATIVE` (bool — use the
   Anthropic-native path for premium), `ANTHROPIC_API_KEY` (only when native), and
   `INSIGHTS_ESCALATE_CONFIDENCE` (threshold). No model ids or keys in code. Document in `.env.example`.

## 4. File layout
```
insights/__init__.py
insights/llm.py              # LLMClient interface + OpenRouterClient + AnthropicClient (normalizes tools/output)
insights/router.py           # select_model(task_type) -> ModelSpec; tier config; escalation policy
insights/tools.py            # typed DB-backed tools (reuse core/db queries)
insights/agent.py            # model-agnostic tool loop + structured output (uses llm.py + router.py)
insights/prompts/system.md   # cached system prompt: role, rules, schema vocabulary, output format
insights/runner.py           # trigger entrypoints (scheduled + queue consumer) → write insights
insights/schemas.py          # pydantic: ModelSpec; InsightOutput (title, narrative, sentiment_label, confidence, cited_metrics)
tests/insights/test_tools.py
tests/insights/test_router.py            # tier selection + escalation logic
tests/insights/test_agent_contract.py    # mocked clients: output shape + grounding rule, both providers
```

## 5. Data contracts
Writes `insights` (PRD 000 §5). `cited_metrics` is JSON: the field/values and timestamps the
agent pulled. `confidence` ∈ [0,1]. `user_id` null for scheduled/system insights; set for
on-demand requests tied to a user. The `model` column stores the **full resolved model id**
(e.g. `google/gemini-flash`, `anthropic/claude-sonnet-…`) so the tier that produced each insight
is auditable; record whether escalation occurred.

## 6. Edge cases & guardrails
- Sparse/early data (null `cog_shift`, missing `india_vix`) → acknowledge, lower confidence.
- Tool returns empty → agent states limitation; never invents a value.
- Model/tool error → retry with backoff; on persistent failure, write no insight (don't write a hallucinated one) and log.
- Duplicate trigger → idempotent; don't write twice for the same (instrument, session, type).
- Prompt-injection via data fields → treat tool data as untrusted content, not instructions.
- **Cheap models are weaker at grounding/JSON:** always validate structured output against the
  `InsightOutput` schema; on validation failure or sub-threshold confidence, **escalate to
  premium** (one retry), then fail soft. Grounding rules apply identically to every tier.
- **Provider differences:** tool-calling/output formats differ (OpenAI-style vs Anthropic) — the
  `LLMClient` must normalize them so the agent + tests are provider-agnostic.

## 7. Acceptance criteria (reviewer checklist)
- [ ] Scheduled + on-demand triggers both produce an `insights` row.
- [ ] Every quantitative claim in `narrative` appears in `cited_metrics` (grounding verified by test).
- [ ] No buy/sell recommendations; descriptive positioning language only.
- [ ] **Model is config-driven**: swapping `INSIGHTS_MODEL_CHEAP`/`_PREMIUM` needs no code change;
      nothing hardcoded.
- [ ] **Routing works**: simple tasks use the cheap tier; complex synthesis uses premium;
      escalation triggers on schema-validation failure / low confidence (test covers it).
- [ ] `LLMClient` normalizes tools + structured output across OpenRouter and Anthropic-native
      paths (contract test runs against mocked versions of both).
- [ ] Prompt caching enabled on the premium Anthropic-native path; tokens/cost logged **per tier**.
- [ ] Tools are read-only and reuse existing queries; no metric recomputed in the agent.
- [ ] Confidence + full resolved `model` id persisted; missing-data path lowers confidence.
- [ ] Tests pass (router + dual-provider contract test); `ruff` clean; env vars in `.env.example`.

## 8. Out of scope / future
Multi-instrument cross-market insights, backtesting insight accuracy, user-tunable insight
styles, streaming insights to the UI. (Later PRDs.)
