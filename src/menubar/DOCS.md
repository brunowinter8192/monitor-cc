# src/menubar/

## Role

Standalone macOS status-bar (menubar) application that shows all currently-running Claude Code sessions on this Mac with their working/idle status and background-task badge. Independent of the tmux TUI — launched via `workflow.py --mode menubar` or launchd. macOS only (rumps/AppKit).

## Public Interface

`from src.menubar import run` — `run()` is the sole entry point. Called by `workflow.py --mode menubar`.

## Flow

1. `run()` (system.py) → sets `LSUIElement=1` env → acquires singleton lock → instantiates `CCMenuBarApp` → `app.run()` starts AppKit runloop.
2. `CCMenuBarApp._tick()` (app.py) fires every 1.5s → `list_alive_sessions()` → auto-focus debounce → `_scan_bg_sleep_timers(cwd_to_project)` → `_auto_abort_check()` → `_aggregate_bg()` → if panel closed: blink on status change; `_rebuild_panel` only on session-set change; if panel open: on None↔Some transition or session-set change call `_rebuild_panel` (adds/removes abort button, grows panel), otherwise `_update_panel_inplace` (updates NSButton attributed titles only, no resize).
3. `list_alive_sessions()` (discover.py) → refreshes CC-process cache (proc_cache.py) → refreshes Ghostty TTY-to-UUID mapping (ghostty.py) → scans `~/.claude/projects/*/` → determines working/idle status per session type → checks `/tmp/claude-<uid>/` for in-progress tasks (proc_cache.py).
4. Click on a main session → `_focus_session(cwd)` (system.py) → looks up Ghostty terminal UUID (ghostty.py) → `focus terminal id "<UUID>"` (Path A) or cwd-match fallback (Path B).

## Modules

### panel.py (266 LOC)

**Purpose:** NSPanel construction, NSView/NSTextField subclasses for cursor-rect pattern, all UI factory helpers, and the two render functions (`_rebuild_panel`, `_update_panel_inplace`). Footer has two buttons: Kill (left) + Restart (right). Pure UI concern — no rumps, no ctypes, no subprocess.
**Reads:** `app` instance attrs (`_panel_sv`, `_panel_width`, `_panel_min_height`, `_displayed_items`, `_cwd_map`, `_abort_btn`, `_toggle_btn`, `_panel_controller`, `_auto_focus`, `_panel`) via function parameters; session list from caller.
**Writes:** `app._displayed_items`, `app._cwd_map`, `app._abort_btn` (reset + populate on each rebuild); NSButton attributed titles (inplace update); NSPanel frame (via `_resize_panel`).
**Called by:** `app.py` (`CCMenuBarApp.__init__`, `_PanelController.togglePanel_`, `_PanelController.windowDidEndLiveResize_`, `CCMenuBarApp._tick`).
**Calls out:** `AppKit`, `Foundation`, `itertools`.

---

### paths.py (31 LOC)

**Purpose:** Single source of truth for the 4 APP_SUPPORT file paths (`SETTINGS_FILE`, `HOOKS_FILE`, `HOOKS_LOCK`, `PID_FILE`) under `~/Library/Application Support/com.brunowinter.monitor_cc_menubar/`. Runs `_migrate_from_dotfiles()` at import — moves any `~/.monitor_cc_menubar_*` dotfiles to APP_SUPPORT atomically; NEW wins if both exist.
**Reads:** old dotfile paths under `~` on first import (migration); nothing thereafter.
**Writes:** creates `_APP_SUPPORT` dir; moves old dotfiles to new paths on first import.
**Called by:** `app.py` (`SETTINGS_FILE`); `proc_cache.py` (`HOOKS_FILE`); `system.py` (`PID_FILE`). `hook_writer.py` derives equivalent paths locally (standalone script, no relative import).
**Calls out:** `pathlib` only.

---

### app.py (288 LOC)

