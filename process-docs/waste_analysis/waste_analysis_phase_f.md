# Waste-Call Analysis + Phase F (Git Wrapper) — Closed 2026-04-22

## State as of 2026-04-22

Tool-use waste tracking ran live in the Monitor (Window 4, waste_pane). Ratio-based (input_chars / output_chars ≥ threshold). Threshold adjustable via digit key 1-9.

### Measures implemented (sessions 2026-04-21 to 2026-04-22)

1. **Tool-description strip (Phase E):** Proxy strips `tools[*].description` (top-level + `input_schema.properties[*].description`) to `""`. Pre-strip originals logged to JSONL. Display shows `[STRIPPED]` + dim-yellow expand. Savings: ~15.8k chars per request (of ~19.7k strippable, ~80% reduction).

2. **sys[3] strip:** Proxy replaces `system[3].text` (claudeMd block) with `"."`. Pre-strip original logged. Display shows `[STRIPPED]` + dim-yellow. Savings: ~3k chars per request.

3. **MCP→CLI migration:** 4 MCP tools (worker_spawn, worker_send, worker_merge, worker_status) migrated to CLI wrappers. MCP server + venv deleted. Tool count in payload: 11 → 7.

4. **tool-use skill consolidation (Phase C):** `tool-usage.md` + `git-commit-workflow.md` + `worker-cli` skill merged into one consolidated `tool-use` SKILL.md. 3 source files deleted.

5. **`c` shorthand:** `worker-cli` and `git-check` accept `c` as project_path argument (resolves to current git root). Eliminates repeated absolute paths.

6. **`worker-cli status --all`:** Snapshot of all active workers in one call instead of N individual status calls.

## Phase F — Git Wrapper Battery (gmv, gst, gd, gadd, gp)

### Evidence

Waste report `dev/tool_use_analysis/20260422_session_waste_patterns.md` (6 proxy JSONLs, 562 tool_use blocks):

| Wrapper candidate | Count | Total waste input | Assessment |
|---|---|---|---|
| `gst` (git status + branch) | 3 | 626 chars | Marginal — 3 calls across 6 sessions |
| `gl` (git log --oneline) | opportunistic | — | No measurable count |
| `gmv`, `gd`, `gadd`, `gp` | 0-1 | <200 chars each | No count-based evidence |

### Decision

**Closed — no action needed.** The high-leverage items (worker-cli c-shorthand, status --all, tool-description strip, MCP removal) were implemented. The remaining git-wrapper candidates had count=1-3 across 6 sessions — no systematic waste pattern. If a pattern emerges organically (e.g. gst appears in 5+ sessions as top offender), a wrapper can be built in 5 minutes.

### Sources

- `dev/tool_use_analysis/20260422_session_waste_patterns.md` — aggregated waste analysis
- `dev/tool_use_analysis/extract_patterns.py` — pattern-extraction script
- `dev/ToolsSystemPrompts/_review.md` — tool-description strip analysis (Phase B)
