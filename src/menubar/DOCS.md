# src/menubar/

## Role

Standalone macOS status-bar (menubar) application that shows all currently-running Claude Code sessions on this Mac with their working/idle status and background-task badge. Independent of the tmux TUI — launched via `workflow.py --mode menubar` or launchd. macOS only (rumps/AppKit).

## Public Interface

`from src.menubar import run` — `run()` is the sole entry point. Called by `workflow.py --mode menubar`.

## Flow

1. `run()` (system.py) → sets `LSUIElement=1` env → acquires singleton lock → instantiates `CCMenuBarApp` → `app.run()` starts AppKit runloop.
2. `CCMenuBarApp._tick()` (app.py) fires every 1.5s → `list_alive_sessions()` → auto-focus debounce → if panel closed: blink on status change; `_rebuild_panel` only on session-set change; if panel open: `_scan_bg_sleep_timers()` → on None↔Some transition or session-set change call `_rebuild_panel` (adds/removes abort button, grows panel), otherwise `_update_panel_inplace` (updates NSButton attributed titles only, no resize).
3. `list_alive_sessions()` (discover.py) → refreshes CC-process cache → refreshes Ghostty TTY-to-UUID mapping → scans `~/.claude/projects/*/` → determines working/idle status per session type → checks `/tmp/claude-<uid>/` for in-progress tasks.
4. Click on a main session → `_focus_session(cwd)` (system.py) → looks up Ghostty terminal UUID → `focus terminal id "<UUID>"` (Path A) or cwd-match fallback (Path B).

## Modules

### panel.py (259 LOC)

**Purpose:** NSPanel construction, NSView/NSTextField subclasses for cursor-rect pattern, all UI factory helpers, and the two render functions (`_rebuild_panel`, `_update_panel_inplace`). Pure UI concern — no rumps, no ctypes, no subprocess.
**Reads:** `app` instance attrs (`_panel_sv`, `_panel_width`, `_panel_min_height`, `_displayed_items`, `_cwd_map`, `_abort_btn`, `_toggle_btn`, `_panel_controller`, `_auto_focus`, `_panel`) via function parameters; session list from caller.
**Writes:** `app._displayed_items`, `app._cwd_map`, `app._abort_btn` (reset + populate on each rebuild); NSButton attributed titles (inplace update); NSPanel frame (via `_resize_panel`).
**Called by:** `app.py` (`CCMenuBarApp.__init__`, `_PanelController.togglePanel_`, `_PanelController.windowDidEndLiveResize_`, `CCMenuBarApp._tick`).
**Calls out:** `AppKit`, `Foundation`, `itertools`.

---

### app.py (235 LOC)

**Purpose:** `CCMenuBarApp` (rumps.App subclass) + `_PanelController` (NSObject target for panel toggle/focus/restart/abort/resize delegate) + `_tick` timer + blink + bar-icon + settings load/save.
**Reads:** `list_alive_sessions()` + `_scan_bg_sleep_timers()` on every tick; `~/.monitor_cc_menubar_settings.json` on launch; `app` instance state throughout.
**Writes:** bar icon via attributed NSStatusItem button; `~/.monitor_cc_menubar_settings.json` on toggle/resize; `/tmp/menubar-tick.log` per tick.
**Called by:** `system.py:run()` (lazy import).
**Calls out:** `rumps`, `AppKit` (NSAttributedString/NSBaselineOffsetAttributeName/NSFont/NSFontAttributeName), `Foundation` (NSObject/NSOperationQueue), `objc`, `threading`; `.panel`, `.hotkey`, `.system`, `.discover`.

---

### hotkey.py (54 LOC)

**Purpose:** Standalone Carbon Cmd+L global hotkey registration. Zero project dependencies — only `ctypes`.
**Reads:** nothing.
**Writes:** Carbon event handler + hotkey registration via CDLL.
**Called by:** `app.py:CCMenuBarApp.__init__` (`register_cmd_l`).
**Calls out:** `ctypes` (Carbon framework CDLL).

