# src/menubar/

## Role

Standalone macOS status-bar (menubar) application that shows all currently-running Claude Code sessions on this Mac with their working/idle status and background-task badge. Independent of the tmux TUI — launched via `workflow.py --mode menubar` or launchd. macOS only (rumps/AppKit).

## Public Interface

`from src.menubar.menubar import run` — `run()` is the sole entry point. Called by `workflow.py --mode menubar`.

## Flow

1. `run()` → sets `LSUIElement=1` env → instantiates `CCMenuBarApp` → `app.run()` starts AppKit runloop.
2. `CCMenuBarApp._tick()` fires every 1.5s (NSDefaultRunLoopMode, uninterrupted — NSPanel does not trigger NSEventTrackingRunLoopMode) → `list_alive_sessions()` → auto-focus debounce → if panel closed: blink on status change; `_rebuild_panel` only on session-set change (new/removed sessions); if panel open: pre-compute `_scan_bg_sleep_timers()` → on None↔Some transition or session-set change call `_rebuild_panel` (adds/removes abort button, grows panel), otherwise `_update_panel_inplace` (updates NSButton attributed titles only, no resize). Background task badge: `[B M:SS]` when Opus sleep timers running, `[B]` otherwise. `⊗ abort timer` button appears below separator when timers present; click kills sleep PIDs + writes `aborted\n` to 0-byte task files.
3. `list_alive_sessions()` → refreshes CC-process cache (ps/lsof, every 10s) → refreshes Ghostty TTY-to-UUID mapping (OSC 2 probe, incremental) → scans `~/.claude/projects/*/` → picks newest JSONL per project → for workers checks tmux session existence; for mains applies 1h alive window → determines working/idle status per session type → checks `/tmp/claude-<uid>/` for in-progress tasks.
4. Click on a main session → `_focus_session(cwd)` → looks up Ghostty terminal UUID from mapping cache → `focus terminal id "<UUID>"` (Path A) or cwd-match fallback (Path B).

## Modules

### menubar.py (559 LOC)

**Purpose:** `CCMenuBarApp` rumps subclass + `_PanelController` (NSObject target for panel toggle/focus/restart/abort + `windowDidResize_` delegate) + `_PanelContentView` (NSView subclass as panel contentView, owns NSTrackingArea for resize cursors) + NSPanel sticky-toggle dropdown with grow-only dynamic height + drag-resize (left/bottom/right edges) + timer + blink + `_rebuild_panel` + `_update_panel_inplace` + `_compute_required_height` + `_resize_panel` + `_focus_session` + `_register_hotkey` + settings load/save + Auto-Jump toggle + `run()` entry point.
**Reads:** `list_alive_sessions()` result on every tick; `get_ghostty_terminal_id(cwd)` on click; `_scan_bg_sleep_timers()` on every tick for `[B M:SS]` badge + abort button visibility; `~/.monitor_cc_menubar_settings.json` on launch.
**Writes:** `app.title` (icon only), NSButton attributed titles in NSStackView (full rebuild or in-place `setAttributedTitle_`); `~/.monitor_cc_menubar_settings.json` on toggle. On abort: `os.kill(SIGTERM)` to sleep PIDs + `'aborted\n'` to 0-byte task files (via `_abort_bg_sleep_timers`).
**Called by:** `workflow.py` (`--mode menubar` route).
**Calls out:** `rumps`, `AppKit` (NSAttributedString/NSBox/NSButton/NSFont/NSColor/NSPanel/NSStackView/NSTextField/NSView), `Foundation` (NSObject/NSMakeRect/NSMakeSize for `_PanelController` + panel layout), `subprocess` (osascript for click-to-focus, launchctl for restart), `threading.Timer`, `ctypes` (Carbon hotkey).

---

### discover.py (501 LOC)