**Purpose:** `CCMenuBarApp` (rumps.App subclass) + `_PanelController` (NSObject target for panel toggle/focus/kill/restart/abort/resize delegate) + `_tick` timer + blink + bar-icon + settings load/save + `_auto_abort_check` (per-project 5s-debounce auto-abort of bg timers when all workers idle).
**Reads:** `list_alive_sessions()` + `_scan_bg_sleep_timers()` on every tick; `SETTINGS_FILE` (`APP_SUPPORT/settings.json`) on launch; `app` instance state throughout.
**Writes:** bar icon via attributed NSStatusItem button; `SETTINGS_FILE` (`APP_SUPPORT/settings.json`) on toggle/resize.
**Called by:** `system.py:run()` (lazy import).
**Calls out:** `rumps`, `AppKit` (NSAttributedString/NSBaselineOffsetAttributeName/NSFont/NSFontAttributeName), `Foundation` (NSObject/NSOperationQueue), `objc`, `subprocess`, `threading`, `pathlib`; `.panel`, `.hotkey`, `.system`, `.discover` (`list_alive_sessions`), `.bg_timer` (`_scan_bg_sleep_timers`, `_abort_bg_sleep_timers`, `_aggregate_bg`); `.setup_menubar` (`write_plist`, lazy import inside `restartApp_`).

---

### hotkey.py (54 LOC)

**Purpose:** Standalone Carbon Cmd+L global hotkey registration. Zero project dependencies — only `ctypes`.
**Reads:** nothing.
**Writes:** Carbon event handler + hotkey registration via CDLL.
**Called by:** `app.py:CCMenuBarApp.__init__` (`register_cmd_l`).
**Calls out:** `ctypes` (Carbon framework CDLL).

---

### system.py (76 LOC)

**Purpose:** `run()` entry point + singleton lock (`_acquire_singleton_lock`) + Ghostty click-to-focus (`_focus_session`). Owns the process-lifecycle concerns; no AppKit dependency.
**Reads:** `PID_FILE` (`APP_SUPPORT/menubar.pid`, lock file); `get_ghostty_terminal_id(cwd)` from `ghostty.py` on click.
**Writes:** `PID_FILE` (`APP_SUPPORT/menubar.pid`); `/tmp/monitor_cc_menubar_focus.log` (focus results via osascript).
**Called by:** `workflow.py` (via `from src.menubar import run` → `__init__.py` → `system.run`); `app.py:_PanelController.focusSession_` + `CCMenuBarApp._tick` (`_focus_session`).
**Calls out:** `fcntl`, `os`, `subprocess` (osascript), `sys`; `.ghostty` (`get_ghostty_terminal_id`); lazy `.app` (`CCMenuBarApp`) inside `run()` only.

---

### discover.py (174 LOC)

**Purpose:** Session discovery entry point — scans JSONL files, classifies sessions (main vs worker), determines working/idle/background status per session type. Orchestrates the per-tick refresh pipeline and delegates to submodules for cache management, Ghostty mapping, and background-task detection.
**Reads:** `~/.claude/projects/*/` JSONL mtimes + last lines; delegates process/tmux/proxy/hook reads to `proc_cache.py`; delegates Ghostty TTY mapping to `ghostty.py`.
**Writes:** nothing directly. Delegates all writes to submodules.
**Called by:** `app.py:CCMenuBarApp._tick` + `app.py:_PanelController.windowDidEndLiveResize_` (`list_alive_sessions`).
**Calls out:** `session_finder.get_project_directories`; `.proc_cache`; `.ghostty`.

---

### proc_cache.py (137 LOC)

**Purpose:** Process and state caches — CC process pid→(tty,cwd) mapping, tmux session state, proxy log mtime lookup, hook state reader. All caches have TTL-based refresh (10s for proc/proxy/hook, 3s for tmux). Owns `_TASKS_BASE` and `_has_active_bg()` (in-progress task detection).
**Reads:** `ps -A` + `lsof -d cwd` (CC process cache); `tmux list-sessions` (tmux state); `_PROXY_LOG_DIR/api_requests_*.jsonl` mtimes; `HOOKS_FILE` (`APP_SUPPORT/hooks.json`, hook state).
**Writes:** module-level caches (`_cc_proc_cache`, `_tmux_state_cache`, `_proxy_log_mtime_cache`, `_hook_state_cache`).
**Called by:** `discover.py:list_alive_sessions` (refresh calls); `discover.py:_process_project_dir` (query calls); `ghostty.py:_tty_for_cwd` (`_cc_proc_cache` import); `bg_timer.py:_scan_bg_sleep_timers` (`_cc_proc_cache` import); `bg_timer.py:_abort_bg_sleep_timers` (`_TASKS_BASE` import).
**Calls out:** `subprocess` (ps, lsof, tmux).

---

### ghostty.py (125 LOC)

