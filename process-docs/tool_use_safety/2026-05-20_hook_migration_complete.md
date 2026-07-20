# Hook Migration — Complete (2026-05-20)

## What Happened

A tracking effort started 2026-05-12 with the first quantifications (267 pkill-f calls / 6 days, 246 in one searxng session). Hook #1 `block_dangerous_kill` landed the morning of 2026-05-20. The evening session on 2026-05-20 brought hooks #2-7 + a skill consolidation in one continuous migration block.

## Hooks Complete

| # | Hook | Matcher | Trigger evidence |
|---|------|---------|----------------|
| 1 | block_dangerous_kill | Bash | pkill -f / ps\|grep\|kill (267 over 6 days) |
| 2 | block_chained_sleep | Bash | sleep N && other (54 violations in 5 logs) |
| 3 | block_unauthorized_background | Bash | run_in_background=true non-canonical (user incident: rag-cli update_docs in bg, 2m36s no live output) |
| 4 | block_broad_grep | Bash | grep -r without --include (23 Rule-3 violations — highest non-hooked) |
| 5 | block_noop_edit | Edit | old_string == new_string |
| 6 | block_read_directory | Read | path is directory |
| 7 | block_read_oversize | Read | file >256KB without offset/limit/pages |

Multi-matcher `hook_setup.py` refactor: a list of `(script, matcher)` tuples — supports parallel Bash/Edit/Read registration. Idempotent via exact command-string match.

## Skill Consolidation

`blank/skills/tool-use-additions/SKILL.md` (operational pre-check tables) integrated as inline extensions into `~/.claude/shared-rules/global/tool-use.md`:

- Rule 11: chain-exit-code = last-command extension
- Read section: byte size limits + nonexistent + worktree CLAUDE.md re-injection
- Edit section: noop edit + file-modified-since-read
- RAG CLI section: multi-model deltas + RAG-meta status-quo subsection

The skill directory was deleted in the blank repo, the `plugin.json` entry removed from the skills array, plugin-publish run.

## What Remains Open

Rule-9 (Read before Edit) — 1 violation in the 5-log sample. Not statically hookable: requires session state (which files were read this session), which is not present in the PreToolUse JSON payload. Stays as a soft rule in tool-use.md.

Worker-local hook suppression remains unanswered (all hooks fire globally, no per-worker override mechanism).

## Sources

- `src/hooks/DOCS.md` (current hook state, evidence incl. the 2026-05-20 run)
- `dev/tool_use_analysis/rule_compliance.py` (compliance audit script)
- The session-findings entry in this area (prior quantification)
- The recurrence-during-implementation entry in this area (Hook #1 trigger)
