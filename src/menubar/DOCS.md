# src/menubar/

## Role

Standalone macOS status-bar (menubar) application that shows all currently-running Claude Code sessions on this Mac with their working/idle status and background-task badge. Independent of the tmux TUI — launched via `workflow.py --mode menubar` or launchd. macOS only (rumps/AppKit).

## Public Interface

`from src.menubar.menubar import run` — `run()` is the sole entry point. Called by `workflow.py --mode menubar`.

## Flow

1. `run()` → sets `LSUIElement=1` env → instantiates `CCMenuBarApp` → `app.run()` starts AppKit runloop.
2. `CCMenuBarApp._tick()` fires every 1.5s (NSDefaultRunLoopMode) → `list_alive_sessions()` → auto-focus debounce → if menu closed: blink on change + `_rebuild_menu`; if menu open: `_update_menu_inplace`. While menu is open the runloop switches to NSEventTrackingRunLoopMode and `_tick` pauses — `_MenuDelegate.fireTrackingTick_` (tracking-mode NSTimer, 0.5s, NSRunLoopCommonModes) drives `_update_menu_inplace` independently during that window. Background task badge: `[B M:SS]` when Opus sleep timers running, `[B]` otherwise.
3. `list_alive_sessions()` → refreshes CC-process cache (ps/lsof, every 10s) → refreshes Ghostty TTY-to-UUID mapping (OSC 2 probe, incremental) → scans `~/.claude/projects/*/` → picks newest JSONL per project → for workers checks tmux session existence; for mains applies 1h alive window → determines working/idle status per session type → checks `/tmp/claude-<uid>/` for in-progress tasks.
4. Click on a main session → `_focus_session(cwd)` → looks up Ghostty terminal UUID from mapping cache → `focus terminal id "<UUID>"` (Path A) or cwd-match fallback (Path B).

## Modules

### menubar.py (334 LOC)

**Purpose:** `CCMenuBarApp` rumps subclass + `_MenuDelegate` (NSMenuDelegate for live-update) + timer + blink + `_rebuild_menu` + `_update_menu_inplace` + `_focus_session` + `_register_hotkey` + settings load/save + Auto-Jump toggle + `run()` entry point.
**Reads:** `list_alive_sessions()` result on every tick; `get_ghostty_terminal_id(cwd)` on click; `_scan_bg_sleep_timers()` on every tick for `[B M:SS]` badge; `~/.monitor_cc_menubar_settings.json` on launch.
**Writes:** `app.title` (icon only), `app.menu` (dropdown items via full rebuild or in-place `setAttributedTitle_`); `~/.monitor_cc_menubar_settings.json` on toggle.
**Called by:** `workflow.py` (`--mode menubar` route).
**Calls out:** `rumps`, `AppKit` (NSAttributedString/NSFont/NSColor), `Foundation` (NSObject/NSTimer/NSRunLoop/NSRunLoopCommonModes for `_MenuDelegate` tracking-mode timer), `subprocess` (osascript for click-to-focus), `threading.Timer`, `ctypes` (Carbon hotkey).

---

### discover.py (397 LOC)

**Purpose:** Session discovery — scans JSONL files, determines working/idle/background status per session type (main vs worker). Provides Ghostty terminal UUID mapping for reliable click-to-focus. Provides `_scan_bg_sleep_timers()` for bar countdown.
**Reads:** `~/.claude/projects/*/` JSONL mtimes + last lines; `/tmp/claude-<uid>/` task dirs; `ps`/`lsof` output (CC process cache); tmux session state; `/dev/ttys<NNN>` device files (OSC 2 marker writes for Ghostty mapping).
**Writes:** `/dev/ttys<NNN>` (transient OSC 2 probe marker + empty-string cleanup). Module-level cache: `_cc_proc_cache`, `_cc_proc_last_refresh`, `_ghostty_tty_to_id`, `_ghostty_tty_last_refresh`, `_tmux_state_cache`, `_tmux_state_last_refresh`.
**Called by:** `menubar.py:CCMenuBarApp._tick` (`list_alive_sessions`, `_scan_bg_sleep_timers`), `menubar.py:_focus_session` (`get_ghostty_terminal_id`).
**Calls out:** `session_finder.get_project_directories`; `subprocess` (ps, lsof, tmux, osascript).

---

## State

