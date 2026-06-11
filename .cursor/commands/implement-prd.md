# Implement PRD

Act as the **Implementer** for the Blackridge Platform.

Follow the `@prd-workflow` rule for the PRD (or single slice) I reference. Reuse
`core/normalize.py`, `core/enrich.py`, `core/db.py`, and `metrics.py` — never rewrite or
duplicate them. Obey the auto-attached path rules (`worker`/`api`/`web`/`insights`/`db`) for
whatever you edit.

Build in thin vertical slices (`@incremental-implementation`): implement → test (`@tdd`) →
verify → commit → next. Keep Python fully typed and `ruff`-clean; TypeScript strict.

Secrets via env only; never expose the Supabase service-role key to API/web. Update
`.env.example` for any new env var.

Before declaring a slice done, self-check it against the PRD's **Acceptance Criteria** and the
**Definition of Done** in `PRDs/000-overview-and-conventions.md`. Keep the change scoped to one
PRD/slice.
