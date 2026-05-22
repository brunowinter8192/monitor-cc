# dev/cc_source_research/

## Role

Research artifacts from Claude Code binary + source analysis (env-var inventory). Contains env-var inventories extracted from npm binaries and cross-referenced against community decompile repos. Touch this directory when adding new binary extracts or updating the env-var inventory.

## Files

| File | Description |
|---|---|
| `20260428_env_var_inventory_v2.1.121.md` | Full env-var table for v2.1.121 binary — all CLAUDE_* + perf-adjacent vars, categorized, with latency-subset highlight and open questions |

## Sources Used

- npm binary: `@anthropic-ai/claude-code-darwin-arm64@2.1.121` — strings extracted via `grep -oa "CLAUDE_[A-Z][A-Z_]*"`
- Decompile: `thepono1/claude-code-source` — INSIGHTS.md (v2.1.88 source, confirmed read-sites)
- Decompile: `alanisme/claude-code-decompiled` — docs/en/ (architecture docs from v2.1.88)
- GH Issues: `anthropics/claude-code` #33949, #25979, #49500 (empirical reverse-engineering by community)
