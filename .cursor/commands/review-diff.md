# Review Diff

Act as the **Reviewer** for the Blackridge Platform. Do **not** edit code — report only.

Follow the `@reviewer` and `@code-quality-review` rules. Review the current diff/PR against:
1. the target PRD's **Acceptance Criteria** + the **Definition of Done** in
   `PRDs/000-overview-and-conventions.md`, and
2. the five axes: correctness, readability, architecture, security, performance.

Catch the project red flags: duplicated metric logic instead of reusing `core/`/`metrics.py`;
service-role key exposure; missing JWT check or RLS bypass; non-idempotent DB writes; new table
without RLS policies; hardcoded expiry / non-parameterized instrument; insight claims not present
in `cited_metrics`; any buy/sell advice; secrets in code; client-side metric recomputation;
field names diverging from the API contract; scope creep beyond the PRD; missing tests.

Output concise comments as **location → problem → fix**, citing the PRD criterion or the axis.
Approve when the change definitely improves code health and follows conventions.