---

### system.py (75 LOC)

**Purpose:** `run()` entry point + singleton lock (`_acquire_singleton_lock`) + Ghostty click-to-focus (`_focus_session`). Owns the process-lifecycle concerns; no AppKit dependency.
**Reads:** `~/.monitor_cc_menubar.pid` (lock file); `get_ghostty_terminal_id(cwd)` from discover.py on click.
**Writes:** `~/.monitor_cc_menubar.pid` (PID); `/tmp/monitor_cc_menubar_focus.log` (focus results via osascript).
**Called by:** `workflow.py` (via `from src.menubar import run` → `__init__.py` → `system.run`); `app.py:_PanelController.focusSession_` + `CCMenuBarApp._tick` (`_focus_session`).
**Calls out:** `fcntl`, `os`, `subprocess` (osascript), `sys`; `.discover` (`get_ghostty_terminal_id`); lazy `.app` (`CCMenuBarApp`) inside `run()` only.

---

### discover.py (501 LOC)

**Purpose:** Session discovery — scans JSONL files, determines working/idle/background status per session type (main vs worker). Provides Ghostty terminal UUID mapping for reliable click-to-focus. Provides `_scan_bg_sleep_timers()` → `BgSleepInfo` (countdown + sleep PIDs) and `_abort_bg_sleep_timers()` for the abort button. For main sessions: primary status from hook state (`~/.monitor_cc_menubar_hooks.json`); fallback to JSONL mtime and proxy-log override when hooks not installed or stale.
**Reads:** `~/.claude/projects/*/` JSONL mtimes + last lines; `/tmp/claude-<uid>/` task dirs; `ps`/`lsof` output (CC process cache); tmux session state; `/dev/ttys<NNN>` device files (OSC 2 marker writes for Ghostty mapping); `_PROXY_LOG_DIR/api_requests_*.jsonl` mtimes (proxy thinking signal); `~/.monitor_cc_menubar_hooks.json` (hook state, TTL 10s).
**Writes:** `/dev/ttys<NNN>` (transient OSC 2 probe marker + empty-string cleanup). On abort: `signal.SIGTERM` to sleep PIDs + `'aborted\n'` to all 0-byte `*.output` task files under `_TASKS_BASE`. Module-level cache: `_cc_proc_cache`, `_cc_proc_last_refresh`, `_ghostty_tty_to_id`, `_ghostty_tty_last_refresh`, `_tmux_state_cache`, `_tmux_state_last_refresh`, `_proxy_log_mtime_cache`, `_hook_state_cache`, `_hook_state_last_read`.
**Called by:** `app.py:CCMenuBarApp._tick` (`list_alive_sessions`, `_scan_bg_sleep_timers`), `app.py:_PanelController.abortBgTimer_` (`_scan_bg_sleep_timers`, `_abort_bg_sleep_timers`), `app.py:_PanelController.windowDidEndLiveResize_` (`list_alive_sessions`), `system.py:_focus_session` (`get_ghostty_terminal_id`).
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
| `CCMenuBarApp._last_statuses` | app.py | `dict` | app instance | `{name: status}` snapshot for blink-on-change detection; updated every tick. |
| `CCMenuBarApp._idle_since_ts` | app.py | `dict` | app instance | `{name: float}` timestamps when each main session first went idle (debounce for auto-focus). Cleared on working or has_bg=True. |
| `CCMenuBarApp._panel_open` | app.py | `bool` | app instance | True while NSPanel is visible. Gates `_tick` between `_rebuild_panel` (closed) and `_update_panel_inplace` (open). Set/cleared by `_PanelController.togglePanel_`. |
| `CCMenuBarApp._initialized` | app.py | `bool` | app instance | Lazy-init sentinel: `setMenu_(None)` + button target/action wiring happens in first `_tick` after AppKit runloop starts. |
| `CCMenuBarApp._displayed_items` | panel.py | `dict` | panel.py (`_rebuild_panel`) | `{name: NSButton}` populated by `_rebuild_panel`; used by `_update_panel_inplace` for O(1) button lookup. Reset on each rebuild. |
| `CCMenuBarApp._cwd_map` | panel.py | `dict` | panel.py (`_rebuild_panel`) | `{tag: cwd}` for click-to-focus routing. NSButton carries integer tag; `focusSession_` reads `sender.tag()`. Reset on each rebuild. |
| `CCMenuBarApp._abort_btn` | panel.py | `NSButton\|None` | panel.py (`_rebuild_panel`) | Abort-timer button reference. `None` when no CC sleep timers running. Checked by `_tick` to detect None↔Some transition. |
| `CCMenuBarApp._toggle_btn` | panel.py | `NSButton` | panel.py (`_make_nspanel`) | Auto-Jump toggle button in fixed top_bar. Created by `_make_nspanel()`; target/action wired in lazy-init tick; title updated by `_rebuild_panel` and `toggleAutoJump_`. |
| `CCMenuBarApp._panel` | panel.py | `NSPanel` | panel.py (`_make_nspanel`) | The sticky dropdown panel. Created in `__init__`. Resized by `_resize_panel`. |
| `CCMenuBarApp._panel_sv` | panel.py | `NSStackView` | panel.py (`_make_nspanel`) | Vertical NSStackView filling content area. Arranged subviews rebuilt on each `_rebuild_panel`. |
| `CCMenuBarApp._panel_quit_btn` | app.py | `NSButton` | panel.py creates, app.py wires | Restart button in fixed footer. Target/action wired in lazy-init tick. |
| `CCMenuBarApp._panel_controller` | app.py | `_PanelController` | app.py | Single PyObjC NSObject as ObjC target for all button actions. Held to prevent ARC GC. |
| `CCMenuBarApp._auto_focus` | app.py | `bool` | app.py | Whether auto-focus is enabled. Loaded from settings; toggled by `toggleAutoJump_`. |
| `CCMenuBarApp._panel_width` | app.py | `int` | app.py owns, panel.py uses | Current panel width in pts. Loaded from settings (fallback: `PANEL_WIDTH=380`). Updated by `windowDidResize_`. |
| `CCMenuBarApp._panel_min_height` | app.py | `int` | app.py owns, panel.py uses | Grow-only floor for panel height. Updated by `windowDidResize_`. `_rebuild_panel` sizes to `max(_panel_min_height, required_h)`. |
| `CCMenuBarApp._hotkey_cb` | app.py | `ctypes CFUNCTYPE` | app.py | GC anchor for ctypes callback returned by `register_cmd_l`. |
| `CCMenuBarApp._hotkey_ref` | app.py | `ctypes.c_void_p` | app.py | GC anchor for Carbon hotkey handle returned by `register_cmd_l`. |
| `_cc_proc_cache` | discover.py | `Dict[pid, (tty, cwd)]` | module | CC processes. Incremental: `ps -A` every 10s. |
| `_cc_proc_last_refresh` | discover.py | `float` | module | Timestamp of last CC cache pass. |
| `_ghostty_tty_to_id` | discover.py | `Dict[str, str]` | module | tty → Ghostty terminal UUID. Populated incrementally by OSC 2 probe. |
| `_ghostty_tty_last_refresh` | discover.py | `float` | module | Timestamp of last probe cycle. |
| `_tmux_state_cache` | discover.py | `Dict[str, (bool, int)]` | module | session_name → (alive, session_activity unix ts). |
| `_tmux_state_last_refresh` | discover.py | `float` | module | Timestamp of last tmux state refresh. |
| `_proxy_log_mtime_cache` | discover.py | `Dict[str, Tuple[float, Optional[float]]]` | module | `opus_<project_key>→(checked_at, newest_mtime)`. TTL=10s. |
| `_hook_state_cache` | discover.py | `Dict[str, dict]` | module | `session_id→{status, cwd, updated_ts}`. TTL=10s. |
| `_hook_state_last_read` | discover.py | `float` | module | Timestamp of last hook state file read. |

