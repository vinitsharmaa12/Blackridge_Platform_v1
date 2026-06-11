# Cursor Commands — Blackridge orchestration agents

Cursor **removed Custom Modes in v2.1** (Dec 2025). The replacement is **Commands**: reusable
prompts stored as markdown in `.cursor/commands/`, invoked by typing `/` in chat. These are
repo-native and version-controlled (better than the old UI-only modes).

## The three "agents"
| Command | Role | Use for |
|---------|------|---------|
| `/orchestrate-prd` | Orchestrator | Turn a PRD into a sequenced slice plan (no code) |
| `/implement-prd`   | Implementer  | Execute a PRD / one slice end to end |
| `/review-diff`     | Reviewer     | Five-axis + Acceptance-Criteria review of a diff (read-only) |

## How to use
1. Type `/` in the Cursor chat → pick the command (filename = command name).
2. Add the target after it, e.g. `/implement-prd PRDs/001-ingestion-worker.md`.
3. The command body is inserted as the prompt; it `@`-mentions the relevant `.cursor/rules/`
   so domain behavior + skills (tdd, review, incremental) load automatically.

Typical flow: `/orchestrate-prd` a PRD → `/implement-prd` each slice → `/review-diff` the result.

## Caveat (vs old modes)
Commands carry the **prompt/behavior** but cannot pin **tools, MCP permissions, or a specific
model** (a known gap Cursor may restore later). Set the model/tools in the normal Agent UI when
needed. MCP servers are pre-wired in `.cursor/mcp.json`.

## MCP
`.cursor/mcp.json` pre-wires Supabase (read-only), context7, and Railway. Replace the
placeholder tokens, and verify each server's package/command in Cursor → Settings → MCP
(confirm the Railway package name for your install). Don't commit real tokens.

## If you don't want commands
The `.cursor/rules/` do most of the work automatically. In plain Agent mode you can `@`-mention
a rule directly — e.g. `@prd-workflow`, `@reviewer` — for the same behavior on demand.