**Purpose:** Ghostty terminal UUID mapping via OSC 2 title-marker probe. Maintains `_ghostty_tty_to_id` (tty → UUID) populated incrementally. Exposes `get_ghostty_terminal_id(cwd)` for click-to-focus routing in `system.py`.
**Reads:** `ps -A` (Ghostty PID + child TTYs); `/dev/ttys<NNN>` (OSC 2 marker writes); `osascript` (Ghostty terminal id|||name pairs); `_cc_proc_cache` from `proc_cache.py` (tty lookup for a given cwd).
**Writes:** `/dev/ttys<NNN>` (transient OSC 2 probe marker + empty-string cleanup); `_ghostty_tty_to_id`, `_ghostty_tty_last_refresh` (module state).
**Called by:** `discover.py:list_alive_sessions` (`_refresh_ghostty_tty_to_id`); `system.py:_focus_session` (`get_ghostty_terminal_id`).
**Calls out:** `subprocess` (ps, osascript); `.proc_cache` (`_cc_proc_cache`).

---

### bg_timer.py (111 LOC)

**Purpose:** Background sleep-timer scanning, per-project attribution, aggregation, and abort. Detects Opus `sleep N && echo done` background timers via `ps`; attributes each to a project via `gppid → _cc_proc_cache → cwd → cwd_to_project` lookup. Returns `Dict[str, BgSleepInfo]` keyed by project_name ('unknown' bucket for unattributed timers). `_aggregate_bg()` collapses the dict to `Optional[BgSleepInfo]` for panel/abort callers. `_abort_bg_sleep_timers` kills PIDs via SIGTERM and writes `aborted\n` to in-progress task files.
**Reads:** `ps -A -o pid=,ppid=,etime=,args=` (timer detection); `_cc_proc_cache` (gppid→cwd attribution); `_TASKS_BASE` task dirs (for abort file writes).
**Writes:** `signal.SIGTERM` to sleep PIDs; `'aborted\n'` to 0-byte `*.output` task files under `_TASKS_BASE`.
**Called by:** `app.py:CCMenuBarApp._tick` (`_scan_bg_sleep_timers`, `_aggregate_bg`); `app.py:_PanelController.abortBgTimer_` (`_scan_bg_sleep_timers`, `_aggregate_bg`, `_abort_bg_sleep_timers`); `app.py:_PanelController.windowDidEndLiveResize_` (`_scan_bg_sleep_timers`, `_aggregate_bg`); `app.py:_auto_abort_check` (`_abort_bg_sleep_timers`).
**Calls out:** `subprocess` (ps); `.proc_cache` (`_TASKS_BASE`, `_cc_proc_cache`).

---

### hook_writer.py (73 LOC)

**Purpose:** CC hook handler — reads the JSON payload CC writes to stdin on UserPromptSubmit/Stop/StopFailure, then atomically updates `APP_SUPPORT/hooks.json` with `{session_id: {status, cwd, updated_ts}}`. Called by CC's hook system (installed via `hook_setup.py`). Prunes entries older than 7200s on each write to prevent unbounded file growth. Standalone script (never imported); defines `_APP_SUPPORT` locally rather than importing `paths.py`.
**Reads:** stdin (CC hook JSON payload); `APP_SUPPORT/hooks.json` (current state, inside exclusive lock).
**Writes:** `APP_SUPPORT/hooks.json` (atomic via temp + `os.replace()`); `APP_SUPPORT/hooks.lock` (flock coordination).
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

### setup_menubar.py (63 LOC)

**Purpose:** One-shot launchd bootstrap script — substitutes `<PROJECT_ROOT>` in the bundled plist template, writes it to `~/Library/LaunchAgents/`, then runs `launchctl bootout` (idempotent) + `launchctl bootstrap`. Includes a 1s-retry on "Input/output error" (intermittent on first install). Analog to `hook_setup.py`.
**Reads:** `src/menubar/com.brunowinter.monitor_cc_menubar.plist` (template).
**Writes:** `~/Library/LaunchAgents/com.brunowinter.monitor_cc_menubar.plist` (substituted).
**Called by:** User manually. Never imported.
**Calls out:** `subprocess` (launchctl); stdlib (`os`, `pathlib`, `time`).

**Usage:** `python3 src/menubar/setup_menubar.py` — run once after clone or when reinstalling the launchd service.

---

## Module Import Graph

