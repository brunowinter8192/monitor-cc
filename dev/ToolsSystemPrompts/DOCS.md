# dev/ToolsSystemPrompts/

## Role
Captured reference corpus of Claude Code's built-in tool definitions + a system-prompt segment, snapshotted to size the proxy-side tool-injection / tool-stripping budget (how many chars each tool description + schema costs, and which are strip candidates). Reference DATA + its analysis, not a script area — no `.py`, nothing produced at runtime. Touch when re-measuring tool-definition sizes against a new CC version; do NOT treat as live state (it is a point-in-time capture).

## Contents
- `_index.md` — size table: per-tool description chars, schema chars, totals, plus `sys[3]` and grand total.
- `_review.md` — strip analysis (Phase B): total tool-description chars, chars classified REDUNDANT/KNOWN and strippable.
- `<Tool>.md` (`Bash`, `Edit`, `Glob`, `Grep`, `Read`, `Skill`, `Write`) — the captured description + JSON schema text of each built-in tool, with its char count.
- `mcp__plugin_iterative-dev_iterative-dev__*.md` — captured MCP tool schemas (dev_sync, git_check, worker_send, worker_spawn).
- `sys3.md` — the captured `sys[3]` system-prompt segment (char count + content).

## Gotchas
Char counts are version-specific — a CC upgrade changes tool descriptions, so the numbers here are only valid for the capture's CC version. Re-capture rather than trust stale figures.
