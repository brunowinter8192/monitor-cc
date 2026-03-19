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
- Project `.claude/rules/*.md` werden vom Hook nicht erfasst (Bug #33275) — nur Global Rules + CLAUDE.md feuern
- System Prompt (mit "Contents of" Zeilen) wird NICHT ins Session-JSONL geschrieben — alternative Quelle nötig

## Quellen

- Claude Code #30973: github.com/anthropics/claude-code/issues/30973 (InstructionsLoaded + compaction)
- Claude Code #33275: github.com/anthropics/claude-code/issues/33275 (InstructionsLoaded session_start bug)
- Claude Code #31017: github.com/anthropics/claude-code/issues/31017 (InstructionsLoaded + /clear)
- Claude Code #12151: github.com/anthropics/claude-code/issues/12151 (Plugin hook output bug — nicht betroffen, native Hook)
- Claude Code CHANGELOG L340: InstructionsLoaded added v2.1.64
