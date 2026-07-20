# Worker Thinking Visibility + Anti-Circling

## Problem

Sonnet workers burn large parts of their thinking budget on complex refactor tasks (REQ #11 in the searxng dev-refactor worker on 2026-05-06: 42-43k of 64k thinking tokens, ~67% of the cap, ~11min). Thinking content is completely opaque — only the signature (~191k chars) is visible, not the reasoning. That makes it impossible to judge whether the model is working productively or circling.

User constraint: lowering the budget is not an option (reasoning depth must be kept). Prompt-level "don't circle" is unreliable. Active prevention of circling needs visibility first.

## State (verified 2026-05-06)

- Worker spawn sends `thinking: {type: 'adaptive', display: 'omitted'}` in raw_payload (verified in `src/logs/api_requests_worker_51bdcc16_dev-refactor_1778024004.jsonl` REQ #1).
- Consequence: session JSONL has `thinking-block.thinking = ""` (empty), only the signature populated.
- Sonnet 4-6 would deliver the API default `summarized`, the CC harness explicitly overrides to `omitted` (GH issue #49268, faster TTFB).
- `showThinkingSummaries: true` in `~/.claude/settings.json` is NOT sufficient — it only controls the Ctrl+O transcript renderer, not the API request.

## Lever — `--thinking-display summarized`

A hidden CLI flag sets the API param explicitly. Verified in GH issue #49268 comments #3, #5, #7: before, `thinking: ""`, after, a populated reasoning summary of 200-500 words. Cost overhead practically zero (signature bytes identical, the summary itself ~hundreds to a few thousand tokens, sub-1% of the reasoning budget).

Implementation: `~/.claude/plugins/cache/brunowinter-plugins/iterative-dev/<version>/src/spawn/tmux_spawn.sh` appends the flag to the `claude` call for every spawned worker.

## Recommended Order (not executed)

1. **Phase A — iterative-dev:** `--thinking-display summarized` in `tmux_spawn.sh`.
2. **Phase B — Monitor_CC:** the token-pane expanded-REQ view at the time showed `[N] thinking text: 0c sig:Xc`. With visibility, `text: Yc` becomes non-zero. Render extension: an expandable summary block, visual highlighting when summary length nears the budget cap, optionally a per-REQ thinking-tokens counter in the header.
3. **Phase C — Empirical observation:** run a few worker sessions with summary visibility, document patterns.
4. **Phase D — Anti-circling strategy** based on the phase-C data.

## Possible Anti-Circling Levers (to Evaluate After Visibility)

1. Pattern detection on summaries — badge in the token pane on repeated reasoning themes.
2. Track a per-worker thinking-token quota, alarm at N% of the cumulative.
3. Prompt engineering — "if a thinking block exceeds X tokens, abort" (effectiveness unclear).
4. Budget adaptation per task type — complex refactor=max, mechanical edit=high/medium (selective, not a global budget cut).

## Status

Spec only. Phases A-D not executed. Parked.

## Sources

- GH `anthropics/claude-code` issue #49268 — thinking summaries missing on Opus 4.7, API mechanics + CLI-flag workaround.
- GH `anthropics/claude-code` issue #49322 — Opus 4.7 thinking summaries not rendered in the VS Code extension.
- Direct verification: `src/logs/api_requests_worker_51bdcc16_dev-refactor_1778024004.jsonl` + session JSONL `~/.claude/projects/-Users-brunowinter2000-Documents-ai-Meta-ClaudeCode-MCP-searxng--claude-worktrees-dev-refactor/07b733ef-f2c8-4d7d-9098-eaaa40931925.jsonl`.