```
stdlib only
    ↓
paths.py        (pathlib only — leaf node; triggers migration at import)
    ↓
proc_cache.py   (json, os, subprocess, time, pathlib, typing; .paths)
    ↓               ↓
ghostty.py          bg_timer.py
(_cc_proc_cache)    (_TASKS_BASE)
    ↓
discover.py  ← ghostty.py (_refresh_ghostty_tty_to_id)
             ← proc_cache.py (_refresh_cc_proc_cache, _refresh_tmux_state,
                               _tmux_session_exists, _read_hook_state,
                               _proxy_log_newest_mtime, _has_active_bg)

hotkey.py   → ctypes only
panel.py    → AppKit, Foundation, itertools
system.py   → fcntl, os, subprocess, sys; .ghostty, .paths (PID_FILE)
              lazy(.app) inside run() only
app.py      → rumps, objc, AppKit, Foundation, time, threading, json, os, sys
              .panel, .hotkey, .system, .discover, .bg_timer, .paths (SETTINGS_FILE)
```

No cycles. `system.py` has no module-level import of `app.py`; the lazy import inside `run()` prevents the `app→system→app` circular dependency. `proc_cache.py` has no internal project imports (leaf node). `setup_menubar.py` and `hook_setup.py` are standalone scripts (stdlib + subprocess only), not imported by any module.

---

## State

| Variable | Module | Type | Owner | Description |
|---|---|---|---|---|
| `CCMenuBarApp._last_statuses` | app.py | `dict` | app instance | `{name: status}` snapshot for blink-on-change detection; updated every tick. |
| `CCMenuBarApp._idle_since_ts` | app.py | `dict` | app instance | `{name: float}` timestamps when each main session first went idle (debounce for auto-focus). Cleared on working or has_bg=True. |
| `CCMenuBarApp._all_workers_idle_since_ts` | app.py | `dict` | app instance | `{project_name: float}` timestamps when ALL workers of a project first went simultaneously idle while a bg timer was running. Cleared when any worker returns to working or the timer disappears. Auto-abort fires after 5s. |
| `CCMenuBarApp._panel_open` | app.py | `bool` | app instance | True while NSPanel is visible. Gates `_tick` between `_rebuild_panel` (closed) and `_update_panel_inplace` (open). Set/cleared by `_PanelController.togglePanel_`. |
| `CCMenuBarApp._initialized` | app.py | `bool` | app instance | Lazy-init sentinel: `setMenu_(None)` + button target/action wiring happens in first `_tick` after AppKit runloop starts. |
| `CCMenuBarApp._displayed_items` | panel.py | `dict` | panel.py (`_rebuild_panel`) | `{name: NSButton}` populated by `_rebuild_panel`; used by `_update_panel_inplace` for O(1) button lookup. Reset on each rebuild. |
| `CCMenuBarApp._cwd_map` | panel.py | `dict` | panel.py (`_rebuild_panel`) | `{tag: cwd}` for click-to-focus routing. NSButton carries integer tag; `focusSession_` reads `sender.tag()`. Reset on each rebuild. |
| `CCMenuBarApp._abort_btn` | panel.py | `NSButton\|None` | panel.py (`_rebuild_panel`) | Abort-timer button reference. `None` when no CC sleep timers running. Checked by `_tick` to detect None↔Some transition. |
| `CCMenuBarApp._toggle_btn` | panel.py | `NSButton` | panel.py (`_make_nspanel`) | Auto-Jump toggle button in fixed top_bar. Created by `_make_nspanel()`; target/action wired in lazy-init tick; title updated by `_rebuild_panel` and `toggleAutoJump_`. |
| `CCMenuBarApp._panel` | panel.py | `NSPanel` | panel.py (`_make_nspanel`) | The sticky dropdown panel. Created in `__init__`. Resized by `_resize_panel`. |
| `CCMenuBarApp._panel_sv` | panel.py | `NSStackView` | panel.py (`_make_nspanel`) | Vertical NSStackView filling content area. Arranged subviews rebuilt on each `_rebuild_panel`. |
| `CCMenuBarApp._panel_quit_btn` | app.py | `NSButton` | panel.py creates, app.py wires | Restart button in fixed footer (right). Target/action wired in lazy-init tick. |
| `CCMenuBarApp._panel_kill_btn` | app.py | `NSButton` | panel.py creates, app.py wires | Kill button in fixed footer (left of Restart, 8pt gap). Wired to `killApp_` in lazy-init tick. |
| `CCMenuBarApp._panel_controller` | app.py | `_PanelController` | app.py | Single PyObjC NSObject as ObjC target for all button actions. Held to prevent ARC GC. |
| `CCMenuBarApp._auto_focus` | app.py | `bool` | app.py | Whether auto-focus is enabled. Loaded from settings; toggled by `toggleAutoJump_`. |
| `CCMenuBarApp._panel_width` | app.py | `int` | app.py owns, panel.py uses | Current panel width in pts. Loaded from settings (fallback: `PANEL_WIDTH=380`). Updated by `windowDidResize_`. |
| `CCMenuBarApp._panel_min_height` | app.py | `int` | app.py owns, panel.py uses | Grow-only floor for panel height. Updated by `windowDidResize_`. `_rebuild_panel` sizes to `max(_panel_min_height, required_h)`. |
| `CCMenuBarApp._hotkey_cb` | app.py | `ctypes CFUNCTYPE` | app.py | GC anchor for ctypes callback returned by `register_cmd_l`. |
| `CCMenuBarApp._hotkey_ref` | app.py | `ctypes.c_void_p` | app.py | GC anchor for Carbon hotkey handle returned by `register_cmd_l`. |
| `_cc_proc_cache` | proc_cache.py | `Dict[pid, (tty, cwd)]` | module | CC processes. Incremental: `ps -A` every 10s drops gone PIDs; `lsof -d cwd` only for newly seen PIDs. |
| `_cc_proc_last_refresh` | proc_cache.py | `float` | module | Timestamp of last CC cache pass. |
| `_tmux_state_cache` | proc_cache.py | `set` | module | session_name set (alive check only). One `tmux list-sessions` call per 3s. |
| `_tmux_state_last_refresh` | proc_cache.py | `float` | module | Timestamp of last tmux state refresh. |
| `_proxy_log_mtime_cache` | proc_cache.py | `Dict[str, Tuple[float, Optional[float]]]` | module | `opus_<project_key>→(checked_at, newest_mtime)`. TTL=10s. |
| `_hook_state_cache` | proc_cache.py | `Dict[str, dict]` | module | `session_id→{status, cwd, updated_ts}`. Read from `APP_SUPPORT/hooks.json` (`HOOKS_FILE`). TTL=10s. |
| `_hook_state_last_read` | proc_cache.py | `float` | module | Timestamp of last hook state file read. |
| `_ghostty_tty_to_id` | ghostty.py | `Dict[str, str]` | module | tty → Ghostty terminal UUID. Populated incrementally by OSC 2 probe. |
| `_ghostty_tty_last_refresh` | ghostty.py | `float` | module | Timestamp of last probe cycle (updated only when a probe actually ran). |