**Purpose:** Session discovery — scans JSONL files, determines working/idle/background status per session type (main vs worker). Provides Ghostty terminal UUID mapping for reliable click-to-focus. Provides `_scan_bg_sleep_timers()` → `BgSleepInfo` (countdown + sleep PIDs) and `_abort_bg_sleep_timers()` for the abort button. For main sessions: primary status from hook state (`~/.monitor_cc_menubar_hooks.json`); fallback to JSONL mtime and proxy-log override when hooks not installed or stale.
**Reads:** `~/.claude/projects/*/` JSONL mtimes + last lines; `/tmp/claude-<uid>/` task dirs; `ps`/`lsof` output (CC process cache); tmux session state; `/dev/ttys<NNN>` device files (OSC 2 marker writes for Ghostty mapping); `_PROXY_LOG_DIR/api_requests_*.jsonl` mtimes (proxy thinking signal); `~/.monitor_cc_menubar_hooks.json` (hook state, TTL 10s).
**Writes:** `/dev/ttys<NNN>` (transient OSC 2 probe marker + empty-string cleanup). On abort: `signal.SIGTERM` to sleep PIDs + `'aborted\n'` to all 0-byte `*.output` task files under `_TASKS_BASE`. Module-level cache: `_cc_proc_cache`, `_cc_proc_last_refresh`, `_ghostty_tty_to_id`, `_ghostty_tty_last_refresh`, `_tmux_state_cache`, `_tmux_state_last_refresh`, `_proxy_log_mtime_cache`, `_hook_state_cache`, `_hook_state_last_read`.
**Called by:** `menubar.py:CCMenuBarApp._tick` (`list_alive_sessions`, `_scan_bg_sleep_timers`), `menubar.py:_PanelController.abortBgTimer_` (`_scan_bg_sleep_timers`, `_abort_bg_sleep_timers`), `menubar.py:_focus_session` (`get_ghostty_terminal_id`).
**Calls out:** `session_finder.get_project_directories`; `subprocess` (ps, lsof, tmux, osascript).

---

### hook_writer.py (73 LOC)

