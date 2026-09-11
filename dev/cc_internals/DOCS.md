# dev/cc_internals/

## Role

Research artifacts from Claude Code binary and source analysis — env-var inventories extracted
from npm binaries and cross-referenced against community decompile repos. No `.py` scripts; add a
new dated file under `md/` when extracting from a new binary version. Pairs with
`process-docs/cc_internals/`.

## Files

| File | Description |
|---|---|
| `md/20260428_env_var_inventory_v2.1.121.md` | Env-var table for v2.1.121 — all `CLAUDE_*` + perf-adjacent vars, categorized, with latency-subset highlight and open questions |

## Sources Used

- npm binary: `@anthropic-ai/claude-code-darwin-arm64@2.1.121` — strings extracted via `grep -oa "CLAUDE_[A-Z][A-Z_]*"`
- Decompile: `thepono1/claude-code-source` — INSIGHTS.md (v2.1.88 source, confirmed read-sites)
- Decompile: `alanisme/claude-code-decompiled` — docs/en/ (architecture docs from v2.1.88)
- GH Issues: `anthropics/claude-code` #33949, #25979, #49500 (empirical reverse-engineering by community)
