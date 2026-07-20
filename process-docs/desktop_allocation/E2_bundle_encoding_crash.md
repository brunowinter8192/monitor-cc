# E2 — Bundle Encoding Crash: UnicodeDecodeError(ascii) → empty cwd_desktop Sidecar (2026-05-29)

## Problem

After the Stage-2 deploy (E1 sidecar write + blank consumer + py2app rebuild/reinstall + menubar relaunch), `cwd_desktop.json` is created but stays `{}`. The launchd-spawned py2app bundle crashes EVERY detection cycle → `_cwd_desktop_lkg` never fills → blank's `desktop_targeting.py` falls back to the active desktop → Stage 2 (worker spawn + `show` file-open on the caller main's desktop) is, despite the full deploy, **not functional live**.

Production status at the time: deployed but non-functional. Blocking the live-verify.

## Evidence

`~/Library/Application Support/com.brunowinter.monitor_cc_menubar/menubar.log` (running bundle PID 70723, started 02:33 from the rebuilt bundle):

```
[detection] all_failed n_mains=1 reason=error:UnicodeDecodeError('ascii', b'tab-group-600002aa1c20|||\xe2\xa0\x82 Open Tasks ...
[detection] all_failed n_mains=0 reason=error:UnicodeDecodeError('ascii', b'    1 /sbin/launchd\n  495 /Library/Apple/System/L ...
```

- TWO crash sources: `ps -A` output (`1 /sbin/launchd ...`) AND AppleScript Ghostty window/tab names (`tab-group-...|||⠂ Open Tasks`).
- Bytes `\xe2\xa0\x82` = UTF-8 for U+2802 (⠂), the Claude Code spinner glyph. Plus German text "Open Tasks". Non-ASCII subprocess output decoded as ASCII → crash.
- Caught by `detect_main_desktop_numbers`'s outer `except Exception` → logged as `all_failed reason=error:...`.
- ONE success at 22:40:50 (`osc2_match tty=ttys051 wid=5582` → `transition None->2 n_cand=12`): the detection LOGIC works when decoding succeeds — the crash is purely the decoding.

## NOT TCC

Screen-recording permission WAS granted (System Settings → Screen Recording: Monitor_CC_Menubar toggle ON, screenshot 2026-05-29). So the blocker is the encoding crash, not a missing screen-recording grant. The earlier Stage-2 TCC hypothesis is superseded by this evidence.

## Root-Cause Hypothesis

The launchd-spawned py2app bundle runs without a UTF-8 locale (no LANG/LC_ALL in the launchd env) → Python's default text decoding for subprocess output is ASCII → every non-ASCII byte (spinner glyph, German window title) throws UnicodeDecodeError.

Candidates:
- A `subprocess.run(...)` in the detection path without `encoding='utf-8'` (+ `errors='replace'`) — despite the C4 fix on `_ghostty_pid_int` + `_applescript_uuid_window_map`. The `ps` crash points at a further call (discover.py / proc_cache.py ps calls?).
- OR bundle-wide: set `PYTHONIOENCODING=utf-8` / `LANG` in the py2app launchd plist or `menubar_main.py` entry, so ALL subprocess decodes default to UTF-8 (belt-and-suspenders, covers all calls).

## Fix Direction (target — pending)

Force UTF-8 in the detection path: either per-call (`encoding='utf-8', errors='replace'` on every subprocess.run in the detection chain — audit ps + osascript calls in desktop_detection.py, discover.py, proc_cache.py) OR a bundle-wide locale (PYTHONIOENCODING/LANG in the launchd env). Bundle-wide is more robust. Then rebuild (setup_py2app) + reinstall (~/Applications) + relaunch + re-verify that cwd_desktop.json fills.

Caveat: rebuild+reinstall (rm+cp) produces a fresh py2app code signature. The TCC screen-recording grant might be bound to the previous signature; if detection still returns empty CGWindow results AFTER the encoding fix → re-grant (System Settings → Screen Recording → remove the old entry with `−`, add the new ~/Applications app with `+`).

## Status

**RESOLVED (2026-05-29).** The per-call encoding fix (C4: all 13 `subprocess.run(text=True)` calls given `encoding='utf-8', errors='replace'` + `PYTHONUTF8=1` in the plist) was already in the `src/` code at the time of the E2 diagnosis — the crashing bundle observed at the time was stale (built before C4). It was rebuilt/reinstalled since:

- Running bundle: executable mtime **02:30** (after C4), PID 96325 since 02:45.
- Last `UnicodeDecodeError` **2026-05-28T22:54:59** — all 87 crashes historical, none since the current PID started.
- `cwd_desktop.json` fills: `Monitor_CC → space_id 780, desktop_no 2`.
- The user re-granted the screen-recording TCC permission to the 02:30 bundle (addresses the separate `cgw_list_empty` weakness).

A rebuild (03:18) done during this session was **NOT deployed** — identical code to the running 02:30 bundle; a redeploy would only have carried the TCC-signature-break risk with no benefit.

**Remaining (separate topic, not follow-up here):** intermittent `all_no_match` / `cgw_list_empty no_names_returned` in detection — TCC/CGWindowList visibility, not encoding. The sidecar still works via the `osc2_match` path. If detection becomes unreliable → own tracking task.

## Sources

- `~/Library/Application Support/com.brunowinter.monitor_cc_menubar/menubar.log` (`[detection]` entries)
- `src/menubar/desktop_detection.py` (`detect_main_desktop_numbers` + subprocess calls)
- `setup_py2app.py` (bundle build — launchd env)
- System Settings → Screen Recording (TCC grant confirmed, 2026-05-29)
