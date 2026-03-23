# Pipe Section: Entry & Startup

## Status Quo

- `workflow.py`: `--mode all` → tmux 7-Pane (main + tokens | rules + subagent + hooks + warnings + workers), `--mode main|subagent|rules|warnings|hooks|tokens|workers` → einzelner Prozess
- `startup.py`: argparse mit choices `['all', 'main', 'subagent', 'rules', 'warnings', 'hooks', 'tokens', 'workers']`, `--project`, `--ui`
- `tmux_launcher.py`: 7 Panes, history 50000, keybindings (C-q scroll, C-r restart all 7 panes, C-f search, mouse, M-m/M-t/M-r/M-s/M-h/M-w/M-k copy)

tmux Layout (7 Panes, Stand Session 3):
```
┌─────────────────┬──────────────────┐
│  Pane 0 (main)  │ Pane 2 (rules)   │  25% Höhe
│─────────────────│──────────────────│
│  Pane 1 (tokens)│ Pane 3 (subs)    │  50% Höhe
│    50% Breite   │──────────────────│
│                 │ Pane 4  │ Pane 5 │  12.5% Höhe
│                 │ (hooks) │(warns) │
│                 │         │ Pane 6 │  12.5% Höhe
│                 │         │(work.) │
└─────────────────┴──────────────────┘
```

Split-Sequenz (Reihenfolge kritisch — erst horizontal, dann vertikal links):
1. `new-session -d -s $session $main_cmd` → Pane 0 (volle Fläche)
2. `split-window -h -t $session:0.0 -l 50% $subagent_cmd` → Pane 0 (links), Pane 1 (rechts)
3. `split-window -v -t $session:0.0 -l 30% $tokens_cmd` → Pane 0 (main oben-links 70%), Pane 1 (tokens unten-links 30%), Pane 2 (rechts)
4. `split-window -v -t $session:0.2 -b -l 25% $rules_cmd` → Pane 2 (rules rechts-oben 25%), Pane 3 (subagents rechts 75%)
5. `split-window -v -t $session:0.3 -l 25% $warnings_cmd` → Pane 4 (warnings rechts-unten 25%)
6. `split-window -h -b -t $session:0.4 -l 50% $hooks_cmd` → Pane 4 (hooks links 50%), Pane 5 (warnings rechts 50%)
7. `split-window -v -t $session:0.5 -l 50% $workers_cmd` → Pane 5 (warnings oben 50%), Pane 6 (workers unten 50%)

## IST — Stellschrauben

### POLL_INTERVAL (Kategorie: Performance)

Zentralisiert in `src/constants.py:20`: `POLL_INTERVAL = 0.5`

- `src/monitor.py:10`: `from .constants import ... POLL_INTERVAL ...` — kein eigener Wert mehr
- `src/ui_mode.py:6`: `from .constants import ... POLL_INTERVAL ...` — kein eigener Wert mehr

Keine Duplikation. Wert muss nur noch an einer Stelle geändert werden. (Umgesetzt in Session 3 via centralize-all-tunable-values in constants.py)

### tmux history-limit (Kategorie: Konfiguration)

Zentralisiert in `src/constants.py:22`: `TMUX_HISTORY_LIMIT = '50000'`

`src/tmux_launcher.py:9`: `from .constants import ... TMUX_HISTORY_LIMIT`
`src/tmux_launcher.py:40`:
```python
subprocess.run(["tmux", "set-option", "-g", "history-limit", TMUX_HISTORY_LIMIT])
```
- Setzt globale tmux Option (nicht session-scoped) — betrifft alle tmux Panes
- Vor dem Setzen wird der Original-Wert gesichert (`get_global_history_limit()`, tmux_launcher.py:98-101)
- Nach dem Session-Aufbau wird der Original-Wert wiederhergestellt (`restore_global_history_limit()`, tmux_launcher.py:103-105)
- Wert jetzt als Konstante in constants.py, kein hardcoded String in tmux_launcher.py mehr

### 7-Pane Layout Split-Ratios (Kategorie: Konfiguration)

Hardcoded Split-Befehle in `src/tmux_launcher.py` (tmux_launcher.py:48-58):
- `-l 50%` — horizontaler Split (left column | right column)
- `-l 30%` — vertikaler Split des Main-Panes (main oben 70% | tokens unten 30%)
- `-l 25%` — vertikaler Split des rechten Panes (rules-oben 25% | subagents-unten 75%)
- `-l 25%` — vertikaler Split des Subagent-Panes (subagents 75% | hooks+warns 25%)
- `-l 50%` — horizontaler Split (hooks links 50% | warns rechts 50%)
- `-l 50%` — vertikaler Split (warnings oben 50% | workers unten 50%)

Keine Config-Parameter. Ratios nicht als Konstanten benannt.

### Session Name Generation (Kategorie: Konfiguration)

`generate_session_name()` in `src/tmux_launcher.py:84-90`:
- Global-Modus: fester Name `"monitor_cc_global"`
- Projekt-Modus: `"monitor_cc_" + MD5(normpath(project_path))[:8]`
- Hash-Länge 8 Zeichen (potenzielle Kollision bei vielen Projekten)

### Logging in Entry/Startup (Kategorie: Observability)

**Stand nach Session 3 (Logging-Entfernung):**

`src/tmux_launcher.py`: **0** `log_tagged()`-Aufrufe. Alle 14 ehemaligen Calls (SPLIT_LAUNCH, SESS_NAME, SCRIPT_PATH, HIST_SET, TMUX_CREATE, TMUX_SPLIT_H, TMUX_SPLIT_V, TMUX_CHECK, TMUX_INSIDE, SESS_EXISTS, SESS_KILL, HIST_ORIG, HIST_RESTORE, TMUX_CONFIG) wurden in Session 3 entfernt.

`workflow.py`: **Stale Logging noch vorhanden** (Stand Worktree). workflow.py:1-14 enthält noch `import logging`, Logger-Setup für `src/logs/01_startup.log`, und `log_tagged()`-Aufruf in `main()` (workflow.py:28). Die Entfernung war als Session-4-Aufgabe geplant.

Gemäss User-Feedback: 0 dieser Logs wurden je zu Debugging-Zwecken konsultiert.

## Evidenz

Pending — needs evaluation.

## Recommendation (SOLL)

Pending — needs evaluation.

## Offene Fragen

- ~~tmux Keybinding für 3. Pane: M-r für Rules-Pane Copy~~ — implementiert, Pane-Index 2 (verifiziert in tmux_launcher.py:127)
- ~~M-w Keybinding: Warnings-Pane Content → Clipboard~~ — implementiert (tmux_launcher.py:130): `M-w` → Pane 5 (warnings)
- M-k Keybinding für Workers-Pane implementiert (tmux_launcher.py:131): `M-k` → Pane 6 (workers)
- workflow.py stale logging (import logging, log_tagged) noch nicht entfernt

## Quellen

- tmux man page: github.com/tmux/tmux `tmux.1` L3591-3648 (split-window), L840-890 (pane targeting)
- dev/display/test_tmux_layout.sh: Pane-Index Verifikation nach verschachtelten Splits
- GitHub anthropics/claude-code #27724: JSONL format undocumented, changes without changelog
- GitHub anthropics/claude-code #33414: FireHose monitoring feature request (kein offizielles Monitoring-API)
