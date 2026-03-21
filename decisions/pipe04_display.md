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

## IST — Stellschrauben

### LONG_OUTPUT_THRESHOLD (Kategorie: Display / UX)

`LONG_OUTPUT_THRESHOLD = 10000` in `src/formatter.py:21`.
Verwendet in `format_output()` (formatter.py:119-138):
- `len(content) >= LONG_OUTPUT_THRESHOLD` → `log_long_output(content)` aufgerufen + `LIGHT_RED_BG` Hintergrundfarbe für den gesamten Output-Block
- `log_long_output()` (formatter.py:213-219) schreibt: char_count, line_count, 500-char Preview, und **den vollständigen Content** nach `src/logs/10_long_outputs.log`

Wert ist hardcoded, kein Config-Parameter.

### Input Preview Truncation (Kategorie: Display / UX)

`get_input_preview()` in `src/subagent_ui.py:159-179`:
- Pro Key-Value-Paar: `value_str[:50] + '...'` wenn `len(value_str) > 50` (subagent_ui.py:170-171)
- Gesamtes Ergebnis: `result[:120] + '...'` wenn `len(result) > 120` (subagent_ui.py:175)
- Fallback für nicht-dict input: `str(input_data)[:40] + '...'` wenn `> 40` (subagent_ui.py:164)

Drei verschiedene Truncation-Schwellen (40, 50, 120), alle hardcoded.

### SCORE_PATTERN Regex (Kategorie: Display / UX)

`SCORE_PATTERN = re.compile(r'^-+ Result \d+ \(score: [\d.]+\) -+$')` in `src/formatter.py:20`.
Verwendet in `format_output()` (formatter.py:130-131): Zeilen die matchen werden in `GREEN` coloriert.
Speziell für RAG-Suchergebnisse (Format aus rag-Plugin). Hardcoded Pattern.

### Screen Clear Escape Sequence (Kategorie: Display / Robustheit)

`\033[2J\033[3J\033[H` an zwei Stellen:
- `src/ui_mode.py:78`: `print("\033[2J\033[3J\033[H", end='', flush=True)` — in `sync_ui_to_screen()`
- `src/monitor.py:433`: `print("\033[2J\033[3J\033[H", end='', flush=True)` — in `run_rules_loop()`

Bedeutung: `[2J` löscht sichtbaren Screen, `[3J` löscht Scrollback-Buffer, `[H` setzt Cursor auf Position 0,0. Duplizierter Hardcode an zwei Stellen.

### Farb-Duplikation — überlappende Namen (Kategorie: Architektur / Kopplung)

Zwei separate Farb-Definitionen mit überlappenden Variablennamen:

**`src/utils.py` (Standard ANSI — 16-Farben):**
```
GREEN  = '\033[92m'
BLUE   = '\033[94m'
YELLOW = '\033[93m'
CYAN   = '\033[96m'
```

**`src/formatter.py` (256-Farben Palette):**
```
GREEN  = '\033[38;5;35m'
BLUE   = '\033[38;5;33m'
YELLOW = '\033[38;5;220m'
CYAN   = '\033[38;5;51m'
```

Überlappende Namen mit unterschiedlichen ANSI-Codes:
| Name | utils.py | formatter.py |
|------|----------|--------------|
| GREEN | `\033[92m` (Standard-Grün) | `\033[38;5;35m` (256c dunkleres Grün) |
| BLUE | `\033[94m` (Standard-Blau) | `\033[38;5;33m` (256c Blau) |
| YELLOW | `\033[93m` (Standard-Gelb) | `\033[38;5;220m` (256c Gelb-Gold) |
| CYAN | `\033[96m` (Standard-Cyan) | `\033[38;5;51m` (256c helles Cyan) |
| RESET | `\033[0m` | `\033[0m` (identisch) |

Import-Abhängigkeit:
- `src/monitor.py:10` importiert aus utils.py: `from .utils import RESET, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE, PURPLE, log_tagged`
- `src/subagent_ui.py:20` importiert aus formatter.py: `from .formatter import GREEN, BLUE, CYAN, YELLOW, RESET`

Folge: monitor.py und subagent_ui.py nutzen dieselben Variablennamen (z.B. `GREEN`), aber unterschiedliche ANSI-Codes. Gleicher Name = unterschiedliche Farbe je nach Import-Kontext.

### Logging im Display (Kategorie: Observability)

`src/formatter.py`: 0 `log_tagged()`-Aufrufe; nutzt `long_output_logger.info()` direkt (formatter.py:216-219) → `src/logs/10_long_outputs.log`
`src/ui_mode.py`: 4 `log_tagged()`-Aufrufe → `src/logs/08_ui_rendering.log`
`src/subagent_ui.py`: 5 `log_tagged()`-Aufrufe → `src/logs/08_ui_rendering.log`

Gemäss User-Feedback: 0 dieser Logs wurden je zu Debugging-Zwecken konsultiert.

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
- GitHub anthropics/claude-code #27724: JSONL format undocumented, changes without changelog
- GitHub anthropics/claude-code #33414: FireHose monitoring feature request (kein offizielles Monitoring-API)