| Variable | Module | Type | Owner | Description |
|---|---|---|---|---|
| `CCMenuBarApp._last_statuses` | menubar.py | `dict` | app instance | `{name: status}` snapshot for blink-on-change detection; updated every tick (also while menu open) to prevent false blink on re-open. |
| `CCMenuBarApp._idle_since_ts` | menubar.py | `dict` | app instance | `{name: float}` timestamps when each main session first went idle (debounce for auto-focus). Cleared on working or has_bg=True. |
| `CCMenuBarApp._menu_open` | menubar.py | `bool` | app instance | True while NSMenu is displayed; set by `_MenuDelegate.menuWillOpen_` / `menuDidClose_`. Gates `_tick` between full rebuild and in-place update. |
| `CCMenuBarApp._displayed_items` | menubar.py | `dict` | app instance | `{name: rumps.MenuItem}` populated by `_rebuild_menu`; used by `_update_menu_inplace` for O(1) item lookup. Keyed by `s.name` (same caveat as `_last_statuses` for same-name collisions across projects). |
| `CCMenuBarApp._toggle_item` | menubar.py | `rumps.MenuItem` | app instance | Ref to the Auto-Jump toggle item; kept for potential in-place label update. Refreshed on each full rebuild. |
| `CCMenuBarApp._auto_focus` | menubar.py | `bool` | app instance | Whether auto-focus is enabled. Loaded from settings JSON on launch; toggled and saved on menu click. Default OFF. |
| `CCMenuBarApp._menu_delegate` | menubar.py | `_MenuDelegate` | app instance | PyObjC NSObject instance set as NSMenu delegate. Held as instance attr to prevent ARC garbage collection. |
| `_MenuDelegate._tracking_timer` | menubar.py | `NSTimer \| None` | delegate instance | Repeating NSTimer (0.5s, NSRunLoopCommonModes) started in `menuWillOpen_`, invalidated in `menuDidClose_`. Drives `fireTrackingTick_` → `_update_menu_inplace` during NSEventTrackingRunLoopMode when `_tick` is paused. None when menu is closed. |
| `_cc_proc_cache` | discover.py | `Dict[pid, (tty, cwd)]` | module | CC processes. Incremental: `ps -A` every 10s drops gone PIDs; `lsof -d cwd` only for newly seen PIDs (cwd is stable after launch). Steady-state: ~75ms (ps only). |
| `_cc_proc_last_refresh` | discover.py | `float` | module | Timestamp of last CC cache pass. |
| `_ghostty_tty_to_id` | discover.py | `Dict[str, str]` | module | tty → Ghostty terminal UUID. Populated incrementally by OSC 2 probe. |
| `_ghostty_tty_last_refresh` | discover.py | `float` | module | Timestamp of last probe cycle (updated only when a probe actually ran). |
| `_tmux_state_cache` | discover.py | `Dict[str, (bool, int)]` | module | session_name → (alive, session_activity unix ts). One `tmux list-sessions` call per 3s replaces per-worker `has-session` + `display-message` pairs. |
| `_tmux_state_last_refresh` | discover.py | `float` | module | Timestamp of last tmux state refresh. |

## Activity Detection (per session type)

**Workers** (tmux sessions):
- Alive iff `tmux has-session -t =worker-{project_basename}-{worker_name}` returns 0. Exact-match `=` prefix prevents prefix-matching false positives.
- Session name reconstructed from worker JSONL cwd: split on `/.claude/worktrees/`, `basename(left)` = project basename.
- Status: `tmux display-message -p '#{window_activity}'` → unix timestamp; `working` if age ≤ 10s.
- Fallback (cwd unreadable): `ALIVE_WINDOW_SECS=3600` JSONL age check + 10s mtime threshold.

**Mains** (Ghostty terminals):
- Alive if JSONL mtime within `ALIVE_WINDOW_SECS=3600` (1h).
- Status: JSONL mtime ≤ `WORKING_THRESHOLD_SECS=10s` = working. TTY mtime removed (cursor blinks keep TTY fresh while CC window is focused → stuck-at-working bug).
- TTY still used for click-to-focus UUID lookup via `_cc_proc_cache`; not used for working detection.
- Auto-focus: on `working → idle` transition with `has_bg=False`, `_focus_session(cwd)` fires after a 3s debounce (`_idle_since_ts` dict). Prevents spurious focus from short JSONL-mtime gaps during streaming.

