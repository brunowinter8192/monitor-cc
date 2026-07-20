# C4 — Subprocess ASCII-Locale UnicodeDecodeError: Root Cause + Fix

## Root Cause

**Confirmed by the live APP_SUPPORT log (2026-05-28 ~22:39–22:41):**

```
22:39:XX [detection] all_failed n_mains=1 reason=error:UnicodeDecodeError('ascii', b'    1 /sbin/launchd...
22:40:50 [detection] transition Monitor_CC/Monitor_CC None->2 win=... n_cand=1
22:40:59 [detection] all_failed n_mains=1 reason=error:UnicodeDecodeError('ascii', b'...\xe2\xa0\x90 Open Tasks...')
```

Two crash sites confirmed by log evidence:
- `22:39` — `ps -A -o pid=,command=` (`desktop_detection.py:170`) — worker-spawn prompt with emojis/umlauts in argv
- `22:40:59` — `osascript` (`desktop_detection.py:196`) — Ghostty tab title contained `'⠐ Open Tasks'` (CC spinner + German text)

**Mechanism:** launchd sets no locale → `locale.getpreferredencoding()` = `'ascii'` →
`subprocess.run(..., text=True)` decodes stdout as ASCII → `ps -A -o command=` returns
the full argv of all processes → a CC worker has its spawn prompt in argv (emoji,
umlauts) → `UnicodeDecodeError` → `detect_main_desktop_numbers`'s try/except catches it
→ `all_failed` → desktop number gone for all mains as long as the worker runs.

The same mechanism affects every other `text=True` call under the ASCII locale:
osascript (window titles), lsof (cwd paths), tmux, the bd CLI (bead content with
emojis).

## Full Audit — All Affected `text=True` Calls in `src/menubar/`

| File:Line (pre-fix) | Command | Non-ASCII possible | Confirmed |
|---|---|---|---|
| `desktop_detection.py:170` | `ps -A -o pid=,command=` | worker-argv emojis/umlauts | **CRASH (22:39)** |
| `desktop_detection.py:196` | `osascript` (Ghostty window/tab names) | `'⠐ Open Tasks'` | **CRASH (22:40:59)** |
| `ghostty.py:95` | `ps -A -o pid=,command=` | identical vector | latent |
| `bg_timer.py:48` | `ps -A -o pid=,ppid=,etime=,args=` | `args=` = full argv | latent |
| `ghostty.py:66` | `osascript` (terminal id\|\|\|name) | other terminal names | latent |
| `proc_cache.py:64` | `ps -A -o pid,tty,comm` | comm = executable basename | low |
| `proc_cache.py:83` | `lsof -a -d cwd -p pid` | non-ASCII cwd paths | low |
| `proc_cache.py:103` | `tmux list-sessions -F #{session_name}` | session names | low |
| `proc_cache.py:120` | `tmux display-message #{window_activity}` | integer — SAFE | SAFE |
| `ghostty.py:109` | `ps -A -o pid=,ppid=,tty=` | digits + device names only — SAFE | SAFE |
| `bead_data.py:38` | `bd show --json` | bead title/description with emojis | latent |
| `bead_data.py:70` | `bd comments --json` | comment text | latent |
| `bead_data.py:118` | `bd list -l tracked --json` | bead metadata | latent |

Already safe (no `text=True`, manual `.decode(errors='replace')`): `system.py`,
`setup_menubar.py`, `queue.py`, `hook_writer.py`.

## Fix (Option c — both layers)

### Primary: per-call `encoding='utf-8', errors='replace'`

All 13 `text=True` calls in the 5 affected modules get:
```python
capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=N
```

- `errors='replace'` → invalid bytes become U+FFFD, no crash possible
- Effective in **every** launch mode (launchd, `open`, Finder, dev)
- A `?` in place of an invalid byte is not falsely matched by any of our pattern
  matches (`'Ghostty.app/Contents/MacOS' in line`, `'claude' in parts[2].lower()`,
  etc.) → the line is silently skipped (correct)

### Belt-and-Suspenders: `PYTHONUTF8=1` in the LaunchAgent plist template

`src/menubar/com.brunowinter.monitor_cc_menubar.plist` → `EnvironmentVariables`:
```xml
<key>PYTHONUTF8</key>
<string>1</string>
```

PEP 540 (Python 3.7+): forces UTF-8 for all `text=True` subprocess decodes and `open()`
in the process. Effective in the launchd context (production deploy). The installed
plist under `~/Library/LaunchAgents/` gets regenerated from the template by
`write_plist_py2app()` on the next Restart-button click — Opus deploys manually for
immediate effect.

`PYTHONUTF8=1` alone does not protect against invalid-UTF-8 bytes (default
`errors='strict'` remains) and not against `open`/Finder launch — hence the per-call fix
is primary.