**Purpose:** CC hook handler — reads the JSON payload CC writes to stdin on UserPromptSubmit/Stop/StopFailure, then atomically updates `~/.monitor_cc_menubar_hooks.json` with `{session_id: {status, cwd, updated_ts}}`. Called by CC's hook system (installed via `hook_setup.py`). Prunes entries older than 7200s on each write to prevent unbounded file growth.
**Reads:** stdin (CC hook JSON payload); `~/.monitor_cc_menubar_hooks.json` (current state, inside exclusive lock).
**Writes:** `~/.monitor_cc_menubar_hooks.json` (atomic via temp + `os.replace()`); `~/.monitor_cc_menubar_hooks.lock` (flock coordination).
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json`; runs `async: true` so it never blocks CC). Never imported by other modules.
**Calls out:** stdlib only (`fcntl`, `json`, `os`, `time`).

**Usage:** `python3 src/menubar/hook_writer.py` (stdin = CC hook JSON). Install via `hook_setup.py`.

---

### hook_setup.py (71 LOC)

**Purpose:** One-shot idempotent installer — adds the activity-monitor hooks (UserPromptSubmit → working, Stop/StopFailure → idle) to `~/.claude/settings.json`. Safe to re-run; detects existing entries by command path and skips duplicates.
**Reads:** `~/.claude/settings.json`.
**Writes:** `~/.claude/settings.json` (atomic via temp + `os.replace()`).
**Called by:** User manually (`python3 src/menubar/hook_setup.py` from Monitor_CC root). Never imported.
**Calls out:** stdlib only (`json`, `os`, `pathlib`).

**Usage:** `python3 src/menubar/hook_setup.py` — run once after clone or when hooks need reinstalling. Restart CC to activate.

---

## State

| Variable | Module | Type | Owner | Description |
|---|---|---|---|---|
| `CCMenuBarApp._last_statuses` | menubar.py | `dict` | app instance | `{name: status}` snapshot for blink-on-change detection; updated every tick (also while panel open) to prevent false blink on re-open. |
| `CCMenuBarApp._idle_since_ts` | menubar.py | `dict` | app instance | `{name: float}` timestamps when each main session first went idle (debounce for auto-focus). Cleared on working or has_bg=True. |
| `CCMenuBarApp._panel_open` | menubar.py | `bool` | app instance | True while NSPanel is visible. Gates `_tick` between `_rebuild_panel` (closed) and `_update_panel_inplace` (open). Set/cleared by `_PanelController.togglePanel_`. |
| `CCMenuBarApp._initialized` | menubar.py | `bool` | app instance | Lazy-init sentinel: `setMenu_(None)` + button target/action wiring happens in first `_tick` after AppKit runloop starts. Prevents AttributeError on `_nsapp` access in `__init__`. |
| `CCMenuBarApp._displayed_items` | menubar.py | `dict` | app instance | `{name: NSButton}` populated by `_rebuild_panel`; used by `_update_panel_inplace` for O(1) button lookup. Reset on each rebuild. |
| `CCMenuBarApp._cwd_map` | menubar.py | `dict` | app instance | `{tag: cwd}` for click-to-focus routing. NSButton carries an integer tag (set in `_rebuild_panel`); `_PanelController.focusSession_` reads `sender.tag()` to resolve cwd. Reset on each rebuild. |
| `CCMenuBarApp._abort_btn` | menubar.py | `NSButton\|None` | app instance | Abort-timer button reference. `None` when no CC sleep timers running; set to NSButton in `_rebuild_panel` when `bg_result is not None`. Checked by `_tick` to detect None↔Some transition → triggers rebuild. Reset to `None` at top of each `_rebuild_panel`. |
| `CCMenuBarApp._toggle_btn` | menubar.py | `NSButton` | app instance | Auto-Jump toggle button in the fixed top_bar NSView. Created by `_make_nspanel()`. Target/action wired in lazy-init tick (`toggleAutoJump:`). Title updated by `_rebuild_panel` and `toggleAutoJump_` (ON/OFF toggle). Never recreated — contrast with the old pattern where toggle was an arranged subview of NSStackView rebuilt each tick. |
| `CCMenuBarApp._panel` | menubar.py | `NSPanel` | app instance | The sticky dropdown panel. Created in `__init__` via `_make_nspanel()`. Stored here because ObjC objects reject Python attrs — (panel, stack, quit_btn) tuple unpacked onto app instance. |
| `CCMenuBarApp._panel_sv` | menubar.py | `NSStackView` | app instance | Vertical NSStackView, direct subview of `panel.contentView()` above the footer. Autoresizing mask 18 (width+height sizable) — fills content area automatically on resize. Arranged subviews rebuilt on each `_rebuild_panel`. |
| `CCMenuBarApp._panel_quit_btn` | menubar.py | `NSButton` | app instance | Restart button in fixed footer. Target/action wired in lazy-init tick (not `__init__`) to `_PanelController.restartApp_`. |
| `CCMenuBarApp._panel_controller` | menubar.py | `_PanelController` | app instance | Single PyObjC NSObject instance as ObjC target for all button actions (toggle, focus, autoJump, quit). Held as instance attr to prevent ARC garbage collection. |
| `CCMenuBarApp._auto_focus` | menubar.py | `bool` | app instance | Whether auto-focus is enabled. Loaded from settings JSON on launch; toggled and saved via `_PanelController.toggleAutoJump_`. Default OFF. |
| `CCMenuBarApp._panel_width` | menubar.py | `int` | app instance | Current panel width in pts. Loaded from settings on launch (fallback: `PANEL_WIDTH=380`). Updated by `_PanelController.windowDidResize_` on user drag; persisted to settings. Used by `_resize_panel` + `_rebuild_panel`. |
| `CCMenuBarApp._panel_min_height` | menubar.py | `int` | app instance | Grow-only floor for panel height in pts. Set by user drag via `windowDidResize_`; persisted to settings. `_rebuild_panel` sizes panel to `max(_panel_min_height, required_h)` — never below the user-set floor, grows when sessions need more space. Loaded from `panel_min_height` key (fallback: legacy `panel_max_height`, then `PANEL_HEIGHT=460`). |
| `_cc_proc_cache` | discover.py | `Dict[pid, (tty, cwd)]` | module | CC processes. Incremental: `ps -A` every 10s drops gone PIDs; `lsof -d cwd` only for newly seen PIDs (cwd is stable after launch). Steady-state: ~75ms (ps only). |
| `_cc_proc_last_refresh` | discover.py | `float` | module | Timestamp of last CC cache pass. |
| `_ghostty_tty_to_id` | discover.py | `Dict[str, str]` | module | tty → Ghostty terminal UUID. Populated incrementally by OSC 2 probe. |
| `_ghostty_tty_last_refresh` | discover.py | `float` | module | Timestamp of last probe cycle (updated only when a probe actually ran). |
| `_tmux_state_cache` | discover.py | `Dict[str, (bool, int)]` | module | session_name → (alive, session_activity unix ts). One `tmux list-sessions` call per 3s replaces per-worker `has-session` + `display-message` pairs. |
| `_tmux_state_last_refresh` | discover.py | `float` | module | Timestamp of last tmux state refresh. |
| `_proxy_log_mtime_cache` | discover.py | `Dict[str, Tuple[float, Optional[float]]]` | module | `opus_<project_key>→(checked_at, newest_mtime)`. TTL=`_PROC_REFRESH_INTERVAL` (10s). Used by `_proxy_log_newest_mtime` to avoid per-tick glob. Populated on first main-session idle check per key. |
| `_hook_state_cache` | discover.py | `Dict[str, dict]` | module | `session_id→{status, cwd, updated_ts}`. Read from `~/.monitor_cc_menubar_hooks.json`. TTL=`_PROC_REFRESH_INTERVAL` (10s). Populated by `_read_hook_state()` once per tick in `list_alive_sessions`. |
| `_hook_state_last_read` | discover.py | `float` | module | Timestamp of last hook state file read. |

## Activity Detection (per session type)

**Workers** (tmux sessions):
- Alive iff `tmux has-session -t =worker-{project_basename}-{worker_name}` returns 0. Exact-match `=` prefix prevents prefix-matching false positives.
- Session name reconstructed from worker JSONL cwd: split on `/.claude/worktrees/`, `basename(left)` = project basename.
- Status: `tmux display-message -p '#{window_activity}'` → unix timestamp; `working` if age ≤ 10s.
- Fallback (cwd unreadable): `ALIVE_WINDOW_SECS=3600` JSONL age check + 10s mtime threshold.

**Mains** (Ghostty terminals):
- Alive if JSONL mtime within `ALIVE_WINDOW_SECS=3600` (1h).
- **Priority 1 — Hook state** (`~/.monitor_cc_menubar_hooks.json`): `session_id` maps directly to JSONL stem. If entry exists and `updated_ts` within `ALIVE_WINDOW_SECS`: use `status` as-is. `UserPromptSubmit` sets working from T=0 (captures thinking phase); `Stop`/`StopFailure` set idle immediately. No heuristic lag.
- **Priority 2 — JSONL mtime** (fallback when hooks absent/stale): mtime ≤ `WORKING_THRESHOLD_SECS=10s` = working. TTY mtime removed (cursor blinks cause stuck-at-working).
- **Priority 3 — Proxy override** (fallback): `proxy_mtime > jsonl_mtime AND (now - proxy_mtime) ≤ THINKING_OVERRIDE_MAX_SECS=300s` → working. See Gotchas.
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

**Workers not affected**: CC processes inside tmux panes have a tmux-allocated PTY (different from the Ghostty tab's TTY). Workers never appear in `_ghostty_tty_to_id`. Workers have no click action in the panel (display-only NSButton rows with no target/action).

## Gotchas

- **Singleton enforcement via fcntl lock**: `run()` calls `_acquire_singleton_lock()` before constructing `CCMenuBarApp`. Opens `~/.monitor_cc_menubar.pid`, attempts `fcntl.flock(LOCK_EX | LOCK_NB)`. On success: sets `FD_CLOEXEC` on the fd (required for clean `os.execv` restart — see below), writes PID to the file, returns the open file handle (held in `run()`'s stack frame for the process lifetime — must not be closed/GC'd, fcntl locks are fd-bound). On failure (another instance holds the lock): returns `None` → `run()` prints to stderr and calls `sys.exit(0)`. **Exit code 0 is mandatory**: launchd `KeepAlive=true` respawns on non-zero exit. A duplicate instance exiting 0 is treated as a clean completion, not a crash — no respawn loop.
- **Restart via os.execv (not launchctl)**: `_PanelController.restartApp_` calls `os.execv(sys.executable, [sys.executable] + sys.argv)` — replaces the current process image in-place with a fresh run of the same command. Chosen over `launchctl kickstart -k` because: (1) same PID, no race condition between old process dying and new one starting; (2) no double bar-icon; (3) no launchd round-trip. The `FD_CLOEXEC` flag on the singleton lock fd is the key enabler: the old fd is closed atomically at exec time, so the new process image can re-acquire the lock in `_acquire_singleton_lock()` without contention.
- `quit_button=None` passed to `rumps.App.__init__` — the default rumps quit button is menu-attached and would be orphaned after `setMenu_(None)`. Restart is instead a footer NSButton in the NSPanel wired to `_PanelController.restartApp_`.
- Background task detection: `/tmp/claude-<uid>/` uses the numeric Unix UID (`os.getuid()`). `*.output` files with `st_size == 0` = in-progress; `done\n` (5 bytes) = completed.
- **Abort leaves task file at 0 bytes:** when the sleep child is killed via SIGTERM, the zsh parent exits via `&&` short-circuit (no `echo done` stdout), so CC writes nothing to the task file — it stays 0 bytes indefinitely. `_abort_bg_sleep_timers` explicitly writes `aborted\n` to all 0-byte task files after kill so `_has_active_bg` returns False and the `[B]` badge disappears. CC fires no completion notification for externally killed timers; Opus must be informed manually.
- **CC uses `zsh -c`, not `bash -c`:** background bash commands are actually `zsh -c "source ... && eval 'cmd' ..."`. `_scan_bg_sleep_timers` correctly matches these because `echo done` appears in the zsh parent's args; the sleep child args are always exactly `sleep N`.
- `LSUIElement=1` must be set before `app.run()` to suppress the Dock icon. Set in `run()` via `os.environ.setdefault`.
- Launched via launchd: `KeepAlive=true` auto-restarts on crash. Logs → `/tmp/monitor_cc_menubar.{log,err}`.
- **launchd PATH inheritance**: launchd spawns processes with a minimal default PATH (`/usr/bin:/bin:/usr/sbin:/sbin`) — Homebrew (`/opt/homebrew/bin`) is absent. `tmux` installed via Homebrew is not found → `discover.py` worker-alive checks fail → all workers silently dropped from the panel. Fix: explicit `EnvironmentVariables/PATH` in `com.brunowinter.monitor_cc_menubar.plist` prepends `/opt/homebrew/bin:/opt/homebrew/sbin` (arm64) and `/usr/local/bin` (Intel fallback).
- **Ghostty PID lookup**: `pgrep` is unreliable on macOS for full-path binary names (`pgrep -x ghostty` and `pgrep -f Ghostty.app/Contents/MacOS` both return empty intermittently). Use `ps -A -o pid=,command=` parsed directly: `'Ghostty.app/Contents/MacOS' in line` finds the process robustly.
- **Ghostty AppleScript**: Ghostty.sdef exposes `id` (UUID, stable), `name` (current title), `working directory` per `terminal`. `focus` command takes a specifier: `focus terminal id "<UUID>"`. Does NOT expose `tty` or `pid`.
- **OSC 2 cleanup**: After the probe, `\033]2;\007` (empty-string OSC 2) written to the probed TTYs restores the shell's default title (CWD from PROMPT_COMMAND / precmd hook). Without cleanup, idle shells show `__GHT_XXXXXXXX` until next prompt display.
- **TTY ownership**: Ghostty children run as `/usr/bin/login` (root) but the `/dev/ttys<NNN>` device files are owned by the logged-in user → write access OK.
- **tmux exact-match**: `tmux has-session -t name` uses prefix matching; `=name` enforces exact match. `display-message -t name` works correctly once the session is confirmed to exist (no `=` needed there — exact match preferred before prefix by tmux's resolution order).
- **Badge column alignment**: Status badges `[*]`/`[ ]` are fixed-width (3 chars). Background task badge `[B M:SS]` is variable-width (3–9 chars); `_NO_BG` spacer is 3 chars. Nothing follows the badge, so variable width causes no column misalignment.
- **Global hotkey Cmd+L**: registered in `CCMenuBarApp.__init__` via Carbon `RegisterEventHotKey` (ctypes, no pyobjc-framework-Carbon, no extra permissions). keycode 37 (`kVK_ANSI_L`), modifier `0x0100` (cmdKey). Callback calls `nsstatusitem.button().performClick_(None)`. With `setMenu_(None)` applied (lazy-init tick), `performClick_` fires the button's target/action → `_PanelController.togglePanel_`. `app._hotkey_cb` and `app._hotkey_ref` held on instance to prevent GC of the ctypes callback.
- **Sleep-countdown detection** (`_scan_bg_sleep_timers`): scans `ps -A -o pid=,ppid=,etime=,args=` every tick (1.5s). Matches child processes with args exactly `sleep N` whose parent args contain `echo done` (the Opus background-timer signature `bash -c "sleep N && echo done"`). Uses `_parse_etime` to decode ps etime format → remaining = max(0, N − elapsed). Returns min across all matches. False-positive risk: another `sh -c "sleep N && echo done"` process — low probability, acceptable.
- **Lazy-init timing**: `rumps.App._nsapp` is only populated after `app.run()` starts the AppKit runloop (`initializeStatusBar` at `jaredks/rumps rumps/rumps.py:1350`). `setMenu_(None)` + button target/action wiring + Quit button wiring therefore happen in the first `_tick` call (guarded by `if not self._initialized`), not `__init__`. `_initialized = False` is the sentinel.
- **Dynamic panel height (grow-only)**: `_rebuild_panel` calls `_compute_required_height(sorted_sessions, bg_result)` → exact pts needed for all sessions with no truncation (`_FOOTER_H + _TOP_BAR_H + _LABEL_H` fixed + per-project `_LABEL_H + N*_ROW_H`), then `_resize_panel(app, max(app._panel_min_height, required_h))`. Panel never shrinks below the user-set floor (`_panel_min_height`); when new sessions appear it grows by `_LABEL_H + _ROW_H` per addition. No sessions are hidden. `NSBoxSeparator` containers in NSStackView require an explicit `heightAnchor().constraintEqualToConstant_(18.0)` — plain `NSView` has no `intrinsicContentSize`, causing NSStackView's Auto Layout to collapse them to 0-height without this constraint.
- **Resize cursors on panel edges**: NSPanel with `NSWindowStyleMaskNonactivatingPanel` never becomes the key window, so macOS does not automatically show OS-default resize cursors on the resizable edges. Three-part fix: (1) `panel.setAcceptsMouseMovedEvents_(True)` — without it, `NSWindowStyleMaskNonactivatingPanel` suppresses `mouseMoved:` dispatch at the window level even when `NSTrackingActiveAlways` is set; (2) `panel.disableCursorRects()` — NSTextField subviews install I-Beam cursor rects via `resetCursorRects` which are processed AFTER `mouseMoved:` event delivery and override `NSCursor.set()` calls; disabling cursor-rect management for the window eliminates this override (safe because all NSTextFields in the panel are `labelWithString_` display-only, so I-Beam was semantically incorrect anyway); (3) `_PanelContentView(NSView)` is installed as `panel.contentView()` via `setContentView_()`. Its `updateTrackingAreas()` installs an `NSTrackingArea` (options 642 = `NSTrackingMouseMoved|NSTrackingActiveAlways|NSTrackingInVisibleRect`, `owner=self`) and removes any prior tracking areas first. Its `mouseMoved_()` checks `event.locationInWindow()` against an 8pt edge threshold and sets `NSCursor.resizeUpDownCursor()` (bottom), `NSCursor.resizeLeftRightCursor()` (left/right), or `NSCursor.arrowCursor()` (interior). **Critical — owner must be the NSView itself, not an external NSObject:** AppKit only dispatches `mouseMoved:` from an `NSTrackingArea` to owners that are `NSView` subclasses present in the view hierarchy. Using an external `NSObject` (e.g. `_PanelController`) as owner causes the tracking area to install silently but `mouseMoved_` never fires — verified by probe (unconditional crosshair cursor never changed). `NSTrackingInVisibleRect` auto-adjusts the tracked rect on panel resize. `NSTrackingActiveAlways` is required — `NSTrackingActiveInKeyWindow` would never fire on this nonactivating panel.
- **Drag-resize**: `NSWindowStyleMaskResizable` added to styleMask enables left/bottom/right edge drag handles. `_PanelController.windowDidResize_` (NSWindowDelegate) fires after each resize step on the main thread — writes new `_panel_width` + `_panel_min_height` (each clamped to their respective `PANEL_MIN_*` floors) to app instance and persists to settings. Autoresizing masks: footer `NSViewWidthSizable=2`, restart button `NSViewMinXMargin=1`, top_bar `NSViewWidthSizable|NSViewMinYMargin=10` (stays at top edge), stack view `NSViewWidthSizable|NSViewHeightSizable=18` (fills middle). Row-button frames are corrected to exact width on next `_rebuild_panel`. Delegate set in lazy-init tick (same pattern as button wiring). Min size enforced by `setContentMinSize_(NSMakeSize(PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT))` + manual clamp in `windowDidResize_`. Content beyond the panel's lower edge is hard-clipped by the window — no scrolling possible. `windowDidEndLiveResize_` fires once when the user releases the mouse; if the panel is open it immediately calls `_rebuild_panel` → panel resizes to `max(_panel_min_height, required_h)`. If user dragged the panel smaller than content requires, `required_h` wins and the panel bounces back; `_panel_min_height` records the drag as the new floor for future empty-panel states.
- **Hook state as primary signal** (`_hook_state_cache`): `session_id` in hook payload == JSONL filename stem (e.g. `37a411d8-...`). Direct lookup, no encoding/decoding. Hook state stale guard uses `ALIVE_WINDOW_SECS=3600s` — if CC is killed without firing `Stop`, state decays within 1h and falls back to JSONL. Worker CC sessions also write to the hook state file (they fire hooks too); their entries are simply not consulted (`is_worker=True` path never calls `_read_hook_state`). `async: true` on hook commands means hook_writer.py runs in background and never blocks CC. Install via `hook_setup.py`; if not installed, `~/.monitor_cc_menubar_hooks.json` doesn't exist → `_read_hook_state` returns `{}` silently → JSONL+proxy path used.
- **Proxy-log thinking signal** (`_proxy_log_newest_mtime`): when JSONL-derived status is `idle`, checks the newest `api_requests_opus_<project_key>_*.jsonl` in `_PROXY_LOG_DIR`. Override condition: `proxy_mtime > jsonl_mtime AND (now - proxy_mtime) ≤ THINKING_OVERRIDE_MAX_SECS=300s` → status `working`. The `proxy_mtime > jsonl_mtime` check is the critical signal: the proxy writes a request entry when the request is intercepted (before the response), so `proxy_mtime` advances ahead of `jsonl_mtime` at the START of the reasoning phase and stays ahead for the full thinking duration. After response completion the proxy writes a latency entry ~0.1s BEFORE CC writes JSONL, so `proxy_mtime` drops just below `jsonl_mtime` — no false positive on completed turns. The old condition `(now - proxy_mtime) ≤ 10s` only caught the first 10s of thinking; thinking takes 30–120s, making the override effectively dead. Workers unaffected (tmux `window_activity` already captures their activity). `_PROXY_LOG_DIR` is hardcoded to `Monitor_CC/src/logs/`. Missing dir → `None` → silent fallback to JSONL-only.
- **Settings backwards-compat**: `_load_settings` reads `panel_min_height` first, falls back to legacy `panel_max_height` key, then to `PANEL_HEIGHT=460`. Old files with only `panel_max_height` migrate transparently — the value is used as the initial floor and rewritten under the new key on next save. Files missing both height keys start at `PANEL_HEIGHT`. Old `auto_focus`-only files fall back to `PANEL_WIDTH`/`PANEL_HEIGHT` for missing numeric keys.
- **Status-change is panel-no-op**: working↔idle transitions NEVER trigger `_rebuild_panel` or `_resize_panel`. Open panel: status changes go through `_update_panel_inplace` (badge update only). Closed panel: status changes only trigger `_blink`; no rebuild. Only two events trigger `_rebuild_panel`: (1) session-set change (`session_names != set(self._displayed_items)`) — new worker spawned or session disappeared; (2) abort-button None↔Some transition (panel open only).
- **In-place update coverage**: `_update_panel_inplace` only updates sessions already in `_displayed_items` (populated by the last `_rebuild_panel`). Session-set changes (new worker spawned, session disappeared) while the panel is open trigger `_rebuild_panel` immediately: `_tick` checks `session_names != set(self._displayed_items)` alongside the `_abort_btn` None↔Some transition. This prevents workers spawned while the panel is open from being invisible until close+reopen.
- **NSPanel ObjC attribute constraint**: NSPanel (and all PyObjC-bridged ObjC objects) reject arbitrary Python attribute assignment — `panel.my_attr = x` raises `AttributeError`. `_make_nspanel()` returns `(panel, stack, quit_btn)` as a Python tuple; refs are unpacked onto the Python `CCMenuBarApp` instance.
- **Button tag → cwd routing**: `_rebuild_panel` assigns each clickable session NSButton an integer tag via `btn.setTag_(tag)` and stores `_cwd_map[tag] = s.cwd`. `_PanelController.focusSession_` reads `sender.tag()` to look up cwd. `_cwd_map` and tags reset at the top of each `_rebuild_panel`.
- **Settings file** (`~/.monitor_cc_menubar_settings.json`): single JSON `{"auto_focus": bool}`. Written atomically via tempfile + `os.replace`. Read on launch; any parse error → default OFF. The `.tmp` suffix is used for the temp file; a crashed write leaves `~/.monitor_cc_menubar_settings.json.tmp` as debris (harmless — overwritten on next save).
- **NSStackView gravity — requires BOTH `addView_inGravity_(view, 1)` AND `setDistribution_(-1)`**: `addArrangedSubview_` defaults to `NSStackViewGravityBottom` (3) in AppKit, packing rows upward from the bottom of the frame. `addView_inGravity_(view, 1)` (NSStackViewGravityTop = 1) anchors rows at the top. **But gravity is only consulted when `setDistribution_(-1)` (NSStackViewDistributionGravityAreas) is set.** `setDistribution_(0)` (NSStackViewDistributionFill) makes views fill the stack equally and ignores gravity entirely — `addView_inGravity_` calls become no-ops. Enum values: `GravityTop=1`, `GravityCenter=2`, `GravityBottom=3`; `DistGravityAreas=-1`, `DistFill=0`. Cleanup uses `removeView_(sv)` (single call, gravity-API counterpart) instead of `removeArrangedSubview_(sv)` + `removeFromSuperview()`.
