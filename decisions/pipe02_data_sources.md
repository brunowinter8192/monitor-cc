# Pipe Section: Data Sources

## Status Quo

- `session_finder.py`: `~/.claude/projects/` → glob `*.jsonl` + `*/subagents/agent-*.jsonl`, sorted by mtime
- `jsonl_parser.py`: tool_use/tool_result correlation via cache, extracts 6 data types (tools, prompts, media, thinking, skills, warnings)
- `hook_parser.py`: reads `src/logs/hook_outputs.jsonl`, filters by project cwd
- External pipeline: `instructions-loaded-hook.sh` (native hook in `~/.claude/settings.json`) → `hook_logger.py` → `hook_outputs.jsonl`

Hook types routed by `process_hook_log()` in monitor.py:
- `UserPromptSubmit` → `pending_user_prompt_hook`
- `PreToolUse` → `pending_pretooluse_hooks`
- `InstructionsLoaded` → `active_rules`

## Evidenz

Pending — needs evaluation.

## Recommendation (SOLL)

Pending — needs evaluation.

## Offene Fragen

- InstructionsLoaded feuert nicht nach compaction (Issue #30973) oder /clear (Issue #31017) — Rules-Pane zeigt nur initial geladene Rules
- ANNAHME: Skill-Aktivierung triggert InstructionsLoaded NICHT (CHANGELOG definiert Scope als CLAUDE.md und .claude/rules/*.md)

## Quellen

- (keine)
