# Pipe Section: Entry & Startup

## State as of this section's audit

- `workflow.py`: `--mode all` → tmux 6-window (main+tokens | proxy | workers+worker-proxy | warnings | gpu | news+news-log), `--mode main|rules|warnings|hooks|tokens|workers|proxy|worker-proxy|gpu|news|news-log|restart-panes` → single process
- `startup.py`: argparse with choices `['all', 'main', 'rules', 'warnings', 'hooks', 'tokens', 'workers', 'proxy', 'worker-proxy', 'restart-panes', 'news', 'news-log']`, `--project`
- `tmux_launcher.py`: 6 windows (9 panes), history 50000, keybindings (C-q scroll, C-r restart all panes, C-f search, mouse, M-m/M-t/M-p/M-k/M-w/M-n copy)

tmux layout (6 windows):
```
Window 0 "main":    Main (0.0, left 70%)   | Tokens (0.1, right 30%)
Window 1 "proxy":   Proxy (1.0, fullscreen)
Window 2 "workers": Workers (2.0, 34%)     | Worker-Proxy (2.1, 66%)
Window 3 "debug":   Warnings (3.0, fullscreen)
Window 4 "gpu":     GPU (4.0, fullscreen)
Window 5 "news":    News (5.0, left 50%)   | News-Log (5.1, right 50%)
```
Switch windows: Ctrl-b 0/1/2/3/4/5

Window creation:
1. `new-session -d -s $session $main_cmd` → window 0, pane 0.0
2. `rename-window -t $session:0 "main"`
3. `split-window -h -t $session:0.0 -l 30% $tokens_cmd` → pane 0.1
4. `new-window -t $session:1 -n "proxy" $proxy_cmd` → window 1, pane 1.0
5. `new-window -t $session:2 -n "workers" $workers_cmd` → window 2, pane 2.0
6. `split-window -h -t $session:2.0 -l 66% $worker_proxy_cmd` → pane 2.1
7. `new-window -t $session:3 -n "debug" $warnings_cmd` → window 3, pane 3.0
8. `new-window -t $session:4 -n "gpu" $gpu_cmd` → window 4, pane 4.0
9. `new-window -t $session:5 -n "news" $news_cmd` → window 5, pane 5.0
10. `split-window -h -t $session:5.0 -l 50% $news_log_cmd` → pane 5.1
11. `select-window -t $session:0` → main window active on attach

### POLL_INTERVAL (category: performance)

Centralized in `src/constants.py:20`: `POLL_INTERVAL = 0.5`

- `src/core/monitor.py:10`: `from .constants import ... POLL_INTERVAL ...` — no own value anymore

No duplication. The value now only needs to change in one place. (Implemented in session 3 via centralize-all-tunable-values in constants.py.)

### tmux history-limit (category: configuration)

Centralized in `src/constants.py:22`: `TMUX_HISTORY_LIMIT = '50000'`

`src/tmux_launcher.py:9`: `from .constants import ... TMUX_HISTORY_LIMIT`
`src/tmux_launcher.py:40`:
```python
subprocess.run(["tmux", "set-option", "-g", "history-limit", TMUX_HISTORY_LIMIT])
```
- Sets a global tmux option (not session-scoped) — affects all tmux panes
- The original value is saved before setting it (`get_global_history_limit()`, tmux_launcher.py:98-101)
- The original value is restored after session setup (`restore_global_history_limit()`, tmux_launcher.py:103-105)
- The value now lives as a constant in constants.py, no more hardcoded string in tmux_launcher.py

### Split Ratios (category: configuration)

Hardcoded split commands in `src/tmux_launcher.py`:
- Window 0: `-l 30%` — horizontal split (main left 70% | tokens right 30%)
- Window 1: no split — proxy fullscreen
- Window 2: `-l 66%` (workers 34% | worker-proxy 66%)
- Window 3: no split — warnings fullscreen
- Window 4: no split — gpu fullscreen
- Window 5: `-l 50%` (news left 50% | news-log right 50%)

No config parameters. Ratios not named as constants.

### Session Name Generation (category: configuration)

`generate_session_name()` in `src/tmux_launcher.py:84-90`:
- Global mode: fixed name `"monitor_cc_global"`
- Project mode: `"monitor_cc_" + MD5(normpath(project_path))[:8]`
- Hash length 8 chars (potential collision with many projects)


## Evidence

No dev/ measurements exist for entry/startup claims.

`dev/display/test_tmux_layout.sh` is the only script with a tmux connection — it verifies pane indices after nested splits for an old 3-pane layout and produces no persistent report MD (the session is auto-deleted after output). Per the evidence spec (documentation.md): scripts without quantitative measurement data are not evidence.

All other dev/ subdirs concern other pipeline stages (pipe02/03: `pipeline/`, `session_analysis/`; proxy: `tool_injection/`, `proxy/`, `tool_use_analysis/`; infrastructure: `cc_source_research/`, `ram_audit/`).

Current-state sources for POLL_INTERVAL (0.5), TMUX_HISTORY_LIMIT (50000, save/restore), split ratios, session-name format, and logging (0 calls) are code-read-derived — no dev/ benchmark backing.

## Recommendation (target state)

Pending — needs evaluation.

## Open Questions

- ~~M-w keybinding: warnings-pane content → clipboard~~ — implemented (tmux_launcher.py): `M-w` → `session:3.0` (warnings)
- M-k keybinding for the workers pane implemented (tmux_launcher.py): `M-k` → `session:2.0` (workers)

## Sources

- tmux man page: github.com/tmux/tmux `tmux.1` L3591-3648 (split-window), L840-890 (pane targeting)
- GitHub anthropics/claude-code #27724: JSONL format undocumented, changes without changelog
- GitHub anthropics/claude-code #33414: FireHose monitoring feature request (no official monitoring API)