## Title-Marker Mapping (tty → Ghostty terminal UUID)

**Problem:** Ghostty's AppleScript `working directory` property reflects the PTY's initial cwd, not the shell's current cwd. `focus (first terminal whose working directory is "...")` fails for sessions where the shell ran `cd X && python3 workflow.py --project Y` — Ghostty shows `X`, CC runs in `Y`. Ghostty does NOT expose `tty` or `pid` via AppleScript.

**Solution:** OSC 2 title-marker bootstrap. Each Ghostty tab has a direct child process (login shell) with a known TTY device (`/dev/ttys<NNN>`). Writing `\033]2;<marker>\007` to that device sets the Ghostty tab's `name` property. An AppleScript query immediately after returns `id|||name` pairs → marker appears in `name` → we learn the UUID for that TTY.

**Probe flow** (`_refresh_ghostty_tty_to_id`):

1. `ps -A -o pid=,command=` parsed for `Ghostty.app/Contents/MacOS` → Ghostty PID.
2. `ps -A -o pid=,ppid=,tty=` filtered by ppid = Ghostty PID → all current TTYs (`all_ttys`).
3. **Stale cleanup**: remove `_ghostty_tty_to_id` entries whose TTY is no longer in `all_ttys` (closed tabs).
4. **Incremental filter**: `new_ttys = [t for t in all_ttys if t not in _ghostty_tty_to_id]`. If empty → return immediately, **no title flash, no sleep**.
5. Write `\033]2;__GHT_<8-hex-random>\007` to each `/dev/<new_tty>`.
6. `time.sleep(0.12)` — 120ms for Ghostty to process the OSC 2 sequence.
7. `osascript` → all terminals `id|||name` pairs (newline-separated).
8. **Cleanup**: write `\033]2;\007` (empty string) to each probed TTY → shell restores its default title.
9. Match markers to IDs → merge into `_ghostty_tty_to_id`.
10. Update `_ghostty_tty_last_refresh = now` **only if probe ran** (step 4 found new TTYs).

**Steady-state behavior:**
- Initial launch: one probe cycle covers all open Ghostty tabs → cache fully populated.
- New terminal opened: detected on next tick after TTL expires (≤10s) → single-tab probe.
- No new terminals: TTL check passes, lightweight subprocess check runs, returns immediately. No sleep, no title flash.
- Closed terminal: stale entry removed on next lightweight check.

**Lookup** (`get_ghostty_terminal_id(cwd)`):
1. `_tty_for_cwd(cwd)` → TTY from `_cc_proc_cache`.
2. `_ghostty_tty_to_id.get(tty)` → UUID or None.

