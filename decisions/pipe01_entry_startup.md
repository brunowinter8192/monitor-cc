# Pipe Section: Entry & Startup

## Status Quo

- `workflow.py`: `--mode all` → tmux 6-Pane (main + tokens | rules + subagent + hooks + warnings), `--mode main|subagent|rules|warnings|hooks|tokens` → einzelner Prozess
- `startup.py`: argparse mit choices `['all', 'main', 'subagent', 'rules', 'warnings', 'hooks', 'tokens']`, `--project`, `--ui`
- `tmux_launcher.py`: 6 Panes, history 50000, keybindings (C-q scroll, C-r restart all 6 panes, C-f search, mouse, M-m/M-t/M-r/M-s/M-h/M-w copy)

tmux Layout:
```
┌─────────────────┬──────────────────┐
│  Pane 0 (main)  │ Pane 2 (rules)   │  25% Höhe
│─────────────────│──────────────────│
│  Pane 1 (tokens)│ Pane 3 (subs)    │  50% Höhe
│    50% Breite   │──────────────────│
│                 │ Pane 4 (hooks) │ Pane 5 (warnings) │  25% Höhe
└─────────────────┴──────────────────┘
```

Split-Sequenz (Reihenfolge kritisch — erst horizontal, dann vertikal links):
1. `new-session -d -s $session $main_cmd` → Pane 0 (volle Fläche)
2. `split-window -h -t $session:0.0 -l 50% $subagent_cmd` → Pane 0 (links), Pane 1 (rechts)
3. `split-window -v -t $session:0.0 -l 30% $tokens_cmd` → Pane 0 (main oben-links 70%), Pane 1 (tokens unten-links 30%), Pane 2 (rechts)
4. `split-window -v -t $session:0.2 -b -l 25% $rules_cmd` → Pane 2 (rules rechts-oben 25%), Pane 3 (subagents rechts 75%)
5. `split-window -v -t $session:0.3 -l 25% $warnings_cmd` → Pane 4 (warnings rechts-unten 25%)
6. `split-window -h -b -t $session:0.4 -l 50% $hooks_cmd` → Pane 4 (hooks links 50%), Pane 5 (warnings rechts 50%)

## IST — Stellschrauben

### POLL_INTERVAL (Kategorie: Performance)

Hardcoded an zwei Stellen:
- `src/monitor.py:59`: `POLL_INTERVAL = 0.5` — Modul-Level Konstante, genutzt in `run_streaming_loop()` (monitor.py:423) und `run_rules_loop()` (monitor.py:436)
- `src/ui_mode.py:24`: `POLL_INTERVAL = 0.5` — separate Definition, genutzt in `run_ui_loop()` (ui_mode.py:48)

Kein gemeinsames `constants.py`-Eintrag. Wert muss an zwei Stellen synchron gehalten werden.

### tmux history-limit (Kategorie: Konfiguration)

Hardcoded in `src/tmux_launcher.py:50`:
```python
subprocess.run(["tmux", "set-option", "-g", "history-limit", "50000"])
```
- Setzt globale tmux Option (nicht session-scoped) — betrifft alle tmux Panes
- Vor dem Setzen wird der Original-Wert gesichert (`get_global_history_limit()`, tmux_launcher.py:106-109)
- Nach dem Session-Aufbau wird der Original-Wert wiederhergestellt (`restore_global_history_limit()`, tmux_launcher.py:112-114)
- Das `50000` ist hardcoded, kein Config-Parameter

### 6-Pane Layout Split-Ratios (Kategorie: Konfiguration)

Hardcoded Split-Befehle in `src/tmux_launcher.py`:
- `-l 30%` — vertikaler Split des Main-Panes (main oben 70% | tokens unten 30%)
- `-l 50%` — horizontaler Split (left column | right column)
- `-l 25%` — vertikaler Split des rechten Panes (rules-oben 25% | subagents-unten 75%)
- `-l 25%` — vertikaler Split des Subagent-Panes (subagents 75% | warnings 25%)

Keine Config-Parameter. Ratios nicht als Konstanten benannt.

### Session Name Generation (Kategorie: Konfiguration)

`generate_session_name()` in `src/tmux_launcher.py:84-90`:
- Global-Modus: fester Name `"monitor_cc_global"`
- Projekt-Modus: `"monitor_cc_" + MD5(normpath(project_path))[:8]`
- Hash-Länge 8 Zeichen (potenzielle Kollision bei vielen Projekten)

### Logging in Entry/Startup (Kategorie: Observability)

`src/tmux_launcher.py`: 14 `log_tagged()`-Aufrufe → `src/logs/01_startup.log`
Tags: SPLIT_LAUNCH, SESS_NAME, SCRIPT_PATH, HIST_SET, TMUX_CREATE, TMUX_SPLIT_H, TMUX_SPLIT_V, TMUX_CHECK, TMUX_INSIDE, SESS_EXISTS, SESS_KILL, HIST_ORIG, HIST_RESTORE, TMUX_CONFIG

Gemäss User-Feedback: 0 dieser Logs wurden je zu Debugging-Zwecken konsultiert.

## Evidenz

Pending — needs evaluation.

## Recommendation (SOLL)

Pending — needs evaluation.

## Offene Fragen

- tmux Keybinding für 3. Pane: M-r für Rules-Pane Copy implementiert, Verhalten bei unterschiedlichen Pane-Indices noch zu verifizieren
- M-w Keybinding: Warnings-Pane Content → Clipboard via pbcopy

## Quellen

- tmux man page: github.com/tmux/tmux `tmux.1` L3591-3648 (split-window), L840-890 (pane targeting)
- dev/display/test_tmux_layout.sh: Pane-Index Verifikation nach verschachtelten Splits
- GitHub anthropics/claude-code #27724: JSONL format undocumented, changes without changelog
- GitHub anthropics/claude-code #33414: FireHose monitoring feature request (kein offizielles Monitoring-API)