## Activity Detection (per session type)

**Workers** (tmux sessions):
- Alive iff `tmux has-session -t =worker-{project_basename}-{worker_name}` returns 0. Exact-match `=` prefix prevents prefix-matching false positives.
- Session name reconstructed from worker JSONL cwd: split on `/.claude/worktrees/`, `basename(left)` = project basename.
- Alive fallback (cwd unreadable from JSONL): `ALIVE_WINDOW_SECS=3600` JSONL age guard.
- **Status — Hook only** (`APP_SUPPORT/hooks.json`): `session_id` maps directly to JSONL stem. If entry exists and `updated_ts` within `ALIVE_WINDOW_SECS`: use `status` as-is. No entry or stale → `idle`. No fallback chain. `UserPromptSubmit` sets working from T=0; `Stop`/`StopFailure` set idle immediately.
- **Auto-abort** (`app.py:_auto_abort_check`): every tick, if ALL workers of a project are idle AND that project has an active bg sleep timer → start/keep a 5s debounce (`_all_workers_idle_since_ts[project_name]`). Any worker returning to working resets the debounce. After 5s: `_abort_bg_sleep_timers(proj_bg.sleep_pids)` fires (per-project PIDs only). 'unknown'-attributed timers are excluded from auto-abort. Projects with no workers at all are excluded (bool([]) guard).

**Mains** (Ghostty terminals):
- Alive if JSONL mtime within `ALIVE_WINDOW_SECS=3600` (1h).
- **Priority 1 — Hook state** (`APP_SUPPORT/hooks.json`): `session_id` maps directly to JSONL stem. If entry exists and `updated_ts` within `ALIVE_WINDOW_SECS`: use `status` as-is. `UserPromptSubmit` sets working from T=0 (captures thinking phase); `Stop`/`StopFailure` set idle immediately. No heuristic lag.
- **Priority 2 — JSONL mtime** (fallback when hooks absent/stale): mtime ≤ `WORKING_THRESHOLD_SECS=10s` = working. TTY mtime removed (cursor blinks cause stuck-at-working).
- **Priority 3 — Proxy override** (fallback): `proxy_mtime > jsonl_mtime AND (now - proxy_mtime) ≤ THINKING_OVERRIDE_MAX_SECS=300s` → working. See Gotchas.
- TTY still used for click-to-focus UUID lookup via `_cc_proc_cache`; not used for working detection.
- Auto-focus: on `working → idle` transition with `has_bg=False`, `_focus_session(cwd)` fires after a 3s debounce (`_idle_since_ts` dict).

