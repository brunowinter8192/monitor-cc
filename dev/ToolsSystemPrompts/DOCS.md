# dev/ToolsSystemPrompts/

## Role
Captured reference corpus of Claude Code's built-in tool definitions plus a system-prompt segment,
snapshotted to size the proxy-side tool-injection/tool-stripping budget (chars per tool description +
schema, and which are strip candidates). Reference data and its analysis, not a script area — no
`.py` files, nothing produced at runtime. Touch when re-measuring tool-definition sizes against a new
CC version; do not treat as live state, since it is a point-in-time capture.

## Modules
None — this directory holds captured Markdown reference data, not scripts:
- `_index.md` — size table: per-tool description chars, schema chars, totals, plus `sys[3]` and
  grand total.
- `_review.md` — strip analysis: total tool-description chars, chars classified redundant/known and
  strippable.
- `Bash.md`, `Edit.md`, `Glob.md`, `Grep.md`, `Read.md`, `Skill.md`, `Write.md` — the captured
  description + JSON schema text of each built-in tool, with its char count.
- `mcp__plugin_iterative-dev_iterative-dev__*.md` — captured MCP tool schemas.
- `sys3.md` — the captured `sys[3]` system-prompt segment (char count + content).

## Gotchas
Char counts are version-specific — a CC upgrade changes tool descriptions, so the numbers here are
only valid for the capture's CC version. Re-capture rather than trust stale figures.
