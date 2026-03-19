# Pipe Section: Core Loop

## Status Quo

- `monitor.py`: `run_streaming_loop()` pollt alle 0.5s, ruft `process_hook_log()` + `monitor_sessions()` auf
- `monitor.py`: `run_rules_loop()` pollt alle 0.5s, ruft `process_hook_log()` auf und rendert `format_rules_block(active_rules)` bei Änderungen
- Hook routing in `process_hook_log()`: 3 Events → 3 State Dicts
  - `UserPromptSubmit` → `pending_user_prompt_hook`
  - `PreToolUse` → `pending_pretooluse_hooks`
  - `InstructionsLoaded` → `active_rules`
- Agent tracking: `agent_to_task`, `agent_to_type` maps, `buffered_subagent_calls` für Orphans (Calls ohne bekannten Agent)
- Usage accumulation: `accumulate_usage()` aggregiert Token-Totals pro Turn

`run_rules_loop()` Ablauf:
1. `process_hook_log()` → aktualisiert `active_rules`
2. `format_rules_block(active_rules)` → rendert ACTIVE RULES Block
3. Bei Änderung: Screen-Clear + Print
4. `time.sleep(POLL_INTERVAL)`

## Evidenz

Pending — needs evaluation.

## Recommendation (SOLL)

Pending — needs evaluation.

## Offene Fragen

- (keine)

## Quellen

- (keine)
