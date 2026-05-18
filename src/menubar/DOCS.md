# src/menubar/

## Role

Standalone macOS status-bar (menubar) application that shows all currently-running Claude Code sessions on this Mac with their working/idle status and background-task badge. Independent of the tmux TUI — launched via `workflow.py --mode menubar` or launchd. macOS only (rumps/AppKit).

## Public Interface

`from src.menubar.menubar import run` — `run()` is the sole entry point. Called by `workflow.py --mode menubar`.

## Flow

1. `run()` → sets `LSUIElement=1` env → instantiates `CCMenuBarApp` → `app.run()` starts AppKit runloop.
2. `CCMenuBarApp._tick()` fires every 1.5s (NSDefaultRunLoopMode, uninterrupted — NSPanel does not trigger NSEventTrackingRunLoopMode) → `list_alive_sessions()` → auto-focus debounce → if panel closed: blink on change + `_rebuild_panel`; if panel open: `_update_panel_inplace` (updates NSButton attributed titles, preserves scroll). Background task badge: `[B M:SS]` when Opus sleep timers running, `[B]` otherwise.
3. `list_alive_sessions()` → refreshes CC-process cache (ps/lsof, every 10s) → refreshes Ghostty TTY-to-UUID mapping (OSC 2 probe, incremental) → scans `~/.claude/projects/*/` → picks newest JSONL per project → for workers checks tmux session existence; for mains applies 1h alive window → determines working/idle status per session type → checks `/tmp/claude-<uid>/` for in-progress tasks.
4. Click on a main session → `_focus_session(cwd)` → looks up Ghostty terminal UUID from mapping cache → `focus terminal id "<UUID>"` (Path A) or cwd-match fallback (Path B).

## Modules

### menubar.py (467 LOC)

**Purpose:** `CCMenuBarApp` rumps subclass + `_PanelController` (NSObject target for panel toggle/focus/restart + `windowDidResize_` delegate) + NSPanel sticky-toggle dropdown with dynamic height + drag-resize (left/bottom/right edges) + timer + blink + `_rebuild_panel` + `_update_panel_inplace` + `_truncate_and_height` + `_resize_panel` + `_focus_session` + `_register_hotkey` + settings load/save + Auto-Jump toggle + `run()` entry point.
**Reads:** `list_alive_sessions()` result on every tick; `get_ghostty_terminal_id(cwd)` on click; `_scan_bg_sleep_timers()` on every tick for `[B M:SS]` badge; `~/.monitor_cc_menubar_settings.json` on launch.
**Writes:** `app.title` (icon only), NSButton attributed titles in NSStackView (full rebuild or in-place `setAttributedTitle_`); `~/.monitor_cc_menubar_settings.json` on toggle.
**Called by:** `workflow.py` (`--mode menubar` route).
**Calls out:** `rumps`, `AppKit` (NSAttributedString/NSButton/NSFont/NSColor/NSPanel/NSScrollView/NSStackView/NSTextField/NSView), `Foundation` (NSObject/NSMakeRect for `_PanelController` + panel layout), `subprocess` (osascript for click-to-focus, launchctl for restart), `threading.Timer`, `ctypes` (Carbon hotkey).

---

### discover.py (427 LOC)

