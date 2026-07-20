# Hook Migration — Complete (2026-05-20)

## Was passierte

Weyg-Tracker started 2026-05-12 mit ersten Quantifizierungen (267 pkill-f calls / 6 days, 246 in einer searxng session). Hook #1 `block_dangerous_kill` landete 2026-05-20-Vormittag. Session 2026-05-20-Abend brachte Hooks #2-7 + Skill-Konsolidierung in einem durchgehenden Migration-Block.

## Hooks komplett

| # | Hook | Matcher | Trigger-Evidenz |
|---|------|---------|----------------|
| 1 | block_dangerous_kill | Bash | pkill -f / ps\|grep\|kill (267 over 6 days) |
| 2 | block_chained_sleep | Bash | sleep N && other (54 violations in 5 logs) |
| 3 | block_unauthorized_background | Bash | run_in_background=true non-canonical (user incident: rag-cli update_docs in bg, 2m36s no live output) |
| 4 | block_broad_grep | Bash | grep -r without --include (23 Rule-3 violations — highest non-hooked) |
| 5 | block_noop_edit | Edit | old_string == new_string |
| 6 | block_read_directory | Read | path is directory |
| 7 | block_read_oversize | Read | file >256KB without offset/limit/pages |

Multi-matcher `hook_setup.py` refactor: list of `(script, matcher)` tuples — supports Bash/Edit/Read parallel registration. Idempotent via exact command-string match.

## Skill consolidation

`blank/skills/tool-use-additions/SKILL.md` (operational pre-check tables) integriert als inline-Erweiterungen in `~/.claude/shared-rules/global/tool-use.md`:

- Rule 11: chain-exit-code = last-command extension
- Read section: byte size limits + nonexistent + worktree CLAUDE.md re-injection
- Edit section: noop edit + file-modified-since-read
- RAG CLI section: multi-model deltas + RAG-meta status-quo subsection

Skill-Direktor deleted in blank repo, `plugin.json` entry removed from skills array, plugin-publish run.

## Was bleibt offen

Rule-9 (Read before Edit) — 1 violation in 5-log sample. Nicht statisch hookable: requires session state (which files were read this session) was im PreToolUse JSON payload nicht steckt. Bleibt als Soft Rule in tool-use.md.

Worker-local hook-suppression weiter unbeantwortet (alle Hooks fire globally, kein per-worker override-Mechanismus).

## Quellen

- `decisions/pipe07_safety_hooks.md` (IST 7 hooks, Evidenz inkl. 2026-05-20 run)
- `dev/tool_use_analysis/rule_compliance.py` (compliance audit script)
- `decisions/OldThemes/tool_use_safety/2026-05-12_session_findings.md` (vorherige Quantifizierung)
- `decisions/OldThemes/tool_use_safety/2026-05-20_recurrence_during_implementation.md` (Hook #1 Trigger)
- Bead Monitor_CC-weyg (closed at session end)
