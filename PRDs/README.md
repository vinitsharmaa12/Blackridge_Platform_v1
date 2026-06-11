# Blackridge Platform — PRDs

Implementation specs for the platform build. **Cursor implements; Claude reviews.**
Point Cursor at one PRD at a time, in order. Each PRD is self-contained but assumes
the conventions and system context in `000-overview-and-conventions.md` — read that first.

## Build order
| # | PRD | Delivers | Depends on |
|---|-----|----------|-----------|
| 000 | [Overview & conventions](000-overview-and-conventions.md) | Shared context, schema, coding standards, Definition of Done | — |
| 001 | [Ingestion worker](001-ingestion-worker.md) | Live scheduled NSE → DB pipeline | 000, schema applied |
| 002 | [Backend API](002-backend-api.md) | FastAPI read API + WebSocket | 001 (data in DB) |
| 003 | [Frontend dashboard](003-frontend-dashboard.md) | Next.js UI + charts | 002 |
| 004 | [Insights engine](004-insights-engine.md) | Agentic insight generation | 001, 002 |
| 005 | [Deployment & ops](005-deployment-and-ops.md) | Hosting, CI, scheduling | 001–004 |

## How to use with Cursor
1. Open the target PRD. Tell Cursor: *"Implement this PRD. Reuse existing `core/`
   and `metrics.py` — do not rewrite them. Follow the conventions in PRD 000."*
2. Work through the **Functional Requirements** and **File layout** sections.
3. Before opening a PR, self-check against the **Acceptance Criteria** checklist.
4. Claude reviews the diff against the same checklist.

## Ground rules for every PRD
- **Reuse, don't rewrite.** `core/normalize.py`, `core/enrich.py`, `core/db.py`,
  and `metrics.py` are done and validated. Build on them.
- **No secrets in code.** Everything sensitive comes from env (`.env`, not committed).
- **Small, reviewable PRs.** One PRD ≈ one PR where practical.
- **Idempotent + typed.** Writes are safe to re-run; Python is fully type-hinted.
