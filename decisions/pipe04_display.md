# Pipe Section: Display

## Status Quo

- `formatter.py`: 21 Funktionen, color-coded output (green=main, blue=subagent, red=error, pastel=meta)
- `ui_mode.py`: `format_rules_block()` rendert `ACTIVE RULES (XP / YG)` mit `[P]`/`[G]` Prefix pro Regel, pastel blue
- `subagent_ui.py`: collapsible list, Digits 1-9 toggle via `click_handler.py`
- `ui_mode.py`: `run_ui_mode()` Screen-clear refresh loop mit raw stdin

**BUG (fixed):** `active_rules` was populated by `process_hook_log()` but never rendered in streaming mode.
Fix: `run_rules_loop()` in monitor.py + dedicated `--mode rules` tmux pane (Pane 1, rechts-oben).

Rules-Pane Layout:
- Pane 1 (rechts-oben, 25% Höhe): `python3 workflow.py --mode rules` → `run_rules_loop()`
- Rendert `format_rules_block()` bei jeder Änderung von `active_rules`
- M-r Keybinding: Rules-Pane Content → Clipboard via `pbcopy`

## Evidenz

Pending — needs evaluation.

## Recommendation (SOLL)

Pending — needs evaluation.

## Offene Fragen

- Rules-Pane zeigt nur initial geladene Rules (InstructionsLoaded feuert nicht nach compaction oder /clear — siehe pipe02)

## Quellen

- (keine)