## Import Graph

```
hotkey.py  → ctypes only
discover.py → subprocess, stdlib only
panel.py   → AppKit, Foundation, itertools
system.py  → fcntl, os, subprocess, sys; .discover
             lazy(.app) inside run() only
app.py     → rumps, objc, AppKit, Foundation, time, threading, json, os, sys
             .panel, .hotkey, .system, .discover
```

No cycles. `system.py` has no module-level import of `app.py`; the lazy import inside `run()` prevents the `app→system→app` circular dependency.

## Activity Detection (per session type)

**Workers** (tmux sessions):
- Alive iff `tmux has-session -t =worker-{project_basename}-{worker_name}` returns 0. Exact-match `=` prefix prevents prefix-matching false positives.
- Session name reconstructed from worker JSONL cwd: split on `/.claude/worktrees/`, `basename(left)` = project basename.
- Status: `tmux display-message -p '#{window_activity}'` → unix timestamp; `working` if age ≤ 10s.
- Fallback (cwd unreadable): `ALIVE_WINDOW_SECS=3600` JSONL age check + 10s mtime threshold.

**Mains** (Ghostty terminals):
- Alive if JSONL mtime within `ALIVE_WINDOW_SECS=3600` (1h).
- **Priority 1 — Hook state** (`~/.monitor_cc_menubar_hooks.json`): `session_id` maps directly to JSONL stem. If entry exists and `updated_ts` within `ALIVE_WINDOW_SECS`: use `status` as-is. `UserPromptSubmit` sets working from T=0 (captures thinking phase); `Stop`/`StopFailure` set idle immediately. No heuristic lag.
- **Priority 2 — JSONL mtime** (fallback when hooks absent/stale): mtime ≤ `WORKING_THRESHOLD_SECS=10s` = working.
- **Priority 3 — Proxy override** (fallback): `proxy_mtime > jsonl_mtime AND (now - proxy_mtime) ≤ THINKING_OVERRIDE_MAX_SECS=300s` → working.
- Auto-focus: on `working → idle` transition with `has_bg=False`, `_focus_session(cwd)` fires after a 3s debounce (`_idle_since_ts` dict).

