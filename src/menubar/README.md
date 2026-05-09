# Monitor_CC Menubar

macOS status-bar indicator for live Claude Code sessions. Shows all active CC sessions with working/idle status and background-task badge. Updates every 1.5s.

## Manual run

```bash
cd /path/to/Monitor_CC
./venv/bin/python3 workflow.py --mode menubar
```

The `◉` icon appears in the menu bar. Click it to see active sessions.

## Auto-start via launchd

1. **Edit the plist** — replace `<PROJECT_ROOT>` with the absolute path to your Monitor_CC directory:

```bash
sed 's|<PROJECT_ROOT>|/path/to/Monitor_CC|g' \
  src/menubar/com.brunowinter.monitor_cc_menubar.plist \
  > ~/Library/LaunchAgents/com.brunowinter.monitor_cc_menubar.plist
```

2. **Load the agent:**

```bash
launchctl load ~/Library/LaunchAgents/com.brunowinter.monitor_cc_menubar.plist
```

3. **Check it started:**

```bash
launchctl list | grep monitor_cc_menubar
# Should show a PID in the first column
```

4. **Logs** — stdout/stderr go to `/tmp/monitor_cc_menubar.log` and `.err`.

## Stop / unload

```bash
launchctl unload ~/Library/LaunchAgents/com.brunowinter.monitor_cc_menubar.plist
```

## Menu layout

```
◉                          ← status-bar icon (blinks on change)
├ Monitor_CC  🟢 [B]       ← working + background task in flight
├ RAG         🔴           ← idle, no background task
└ Quit
```

- `🟢` = last JSONL write ≤ 10s ago (working)
- `🔴` = last JSONL write > 10s ago (idle)
- `[B]` = a background task (`Bash run_in_background=true`) is still running