## Title-Marker Mapping (tty → Ghostty terminal UUID)

**Problem:** Ghostty's AppleScript `working directory` property reflects the PTY's initial cwd, not the shell's current cwd. `focus (first terminal whose working directory is "...")` fails for sessions where the shell ran `cd X && python3 workflow.py --project Y`. Ghostty does NOT expose `tty` or `pid` via AppleScript.

**Solution:** OSC 2 title-marker bootstrap. Each Ghostty tab has a direct child process (login shell) with a known TTY device (`/dev/ttys<NNN>`). Writing `\033]2;<marker>\007` to that device sets the Ghostty tab's `name` property. An AppleScript query immediately after returns `id|||name` pairs → marker appears in `name` → we learn the UUID for that TTY.

**Probe flow** (`_refresh_ghostty_tty_to_id` in `ghostty.py`):

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

## Gotchas

- **Singleton enforcement via fcntl lock** (`system.py`): `run()` calls `_acquire_singleton_lock()` before constructing `CCMenuBarApp`. Lock file: `PID_FILE` = `APP_SUPPORT/menubar.pid`. On success: sets `FD_CLOEXEC` on the fd (required for clean `os.execv` restart), writes PID, returns open file handle (held on `run()`'s stack frame for the process lifetime). On failure: prints to stderr and calls `sys.exit(0)`. **Exit code 0 is mandatory**: launchd `KeepAlive=true` respawns on non-zero exit only.
- **APP_SUPPORT migration** (`paths.py`): on first import, `_migrate_from_dotfiles()` moves `~/.monitor_cc_menubar_{settings,hooks}.json`, `~/.monitor_cc_menubar_hooks.lock`, and `~/.monitor_cc_menubar.pid` to `~/Library/Application Support/com.brunowinter.monitor_cc_menubar/`. `os.rename()` is atomic on APFS/HFS+ (same volume). If both old and new exist (partial prior migration or manual intervention): NEW wins, old silently deleted. `hook_writer.py` derives the same APP_SUPPORT path locally (standalone script; relative import not usable).
- **Restart via plist-resync + detached relaunch** (`app.py:_PanelController.restartApp_`): three-step flow: (1) `write_plist()` (imported from `setup_menubar.py`) — synchronously substitutes `<PROJECT_ROOT>` and writes the updated plist to `~/Library/LaunchAgents/` so any plist edits take effect immediately, not just on the next launchd cycle; (2) `subprocess.Popen(['sh', '-c', 'sleep 0.5 && python3 setup_menubar.py'], start_new_session=True)` — detached helper (survives parent exit) that runs `setup_menubar_workflow()` after a 0.5s grace period, which does `launchctl bootout` + `launchctl bootstrap` with the existing 1s-retry logic; (3) `rumps.quit_application()` — clean status-bar teardown, launchd sees the process exit and respawns from the freshly-written plist. `start_new_session=True` detaches the helper from the dying process so it is not killed when the parent exits. The `write_plist` import is inside `restartApp_` body (not module-level) as a defensive measure against any future import-order sensitivity.
- **Kill unloads the plist (`launchctl bootout`)**: `killApp_` (`app.py:_PanelController`) fires `launchctl bootout gui/<uid>/com.brunowinter.monitor_cc_menubar` via a detached `sh -c 'sleep 0.5 && ...'` subprocess (survives parent exit), then calls `rumps.quit_application()`. `bootout` removes the plist from the launchd domain so `KeepAlive=true` no longer respawns the process. Next reload requires login (`RunAtLoad=true`) or manual `launchctl bootstrap gui/<uid> ~/Library/LaunchAgents/com.brunowinter.monitor_cc_menubar.plist`.
- **Lazy import in system.run()**: `from .app import CCMenuBarApp` is inside `run()` to break the `app→system→app` circular import. `app.py` imports `_focus_session` from `system.py` at module level; `system.py` has no module-level import of `app.py`. No circular dependency at module init time.
- **bg_result always passed explicitly to `_rebuild_panel`**: the `_rebuild_panel` fallback scan was removed from panel.py (to keep panel.py free of discover/bg_timer dependency). `app.py:_tick` computes `bg_result = _aggregate_bg(_scan_bg_sleep_timers(cwd_to_project))` once per tick and passes it explicitly to all panel calls.
- **Global hotkey Cmd+L** (`hotkey.py`): `register_cmd_l(callback)` wraps the callback in a ctypes `CFUNCTYPE` and registers via Carbon `RegisterEventHotKey`. Returns `(cb_handle, hk_handle)` — caller (`CCMenuBarApp.__init__`) stores both on `self._hotkey_cb` / `self._hotkey_ref` to prevent GC of the C callback.
- `quit_button=None` passed to `rumps.App.__init__` — default rumps quit button is menu-attached and would be orphaned after `setMenu_(None)`. Restart is a footer NSButton wired to `_PanelController.restartApp_`.
- **Lazy-init timing** (`app.py`): `rumps.App._nsapp` is only populated after `app.run()` starts the AppKit runloop. `setMenu_(None)` + button wiring happens in the first `_tick` call (guarded by `if not self._initialized`).
- **Diagnostics gating** (`app.py:_tick_log`): tick logging is gated on `MENUBAR_DIAGNOSTICS=1` env var — default OFF. Without the var, `_tick_log` returns immediately (no file I/O). Enable by launching via `dev/menubar_debug.py` (sets the var automatically) or `launchctl setenv MENUBAR_DIAGNOSTICS 1` for the running launchd service. Log path: `_TICK_LOG = '/tmp/menubar-tick.log'`.
- Background task detection: `/tmp/claude-<uid>/` uses the numeric Unix UID (`os.getuid()`). `*.output` files with `st_size == 0` = in-progress; `done\n` (5 bytes) = completed.
- **Abort leaves task file at 0 bytes:** when the sleep child is killed via SIGTERM, the zsh parent exits via `&&` short-circuit (no `echo done` stdout), so CC writes nothing to the task file — it stays 0 bytes indefinitely. `_abort_bg_sleep_timers` (bg_timer.py) explicitly writes `aborted\n` to all 0-byte task files after kill so `_has_active_bg` returns False and the `[B]` badge disappears.
- **CC uses `zsh -c`, not `bash -c`:** background bash commands are actually `zsh -c "source ... && eval 'cmd' ..."`. `_scan_bg_sleep_timers` correctly matches these because `echo done` appears in the zsh parent's args; the sleep child args are always exactly `sleep N`.
- `LSUIElement=1` must be set before `app.run()` to suppress the Dock icon. Set in `run()` via `os.environ.setdefault`.
- Launched via launchd: `KeepAlive=true` auto-restarts on crash. Logs → `/tmp/monitor_cc_menubar.{log,err}`.
- **launchd PATH inheritance**: `EnvironmentVariables/PATH` in the plist must prepend `/opt/homebrew/bin` — launchd's default PATH lacks Homebrew, making `tmux` unavailable for proc_cache.py worker-alive checks.
- **Ghostty PID lookup** (`ghostty.py:_ghostty_pid`): `pgrep` is unreliable on macOS for full-path binary names. Use `ps -A -o pid=,command=` parsed directly: `'Ghostty.app/Contents/MacOS' in line` finds the process robustly.
- **Ghostty AppleScript**: Ghostty.sdef exposes `id` (UUID, stable), `name` (current title), `working directory` per `terminal`. `focus` command takes a specifier: `focus terminal id "<UUID>"`. Does NOT expose `tty` or `pid`.
- **OSC 2 cleanup**: After the probe, `\033]2;\007` (empty-string OSC 2) written to the probed TTYs restores the shell's default title. Without cleanup, idle shells show `__GHT_XXXXXXXX` until next prompt display.
- **TTY ownership**: Ghostty children run as `/usr/bin/login` (root) but the `/dev/ttys<NNN>` device files are owned by the logged-in user → write access OK.
- **Dynamic panel height (grow-only)** (`panel.py`): `_rebuild_panel` calls `_compute_required_height` → `_resize_panel(app, max(app._panel_min_height, required_h))`. Panel never shrinks below user-set floor. `NSBoxSeparator` containers in NSStackView require explicit `heightAnchor().constraintEqualToConstant_(18.0)` — plain `NSView` has no `intrinsicContentSize`.
- **Resize cursors on panel edges** (`panel.py`): `_PanelContentView(NSView)` as `panel.contentView()` — its `resetCursorRects()` registers four cursor rects. `_CursorlessLabel(NSTextField)` overrides `resetCursorRects` with no-op to prevent I-Beam installation from display-only labels winning over edge cursors.
- **Status-change is panel-no-op**: working↔idle transitions NEVER trigger `_rebuild_panel` or `_resize_panel`. Open panel: status changes go through `_update_panel_inplace`. Closed panel: only trigger `_blink`. Only two events trigger `_rebuild_panel`: (1) session-set change; (2) abort-button None↔Some transition (panel open only).
- **NSPanel ObjC attribute constraint**: NSPanel (and all PyObjC-bridged ObjC objects) reject arbitrary Python attribute assignment — `panel.my_attr = x` raises `AttributeError`. `_make_nspanel()` returns `(panel, stack, quit_btn)` as a Python tuple.
- **NSStackView gravity**: requires BOTH `addView_inGravity_(view, 1)` AND `setDistribution_(-1)` (`NSStackViewDistributionGravityAreas`). `setDistribution_(0)` ignores gravity entirely. Enum values: `GravityTop=1`, `GravityCenter=2`, `GravityBottom=3`; `DistGravityAreas=-1`, `DistFill=0`.
- **Badge column alignment**: `[*]`/`[ ]` fixed 3 chars; `_NO_BG` spacer 3 chars; `[B M:SS]` variable 3–9 chars but nothing follows it, so no misalignment.
- **Settings backwards-compat** (`app.py:_load_settings`): reads `panel_min_height` first, falls back to legacy `panel_max_height`, then `PANEL_HEIGHT=460`. Old files migrate transparently.
- **Auto-abort task-file write is global** (`bg_timer.py:_abort_bg_sleep_timers`): after killing sleep PIDs, writes `aborted\n` to ALL 0-byte `*.output` task files under `_TASKS_BASE`, not just those belonging to the aborted project. Pre-existing behavior shared with manual abort. If project B has live 0-byte task files when project A is auto-aborted, B's `[B]` badge may transiently disappear. In practice rare (requires simultaneous multi-project bg tasks).
- **Hook state as primary signal** (`proc_cache.py:_hook_state_cache`): `session_id` in hook payload == JSONL filename stem. Direct lookup, no encoding/decoding. Hook state stale guard uses `ALIVE_WINDOW_SECS=3600s`. Workers fire hooks too; their entries ARE consulted by the worker status branch (hook-only, no fallback).
- **Proxy-log thinking signal** (`proc_cache.py:_proxy_log_newest_mtime`): override condition: `proxy_mtime > jsonl_mtime AND (now - proxy_mtime) ≤ THINKING_OVERRIDE_MAX_SECS=300s` → status `working`. The `proxy_mtime > jsonl_mtime` check: proxy writes at the START of the reasoning phase, staying ahead for the full thinking duration. After response completion the proxy latency entry lands ~0.1s BEFORE CC writes JSONL, so `proxy_mtime` drops just below `jsonl_mtime` — no false positive.
- **_PROXY_LOG_DIR placement**: lives in `proc_cache.py` (not `discover.py`) to avoid an import cycle — `_proxy_log_newest_mtime` is its sole consumer and lives in proc_cache.py.

## Dev Tools

### dev/menubar_debug.py

Foreground debug runner — boots out the launchd service, starts the menubar app directly via venv Python with `MENUBAR_DIAGNOSTICS=1`, and optionally re-registers launchd on exit.

**Usage:**
```bash
# From project root:
python3 dev/menubar_debug.py               # foreground run; Ctrl-C to stop
python3 dev/menubar_debug.py --rebootstrap # same + re-registers launchd service on exit
```

**What it does:**
1. `launchctl bootout` (ignore failure — service may not be loaded)
2. Launches `venv/bin/python3 workflow.py --mode menubar` with `MENUBAR_DIAGNOSTICS=1` in env
3. On Ctrl-C: prints "Stopped"; if `--rebootstrap`: runs `launchctl bootstrap` from the installed plist

Tick log written to `/tmp/menubar-tick.log` while running (gated on `MENUBAR_DIAGNOSTICS=1`). stdout/stderr land in terminal directly. Requires `~/Library/LaunchAgents/com.brunowinter.monitor_cc_menubar.plist` to exist for `--rebootstrap` — run `src/menubar/setup_menubar.py` first if missing.