## Title-Marker Mapping (tty → Ghostty terminal UUID)

**Problem:** Ghostty's AppleScript `working directory` property reflects the PTY's initial cwd, not the shell's current cwd. `focus (first terminal whose working directory is "...")` fails for sessions where the shell ran `cd X && python3 workflow.py --project Y`.

**Solution:** OSC 2 title-marker bootstrap. Each Ghostty tab has a direct child process (login shell) with a known TTY device (`/dev/ttys<NNN>`). Writing `\033]2;<marker>\007` to that device sets the Ghostty tab's `name` property. An AppleScript query immediately after returns `id|||name` pairs → marker appears in `name` → we learn the UUID for that TTY.

**Probe flow** (`_refresh_ghostty_tty_to_id` in discover.py):
1. `ps -A` parsed for Ghostty PID → all current TTYs (`all_ttys`).
2. Stale cleanup: remove `_ghostty_tty_to_id` entries whose TTY is no longer in `all_ttys`.
3. Incremental filter: `new_ttys = [t for t in all_ttys if t not in _ghostty_tty_to_id]`. Empty → return immediately, no title flash.
4. Write `\033]2;__GHT_<8-hex-random>\007` to each `/dev/<new_tty>`.
5. `time.sleep(0.12)` — 120ms for Ghostty to process OSC 2.
6. `osascript` → all terminals `id|||name` pairs.
7. Cleanup: write `\033]2;\007` (empty string) → shell restores default title.
8. Match markers to IDs → merge into `_ghostty_tty_to_id`.

## Gotchas