**Workers not affected**: CC processes inside tmux panes have a tmux-allocated PTY (different from the Ghostty tab's TTY). Workers never appear in `_ghostty_tty_to_id`. Workers also have no click callback in the menu.

## Gotchas

- `app.menu = [...]` clears the entire menu including the quit button. `_rebuild_menu` always re-appends `app._quit_button` explicitly.
- Background task detection: `/tmp/claude-<uid>/` uses the numeric Unix UID (`os.getuid()`). `*.output` files with `st_size == 0` = in-progress; `done\n` (5 bytes) = completed.
- `LSUIElement=1` must be set before `app.run()` to suppress the Dock icon. Set in `run()` via `os.environ.setdefault`.
- Launched via launchd: `KeepAlive=true` auto-restarts on crash. Logs → `/tmp/monitor_cc_menubar.{log,err}`.
- **Ghostty PID lookup**: `pgrep` is unreliable on macOS for full-path binary names (`pgrep -x ghostty` and `pgrep -f Ghostty.app/Contents/MacOS` both return empty intermittently). Use `ps -A -o pid=,command=` parsed directly: `'Ghostty.app/Contents/MacOS' in line` finds the process robustly.
- **Ghostty AppleScript**: Ghostty.sdef exposes `id` (UUID, stable), `name` (current title), `working directory` per `terminal`. `focus` command takes a specifier: `focus terminal id "<UUID>"`. Does NOT expose `tty` or `pid`.
- **OSC 2 cleanup**: After the probe, `\033]2;\007` (empty-string OSC 2) written to the probed TTYs restores the shell's default title (CWD from PROMPT_COMMAND / precmd hook). Without cleanup, idle shells show `__GHT_XXXXXXXX` until next prompt display.
- **TTY ownership**: Ghostty children run as `/usr/bin/login` (root) but the `/dev/ttys<NNN>` device files are owned by the logged-in user → write access OK.
- **tmux exact-match**: `tmux has-session -t name` uses prefix matching; `=name` enforces exact match. `display-message -t name` works correctly once the session is confirmed to exist (no `=` needed there — exact match preferred before prefix by tmux's resolution order).
- **Badge column alignment**: Status badges `[*]`/`[ ]` are fixed-width (3 chars). Background task badge `[B M:SS]` is variable-width (3–9 chars); `_NO_BG` spacer is 3 chars. Nothing follows the badge, so variable width causes no column misalignment.
- **Global hotkey Cmd+L**: registered in `CCMenuBarApp.__init__` via Carbon `RegisterEventHotKey` (ctypes, no pyobjc-framework-Carbon, no extra permissions). keycode 37 (`kVK_ANSI_L`), modifier `0x0100` (cmdKey). Callback fires on NSApp's CFRunLoop and calls `nsstatusitem.button().performClick_(None)` to open the dropdown. `app._hotkey_cb` and `app._hotkey_ref` are held on the instance to prevent GC of the ctypes callback.
- **Sleep-countdown detection** (`_scan_bg_sleep_timers`): scans `ps -A -o pid=,ppid=,etime=,args=` every tick (1.5s). Matches child processes with args exactly `sleep N` whose parent args contain `echo done` (the Opus background-timer signature `bash -c "sleep N && echo done"`). Uses `_parse_etime` to decode ps etime format → remaining = max(0, N − elapsed). Returns min across all matches. False-positive risk: another `sh -c "sleep N && echo done"` process — low probability, acceptable.
- **NSMenuDelegate bridging**: `_MenuDelegate(NSObject)` with `menuWillOpen_` / `menuDidClose_` (pyobjc underscore-for-colon). pyobjc bridges these automatically via AppKit protocol metadata. If bridging silently fails (delegate methods don't fire), fallback: declare `class _MenuDelegate(NSObject, protocols=[objc.protocolNamed('NSMenuDelegate')])`. The `_menu_delegate` instance attr on CCMenuBarApp is mandatory — without it, ARC collects the delegate immediately after `__init__` returns. **Lazy-init pattern**: `rumps.App._nsapp` is only populated by `app.run()`, NOT by `__init__` — calling `self._nsapp...` in `__init__` raises `AttributeError`. Delegate setup therefore happens in the first `_tick` call (guarded by `if self._menu_delegate is None`), which fires after the AppKit run-loop starts. `__init__` only sets `self._menu_delegate = None` as a sentinel.
- **In-place update coverage**: `_update_menu_inplace` only updates sessions already in `_displayed_items` (populated by the last closed-state `_rebuild_menu`). Sessions that appear or disappear while the menu is open are deferred to the next full rebuild after close. The toggle item is not updated in-place (clicking it closes the menu, triggering a full rebuild with new state).
- **Settings file** (`~/.monitor_cc_menubar_settings.json`): single JSON `{"auto_focus": bool}`. Written atomically via tempfile + `os.replace`. Read on launch; any parse error → default OFF. The `.tmp` suffix is used for the temp file; a crashed write leaves `~/.monitor_cc_menubar_settings.json.tmp` as debris (harmless — overwritten on next save).
- **RunLoop mode freeze**: `@rumps.timer` schedules NSTimers in `NSDefaultRunLoopMode`. When the NSStatusItem menu opens, AppKit switches the run-loop to `NSEventTrackingRunLoopMode` — NSDefaultRunLoopMode timers stop firing. This means `_tick` (and therefore `_update_menu_inplace`) is never called while the dropdown is open. Fix: `_MenuDelegate` creates a separate NSTimer scheduled in `NSRunLoopCommonModes` (`menuWillOpen_` → `NSRunLoop.currentRunLoop().addTimer_forMode_(..., NSRunLoopCommonModes)`). CommonModes covers both Default and EventTracking, so `fireTrackingTick_` fires at 0.5s even during menu tracking. The timer is invalidated in `menuDidClose_`. Empirically verified: 10-second menu-open window produced zero `_tick` calls; tracking-mode timer restores live updates at 0.5s intervals.
