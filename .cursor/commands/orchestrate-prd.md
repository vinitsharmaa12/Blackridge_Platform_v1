# Orchestrate PRD

Act as the **Orchestrator** for the Blackridge Platform.

Read `AGENTS.md` and the PRD I reference (in `PRDs/`) before planning. Also read
`PRDs/000-overview-and-conventions.md` for shared context.

Produce a sequenced checklist of **thin vertical slices** (follow `@incremental-implementation`).
For each slice give:
- scope (what it delivers, end to end),
- files it touches,
- the PRD **Acceptance Criteria** it satisfies,
- how to verify it (test/command/manual check).

Identify dependencies between slices and call out the **riskiest** slice to tackle first.

Do **not** write feature code in this command — output the plan only, then hand each slice to
`/implement-prd`. Reuse `core/` and `metrics.py`; never duplicate metric logic. If anything in
the PRD is ambiguous or wrong, surface it instead of guessing.