- **Singleton enforcement via fcntl lock** (`system.py`): `run()` calls `_acquire_singleton_lock()` before constructing `CCMenuBarApp`. On success: sets `FD_CLOEXEC` on the fd (required for clean `os.execv` restart), writes PID, returns open file handle (held on `run()`'s stack frame for the process lifetime). On failure: prints to stderr and calls `sys.exit(0)`. **Exit code 0 is mandatory**: launchd `KeepAlive=true` respawns on non-zero exit only.
- **Restart via os.execv** (`app.py:_PanelController.restartApp_`): `os.execv(sys.executable, [sys.executable] + sys.argv)` — replaces current process image in-place. Same PID, no race condition, no double bar-icon. `FD_CLOEXEC` on the singleton lock fd enables re-acquisition by the new image.
- **Lazy import in system.run()**: `from .app import CCMenuBarApp` is inside `run()` to break the `app→system→app` circular import. `app.py` imports `_focus_session` from `system.py` at module level; `system.py` has no module-level import of `app.py`. No circular dependency at module init time.
- **bg_result always passed explicitly to `_rebuild_panel`**: the `_rebuild_panel` fallback scan was removed from panel.py (to keep panel.py free of discover dependency). `app.py:_tick` passes `_scan_bg_sleep_timers()` explicitly on the panel-closed session-set-change path.
- **Global hotkey Cmd+L** (`hotkey.py`): `register_cmd_l(callback)` wraps the callback in a ctypes `CFUNCTYPE` and registers via Carbon `RegisterEventHotKey`. Returns `(cb_handle, hk_handle)` — caller (`CCMenuBarApp.__init__`) stores both on `self._hotkey_cb` / `self._hotkey_ref` to prevent GC of the C callback.
- `quit_button=None` passed to `rumps.App.__init__` — default rumps quit button is menu-attached and would be orphaned after `setMenu_(None)`. Restart is a footer NSButton wired to `_PanelController.restartApp_`.
- **Lazy-init timing** (`app.py`): `rumps.App._nsapp` is only populated after `app.run()` starts the AppKit runloop. `setMenu_(None)` + button wiring happens in the first `_tick` call (guarded by `if not self._initialized`).
- **Dynamic panel height (grow-only)** (`panel.py`): `_rebuild_panel` calls `_compute_required_height` → `_resize_panel(app, max(app._panel_min_height, required_h))`. Panel never shrinks below user-set floor. `NSBoxSeparator` containers in NSStackView require explicit `heightAnchor().constraintEqualToConstant_(18.0)` — plain `NSView` has no `intrinsicContentSize`.
- **Resize cursors on panel edges** (`panel.py`): `_PanelContentView(NSView)` as `panel.contentView()` — its `resetCursorRects()` registers four cursor rects. `_CursorlessLabel(NSTextField)` overrides `resetCursorRects` with no-op to prevent I-Beam installation from display-only labels winning over edge cursors.
- **Status-change is panel-no-op**: working↔idle transitions NEVER trigger `_rebuild_panel` or `_resize_panel`. Open panel: status changes go through `_update_panel_inplace`. Closed panel: only trigger `_blink`. Only two events trigger `_rebuild_panel`: (1) session-set change; (2) abort-button None↔Some transition (panel open only).
- **NSStackView gravity**: requires BOTH `addView_inGravity_(view, 1)` AND `setDistribution_(-1)` (`NSStackViewDistributionGravityAreas`). `setDistribution_(0)` ignores gravity entirely.
- **launchd PATH inheritance**: `EnvironmentVariables/PATH` in the plist must prepend `/opt/homebrew/bin` — launchd's default PATH lacks Homebrew, making `tmux` unavailable for worker-alive checks.
- **Badge column alignment**: `[*]`/`[ ]` fixed 3 chars; `_NO_BG` spacer 3 chars; `[B M:SS]` variable 3–9 chars but nothing follows it, so no misalignment.
- **Settings backwards-compat** (`app.py:_load_settings`): reads `panel_min_height` first, falls back to legacy `panel_max_height`, then `PANEL_HEIGHT=460`. Old files migrate transparently.
