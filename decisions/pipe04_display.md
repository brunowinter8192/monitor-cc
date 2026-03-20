# Pipe Section: Display

## Status Quo

- `formatter.py`: 21 Funktionen, color-coded output (green=main, blue=subagent, red=error, pastel=meta)
- `ui_mode.py`: `format_rules_block()` rendert `ACTIVE RULES (XP / YG)` mit `[P]`/`[G]` Prefix pro Regel, pastel blue
- `subagent_ui.py`: collapsible list, Digits 1-9 toggle via `click_handler.py`
- `ui_mode.py`: `run_ui_mode()` Screen-clear refresh loop mit raw stdin

**BUG (fixed):** `active_rules` was populated by `process_hook_log()` but never rendered in streaming mode.
Fix: `run_rules_loop()` in monitor.py + dedicated `--mode rules` tmux pane (Pane 1, rechts-oben).
**BUG (fixed):** Project `.claude/rules/*.md` did not appear — root cause was YAML array syntax in `paths:` frontmatter (Claude Code Bug #19377/#33581). CSV parser expects string, receives JS Array from `yaml.parse()`, producing broken globs. Fix: CSV string format (`paths: src/**, workflow.py`). All project rules now load correctly via InstructionsLoaded hook.
**BUG (fixed):** Rules-Pane showed historical rules from previous sessions because `hook_log_position` was set to 0 (read from beginning of hook log). Fix: removed `hook_log_position = 0` override, now starts from EOF like all other modes.

Rules-Pane Layout:
- Pane 1 (rechts-oben, 25% Höhe): `python3 workflow.py --mode rules` → `run_rules_loop()`
- Rendert `format_rules_block()` bei jeder Änderung von `active_rules`
- M-r Keybinding: Rules-Pane Content → Clipboard via `pbcopy`

## Evidenz

Pending — needs evaluation.

## Recommendation (SOLL)

Pending — needs evaluation.

## Offene Fragen

- Rules-Pane: `active_rules` ist ein Set (nur add, kein remove) — Rules verschwinden nicht wenn sie out-of-scope gehen
- InstructionsLoaded Hook feuert nicht nach /clear oder /compact (#30973, #31017) — Monitor kann Reloads nicht tracken
- Session-JSONL enthält keine Rules/Instructions-Daten (verifiziert via dev/display/jsonl_exploration Scripts)

## Quellen

- GitHub anthropics/claude-code #19377 — YAML array syntax for `paths:` broken (CSV parser bug)
- GitHub anthropics/claude-code #33581 — Multiple `paths:` entries silently fail (same root cause)
- GitHub anthropics/claude-code #30973 — InstructionsLoaded missing after compaction
- GitHub anthropics/claude-code #31017 — InstructionsLoaded missing on /clear
- GitHub anthropics/claude-code #16299 — Path-scoped rules load globally (opposite bug, version-dependent)
