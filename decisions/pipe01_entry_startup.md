# Pipe Section: Entry & Startup

## Status Quo

- `workflow.py`: `--mode all` → tmux 4-Window (main+tokens | proxy+metadata | workers+worker-proxy+worker-metadata | warnings), `--mode main|rules|warnings|hooks|tokens|workers|proxy|metadata|worker-proxy|worker-metadata|restart-panes` → einzelner Prozess
- `startup.py`: argparse mit choices `['all', 'main', 'rules', 'warnings', 'hooks', 'tokens', 'workers', 'proxy', 'metadata', 'worker-proxy', 'worker-metadata', 'restart-panes']`, `--project`
- `tmux_launcher.py`: 4 Windows (10 Panes), history 50000, keybindings (C-q scroll, C-r restart all panes, C-f search, mouse, M-m/M-t/M-p/M-r/M-h/M-k/M-w copy)

tmux Layout (4 Windows):
```
Window 0 "main":    Main (0.0, left 70%)   | Tokens (0.1, right 30%)
Window 1 "proxy":   Proxy (1.0, left 70%)  | Metadata (1.1, right 30%)
Window 2 "workers": Workers (2.0, 34%)     | Worker-Proxy (2.1, 33%) | Worker-Metadata (2.2, 33%)
Window 3 "debug":   Warnings (3.0, fullscreen)
```
Switch windows: Ctrl-b 0/1/2/3

Window-Erstellung:
1. `new-session -d -s $session $main_cmd` → Window 0, Pane 0.0
2. `rename-window -t $session:0 "main"`
3. `split-window -h -t $session:0.0 -l 30% $tokens_cmd` → Pane 0.1
4. `new-window -t $session:1 -n "proxy" $proxy_cmd` → Window 1, Pane 1.0
5. `split-window -h -t $session:1.0 -l 30% $metadata_cmd` → Pane 1.1
6. `new-window -t $session:2 -n "workers" $workers_cmd` → Window 2, Pane 2.0
7. `split-window -h -t $session:2.0 -l 66% $worker_proxy_cmd` → Pane 2.1
8. `split-window -h -t $session:2.1 -l 50% $worker_metadata_cmd` → Pane 2.2
9. `new-window -t $session:3 -n "debug" $warnings_cmd` → Window 3, Pane 3.0
10. `select-window -t $session:0` → Main window active on attach

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

### 5-Window Layout Split-Ratios (Kategorie: Konfiguration)

Hardcoded Split-Befehle in `src/tmux_launcher.py`:
- Window 0: `-l 30%` — horizontaler Split (main links 70% | tokens rechts 30%)
- Window 1: `-l 30%` — horizontaler Split (proxy links 70% | metadata rechts 30%)
- Window 2: `-l 50%` — horizontaler Split (rules links 50% | hooks rechts 50%)
- Window 3: two splits — `-l 66%` (workers 34% | rest 66%), then `-l 50%` on 3.1 (worker-proxy | worker-metadata each ~33%)
- Window 3: kein Split — warnings fullscreen

Keine Config-Parameter. Ratios nicht als Konstanten benannt.

### Session Name Generation (Kategorie: Konfiguration)

`generate_session_name()` in `src/tmux_launcher.py:84-90`:
- Global-Modus: fester Name `"monitor_cc_global"`
- Projekt-Modus: `"monitor_cc_" + MD5(normpath(project_path))[:8]`
- Hash-Länge 8 Zeichen (potenzielle Kollision bei vielen Projekten)

### Logging in Entry/Startup (Kategorie: Observability)

**Stand nach Session 3 (Logging-Entfernung):**

`src/tmux_launcher.py`: **0** `log_tagged()`-Aufrufe. Alle 14 ehemaligen Calls (SPLIT_LAUNCH, SESS_NAME, SCRIPT_PATH, HIST_SET, TMUX_CREATE, TMUX_SPLIT_H, TMUX_SPLIT_V, TMUX_CHECK, TMUX_INSIDE, SESS_EXISTS, SESS_KILL, HIST_ORIG, HIST_RESTORE, TMUX_CONFIG) wurden in Session 3 entfernt.

`workflow.py`: **0** `log_tagged()`-Aufrufe. `import logging`, Logger-Setup (`log_format`, `logger_startup`, `startup_handler`), `MAGENTA`-Import und `log_tagged()`-Aufruf in `main()` wurden in Session 4 entfernt.

Gemäss User-Feedback: 0 dieser Logs wurden je zu Debugging-Zwecken konsultiert.

## Evidenz

Pending — needs evaluation.

## Recommendation (SOLL)

Pending — needs evaluation.

## Offene Fragen

- ~~tmux Keybinding für 3. Pane: M-r für Rules-Pane Copy~~ — implementiert, `session:1.0` (verifiziert in tmux_launcher.py:129)
- ~~M-w Keybinding: Warnings-Pane Content → Clipboard~~ — implementiert (tmux_launcher.py): `M-w` → `session:4.0` (warnings)
- M-k Keybinding für Workers-Pane implementiert (tmux_launcher.py): `M-k` → `session:3.0` (workers)
- ~~workflow.py stale logging (import logging, log_tagged)~~ — entfernt in Session 4

## Quellen

- tmux man page: github.com/tmux/tmux `tmux.1` L3591-3648 (split-window), L840-890 (pane targeting)
- dev/display/test_tmux_layout.sh: Pane-Index Verifikation nach verschachtelten Splits
- GitHub anthropics/claude-code #27724: JSONL format undocumented, changes without changelog
- GitHub anthropics/claude-code #33414: FireHose monitoring feature request (kein offizielles Monitoring-API)