**Purpose:** Session discovery — scans JSONL files, determines working/idle/background status per session type (main vs worker). Provides Ghostty terminal UUID mapping for reliable click-to-focus. Provides `_scan_bg_sleep_timers()` for bar countdown. For main sessions: overlays proxy-log mtime as thinking-state signal (JSONL lags during reasoning-only phases).
**Reads:** `~/.claude/projects/*/` JSONL mtimes + last lines; `/tmp/claude-<uid>/` task dirs; `ps`/`lsof` output (CC process cache); tmux session state; `/dev/ttys<NNN>` device files (OSC 2 marker writes for Ghostty mapping); `_PROXY_LOG_DIR/api_requests_*.jsonl` mtimes (proxy thinking signal).
**Writes:** `/dev/ttys<NNN>` (transient OSC 2 probe marker + empty-string cleanup). Module-level cache: `_cc_proc_cache`, `_cc_proc_last_refresh`, `_ghostty_tty_to_id`, `_ghostty_tty_last_refresh`, `_tmux_state_cache`, `_tmux_state_last_refresh`, `_proxy_log_mtime_cache`.
**Called by:** `menubar.py:CCMenuBarApp._tick` (`list_alive_sessions`, `_scan_bg_sleep_timers`), `menubar.py:_focus_session` (`get_ghostty_terminal_id`).
**Calls out:** `session_finder.get_project_directories`; `subprocess` (ps, lsof, tmux, osascript).

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
| `CCMenuBarApp._panel` | menubar.py | `NSPanel` | app instance | The sticky dropdown panel. Created in `__init__` via `_make_nspanel()`. Stored here because ObjC objects reject Python attrs — (panel, stack, quit_btn) tuple unpacked onto app instance. |
| `CCMenuBarApp._panel_sv` | menubar.py | `NSStackView` | app instance | Vertical NSStackView (document view of scroll area). Arranged subviews rebuilt on each `_rebuild_panel`. |
| `CCMenuBarApp._panel_quit_btn` | menubar.py | `NSButton` | app instance | Restart button in fixed footer. Target/action wired in lazy-init tick (not `__init__`) to `_PanelController.restartApp_`. |
| `CCMenuBarApp._panel_scroll` | menubar.py | `NSScrollView` | app instance | Scroll area covering content above footer. Frame resized on every `_rebuild_panel` to match dynamic panel height (`new_h - _FOOTER_H`). |
| `CCMenuBarApp._panel_controller` | menubar.py | `_PanelController` | app instance | Single PyObjC NSObject instance as ObjC target for all button actions (toggle, focus, autoJump, quit). Held as instance attr to prevent ARC garbage collection. |
| `CCMenuBarApp._auto_focus` | menubar.py | `bool` | app instance | Whether auto-focus is enabled. Loaded from settings JSON on launch; toggled and saved via `_PanelController.toggleAutoJump_`. Default OFF. |
| `CCMenuBarApp._panel_width` | menubar.py | `int` | app instance | Current panel width in pts. Loaded from settings on launch (fallback: `PANEL_WIDTH=380`). Updated by `_PanelController.windowDidResize_` on user drag; persisted to settings. Used by `_resize_panel` + `_rebuild_panel`. |
| `CCMenuBarApp._panel_max_height` | menubar.py | `int` | app instance | Current panel max-height cap in pts. Loaded from settings on launch (fallback: `PANEL_MAX_HEIGHT=600`). Updated by `windowDidResize_` on user drag; persisted to settings. Used by `_truncate_and_height`. |
| `_cc_proc_cache` | discover.py | `Dict[pid, (tty, cwd)]` | module | CC processes. Incremental: `ps -A` every 10s drops gone PIDs; `lsof -d cwd` only for newly seen PIDs (cwd is stable after launch). Steady-state: ~75ms (ps only). |
| `_cc_proc_last_refresh` | discover.py | `float` | module | Timestamp of last CC cache pass. |
| `_ghostty_tty_to_id` | discover.py | `Dict[str, str]` | module | tty → Ghostty terminal UUID. Populated incrementally by OSC 2 probe. |
| `_ghostty_tty_last_refresh` | discover.py | `float` | module | Timestamp of last probe cycle (updated only when a probe actually ran). |
| `_tmux_state_cache` | discover.py | `Dict[str, (bool, int)]` | module | session_name → (alive, session_activity unix ts). One `tmux list-sessions` call per 3s replaces per-worker `has-session` + `display-message` pairs. |
| `_tmux_state_last_refresh` | discover.py | `float` | module | Timestamp of last tmux state refresh. |
| `_proxy_log_mtime_cache` | discover.py | `Dict[str, Tuple[float, Optional[float]]]` | module | `opus_<project_key>→(checked_at, newest_mtime)`. TTL=`_PROC_REFRESH_INTERVAL` (10s). Used by `_proxy_log_newest_mtime` to avoid per-tick glob. Populated on first main-session idle check per key. |

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

**Workers not affected**: CC processes inside tmux panes have a tmux-allocated PTY (different from the Ghostty tab's TTY). Workers never appear in `_ghostty_tty_to_id`. Workers have no click action in the panel (display-only NSButton rows with no target/action).

## Gotchas

- `quit_button=None` passed to `rumps.App.__init__` — the default rumps quit button is menu-attached and would be orphaned after `setMenu_(None)`. Restart is instead a footer NSButton in the NSPanel wired to `_PanelController.restartApp_`.
- Background task detection: `/tmp/claude-<uid>/` uses the numeric Unix UID (`os.getuid()`). `*.output` files with `st_size == 0` = in-progress; `done\n` (5 bytes) = completed.
- `LSUIElement=1` must be set before `app.run()` to suppress the Dock icon. Set in `run()` via `os.environ.setdefault`.
- Launched via launchd: `KeepAlive=true` auto-restarts on crash. Logs → `/tmp/monitor_cc_menubar.{log,err}`.
- **Ghostty PID lookup**: `pgrep` is unreliable on macOS for full-path binary names (`pgrep -x ghostty` and `pgrep -f Ghostty.app/Contents/MacOS` both return empty intermittently). Use `ps -A -o pid=,command=` parsed directly: `'Ghostty.app/Contents/MacOS' in line` finds the process robustly.
- **Ghostty AppleScript**: Ghostty.sdef exposes `id` (UUID, stable), `name` (current title), `working directory` per `terminal`. `focus` command takes a specifier: `focus terminal id "<UUID>"`. Does NOT expose `tty` or `pid`.
- **OSC 2 cleanup**: After the probe, `\033]2;\007` (empty-string OSC 2) written to the probed TTYs restores the shell's default title (CWD from PROMPT_COMMAND / precmd hook). Without cleanup, idle shells show `__GHT_XXXXXXXX` until next prompt display.
- **TTY ownership**: Ghostty children run as `/usr/bin/login` (root) but the `/dev/ttys<NNN>` device files are owned by the logged-in user → write access OK.
- **tmux exact-match**: `tmux has-session -t name` uses prefix matching; `=name` enforces exact match. `display-message -t name` works correctly once the session is confirmed to exist (no `=` needed there — exact match preferred before prefix by tmux's resolution order).
- **Badge column alignment**: Status badges `[*]`/`[ ]` are fixed-width (3 chars). Background task badge `[B M:SS]` is variable-width (3–9 chars); `_NO_BG` spacer is 3 chars. Nothing follows the badge, so variable width causes no column misalignment.
- **Global hotkey Cmd+L**: registered in `CCMenuBarApp.__init__` via Carbon `RegisterEventHotKey` (ctypes, no pyobjc-framework-Carbon, no extra permissions). keycode 37 (`kVK_ANSI_L`), modifier `0x0100` (cmdKey). Callback calls `nsstatusitem.button().performClick_(None)`. With `setMenu_(None)` applied (lazy-init tick), `performClick_` fires the button's target/action → `_PanelController.togglePanel_`. `app._hotkey_cb` and `app._hotkey_ref` held on instance to prevent GC of the ctypes callback.
- **Sleep-countdown detection** (`_scan_bg_sleep_timers`): scans `ps -A -o pid=,ppid=,etime=,args=` every tick (1.5s). Matches child processes with args exactly `sleep N` whose parent args contain `echo done` (the Opus background-timer signature `bash -c "sleep N && echo done"`). Uses `_parse_etime` to decode ps etime format → remaining = max(0, N − elapsed). Returns min across all matches. False-positive risk: another `sh -c "sleep N && echo done"` process — low probability, acceptable.
- **Lazy-init timing**: `rumps.App._nsapp` is only populated after `app.run()` starts the AppKit runloop (`initializeStatusBar` at `jaredks/rumps rumps/rumps.py:1350`). `setMenu_(None)` + button target/action wiring + Quit button wiring therefore happen in the first `_tick` call (guarded by `if not self._initialized`), not `__init__`. `_initialized = False` is the sentinel.
- **Dynamic panel height**: `_resize_panel` runs inside every `_rebuild_panel` (closed-panel path only). If session count changes while the panel is open, the resize is deferred until the panel is closed and the next tick triggers a rebuild. `PANEL_MAX_HEIGHT` is a module-level constant — user adjusts per Edit.
- **Drag-resize**: `NSWindowStyleMaskResizable` added to styleMask enables left/bottom/right edge drag handles. `_PanelController.windowDidResize_` (NSWindowDelegate) fires after each resize step on the main thread — writes new `_panel_width` + `_panel_max_height` to app instance and persists to settings. Autoresizing masks on footer (`NSViewWidthSizable=2`), restart button (`NSViewMinXMargin=1`), and scroll view (`NSViewWidthSizable|NSViewHeightSizable=18`) keep layout coherent during live drag; row-button frames are corrected to exact width on next `_rebuild_panel`. Delegate set in lazy-init tick (same pattern as button wiring). Min size enforced by `setContentMinSize_((PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT))`.
- **Proxy-log thinking signal** (`_proxy_log_newest_mtime`): when JSONL-derived status is `idle` but the newest `api_requests_opus_<project_key>_*.jsonl` in `_PROXY_LOG_DIR` has mtime < `WORKING_THRESHOLD_SECS` (10s), status is overridden to `working`. Covers the gap where Opus is reasoning (no streaming output yet → JSONL not updated). Workers unaffected (tmux `window_activity` already captures their activity). `_PROXY_LOG_DIR` is hardcoded to `Monitor_CC/src/logs/` — proxy is central and intercepts all machine-wide CC sessions via `ANTHROPIC_BASE_URL`. Missing dir → `None` → silent fallback to JSONL-only.
- **Settings backwards-compat**: old `{"auto_focus": bool}` files missing `panel_width`/`panel_max_height` keys fall back to module constants `PANEL_WIDTH`/`PANEL_MAX_HEIGHT` via `d.get(key, default)`.
- **In-place update coverage**: `_update_panel_inplace` only updates sessions already in `_displayed_items` (populated by the last closed-state `_rebuild_panel`). Sessions that appear or disappear while the panel is open are deferred to the next full rebuild after close.
- **NSPanel ObjC attribute constraint**: NSPanel (and all PyObjC-bridged ObjC objects) reject arbitrary Python attribute assignment — `panel.my_attr = x` raises `AttributeError`. `_make_nspanel()` returns `(panel, stack, quit_btn)` as a Python tuple; refs are unpacked onto the Python `CCMenuBarApp` instance.
- **Button tag → cwd routing**: `_rebuild_panel` assigns each clickable session NSButton an integer tag via `btn.setTag_(tag)` and stores `_cwd_map[tag] = s.cwd`. `_PanelController.focusSession_` reads `sender.tag()` to look up cwd. `_cwd_map` and tags reset at the top of each `_rebuild_panel`.
- **Settings file** (`~/.monitor_cc_menubar_settings.json`): single JSON `{"auto_focus": bool}`. Written atomically via tempfile + `os.replace`. Read on launch; any parse error → default OFF. The `.tmp` suffix is used for the temp file; a crashed write leaves `~/.monitor_cc_menubar_settings.json.tmp` as debris (harmless — overwritten on next save).
- **NSStackView gravity — requires BOTH `addView_inGravity_(view, 1)` AND `setDistribution_(-1)`**: `addArrangedSubview_` defaults to `NSStackViewGravityBottom` (3) in AppKit, packing rows upward from the bottom of the frame. `addView_inGravity_(view, 1)` (NSStackViewGravityTop = 1) anchors rows at the top. **But gravity is only consulted when `setDistribution_(-1)` (NSStackViewDistributionGravityAreas) is set.** `setDistribution_(0)` (NSStackViewDistributionFill) makes views fill the stack equally and ignores gravity entirely — `addView_inGravity_` calls become no-ops. Enum values: `GravityTop=1`, `GravityCenter=2`, `GravityBottom=3`; `DistGravityAreas=-1`, `DistFill=0`. Cleanup uses `removeView_(sv)` (single call, gravity-API counterpart) instead of `removeArrangedSubview_(sv)` + `removeFromSuperview()`.
