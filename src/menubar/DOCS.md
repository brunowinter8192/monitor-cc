# src/menubar/

## Role

Standalone macOS status-bar (menubar) application that shows all currently-running Claude Code sessions on this Mac with their working/idle status and background-task badge. Independent of the tmux TUI — launched via `workflow.py --mode menubar` or launchd. macOS only (rumps/AppKit).

## Public Interface

`from src.menubar import run` — `run()` is the sole entry point. Called by `workflow.py --mode menubar`.

## Flow

1. `run()` (system.py) → sets `LSUIElement=1` env → acquires singleton lock → instantiates `CCMenuBarApp` → `app.run()` starts AppKit runloop.
2. `CCMenuBarApp._tick()` (app.py) fires every 1.5s → `list_alive_sessions()` → auto-focus debounce → `_scan_bg_sleep_timers(cwd_to_project)` → `_auto_abort_check()` → `_aggregate_bg()` → if panel closed: blink on status change; `_rebuild_panel` only on session-set change; if panel open: on None↔Some transition or session-set change call `_rebuild_panel` (adds/removes abort button, grows panel), otherwise `_update_panel_inplace` (updates NSButton attributed titles only, no resize).
3. `list_alive_sessions()` (discover.py) → refreshes CC-process cache (proc_cache.py) → refreshes Ghostty TTY-to-UUID mapping (ghostty.py) → scans `~/.claude/projects/*/` → determines working/idle status per session type → checks `/tmp/claude-<uid>/` for in-progress tasks (proc_cache.py).
4. Click on a main session → `_focus_session(cwd)` (system.py) → looks up Ghostty terminal UUID (ghostty.py) → `focus terminal id "<UUID>"` (Path A) or cwd-match fallback (Path B). Same path triggered by Cmd+1..9 when panel is open (see hotkey.py + app.py lifecycle).

## Modules

### panel.py (462 LOC) ⚠ over 400 LOC ceiling — split-refactor deferred

**Purpose:** NSPanel construction, NSView/NSTextField/NSButton subclasses for cursor tracking, all UI factory helpers, and the two render functions (`_rebuild_panel`, `_update_panel_inplace`). Footer has two buttons: Kill (left) + Restart (right). Main session rows carry an inline `[N] ` prefix (slots 1..9) for Cmd+N hotkey reference; workers and slots >9 carry no prefix. Per-project abort buttons (Option B) are embedded inline in the project separator rows — `_make_separator_view` returns `(NSView, Optional[NSButton])`. Queue UI removed — moved to `queue_panel.py`. Defines `_KeyablePanel(NSPanel)` — overrides `canBecomeKeyWindow` to return True so all three panels can receive keyboard events despite `NSWindowStyleMaskNonactivatingPanel`; imported by bead_panel.py and queue_panel.py. Also overrides `performKeyEquivalent_` to route Cmd+{V,C,X,A,Z} and Shift+Cmd+Z to the first responder via `respondsToSelector_`/`performSelector_withObject_` — `rumps.App` has no main menu Edit items, so these key equivalents would otherwise fall through silently. Rebuild: `sv.removeFromSuperview()` called after `removeView_` — NSStackView.removeView_ removes from arrangedSubviews only, not from view hierarchy. Pure UI concern — no rumps, no ctypes, no subprocess.
**Reads:** `app` instance attrs (`_panel_sv`, `_panel_width`, `_panel_min_height`, `_displayed_items`, `_cwd_map`, `_abort_btns_by_project`, `_abort_project_for_tag`, `_toggle_btn`, `_panel_controller`, `_auto_focus`, `_panel`) via function parameters; session list and `bg_by_project` dict from caller.
**Writes:** `app._displayed_items`, `app._cwd_map`, `app._abort_btns_by_project`, `app._abort_project_for_tag` (reset on each rebuild); NSPanel frame.
**Key signatures:** `_rebuild_panel(app, sessions, bg_by_project=None)`, `_update_panel_inplace(app, sessions, bg_by_project)`, `_compute_required_height(sorted_sessions)`.
**Called by:** `app.py` (`_open_main_panel`, `_PanelController.abortBgTimer_`, `CCMenuBarApp._tick`, `_PanelController.windowDidEndLiveResize_`).
**Calls out:** `AppKit`, `Foundation`, `itertools`.

---

### queue_panel.py (269 LOC)

**Purpose:** Standalone NSPanel (3rd panel) for the per-session message queue. Analogous to `bead_panel.py`. `_make_queue_nspanel()` returns `(panel, stack, toggle_btn)` — no footer. `_rebuild_queue_panel(app, sessions)` renders per-main-session blocks via ONE NSGridView (1-col): every row is a full-width container `NSView` (`wantsLayer=True`). Three-state rows: **draft** (no background, editable NSTextField, `↑` toggle button, `×` delete), **queued** (red bg tint via `layer.backgroundColor = systemRedColor α0.18`, read-only label, `↓` toggle, `×` delete), **sent** (green bg tint, read-only label, no toggle, `×` delete). Session headers and `+` add-btn are also full-width views. Container background pattern: `view.setWantsLayer_(True)` + `view.layer().setBackgroundColor_(NSColor.systemRedColor().colorWithAlphaComponent_(0.18).CGColor())` — no Quartz import needed (AppKit bridging exposes `.CGColor()`). All NSGridView direct content views carry explicit `widthAnchor` + `heightAnchor` constraints (TAMIC disabled by NSGridView). NSTextField first-responder fix: `makeKeyAndOrderFront_(None)` + `makeFirstResponder_(tf)` on first draft field after rebuild. Constants: `_QUEUE_TOGGLE_W = 22` (toggle btn), `_QUEUE_MINUS_W = 22` (× btn). Column layout inside container (frame-based, not AutoLayout): `[0..col0_w) text | [col0_w..col0_w+TOGGLE_W) toggle | [col0_w+TOGGLE_W..pw) ×`.
**Reads:** `app._queue_sv`, `app._queue_panel`, `app._queue_toggle_btn`, `app._queue_data`, `app._panel_width`, `app._panel_min_height`, `app._auto_focus`, `app._panel_controller`; `sessions` list from caller.
**Writes:** `app._queue_add_tags`, `app._queue_remove_tags`, `app._pending_queue_tags`, `app._queue_toggle_tags`, `app._queue_displayed_names` (reset on each rebuild); NSPanel frame.
**Key signatures:** `_make_queue_nspanel()`, `_rebuild_queue_panel(app, sessions)`, `_reposition_queue_panel(panel, nsstatusitem)`, `_resize_queue_panel(app, new_h)`.
**Called by:** `app.py` (`_open_queue_panel`, `_PanelController.*Queue*`, `CCMenuBarApp._tick`, `_PanelController.windowDidEndLiveResize_`).
**Calls out:** `AppKit`, `Foundation`; `.panel` (constants + helpers); `.queue` (`load_queue`, `save_queue`).

---

### bead_panel.py (289 LOC)

**Purpose:** Bead-tracker NSPanel (2nd panel). ONE NSGridView (2-col): col 0 = expand button (flexible), col 1 = × untrack button (22pt fixed). Expand rows merged across both columns. `_make_expand_view` builds a per-line NSTextField container for the expanded bead content; when content exceeds `_BEAD_EXPAND_MAX_LINES = 20` rows, wraps in NSScrollView with fixed-height viewport (`20 × _ROW_H` ≈ 420pt), vertical scroller always visible, no horizontal scroll. Container `widthAnchor` anchored to `sv.contentView().widthAnchor()` (scrolled) or set to `panel_width` directly (non-scrolled) — required because NSGridView disables TAMIC on content views; without explicit width constraint AutoLayout assigns `w=0`.
**Reads:** `app._bead_data`, `app._bead_expanded`, `app._bead_expand_tags`, `app._bead_untrack_tags`, `app._bead_displayed`, `app._bead_db_paths`, `app._panel_width`, `app._panel_min_height`, `app._tracker_sv`, `app._tracker_panel`, `app._tracker_toggle_btn`, `app._panel_controller`.
**Writes:** `app._bead_expanded` (clear or set expand text); `app._bead_displayed`, `app._bead_expand_tags`, `app._bead_untrack_tags` (reset each rebuild); NSPanel frame.
**Key signatures:** `_make_bead_nspanel()`, `_rebuild_bead_panel(app)`, `_reposition_bead_panel(panel, nsstatusitem)`, `_compute_bead_height(app)`, `_handle_expand_bead(app, tag)`, `_handle_untrack_bead(app, tag)`.
**Called by:** `app.py` (`_open_tracker_panel`, `_PanelController.expandBead_`, `_PanelController.untrackBead_`, `CCMenuBarApp._tick`, `_PanelController.windowDidEndLiveResize_`).
**Calls out:** `AppKit` (incl. `NSScrollView`), `Foundation`; `.bead_data` (`bd_show_text`, `bd_label_remove`); `.panel` (constants + helpers).

---

### bead_data.py (132 LOC)

**Purpose:** All `bd` CLI interactions for the bead panel. `bd_show_text(bead_id, db_path)` runs `bd show --json` (description) then `bd comments --json` (separate call; show does NOT include comments) and returns a formatted string: description body (≤300 chars before Sources block), Sources block (full), then per-comment blocks `[YYYY-MM-DD HH:MM by Author]\n  text`. `bd_label_remove` untracks a bead. Helper functions: `project_db_map`, `load_tracked_beads`, `_bd_list_tracked`, `_bd_fetch_comments`, `_format_expand_text`, `_format_comment_ts`. Comment JSON schema: `{id, issue_id, author, text, created_at}` — field is `text` (not `body`). Timestamps parsed via `datetime.fromisoformat` with Z→+00:00 substitution, displayed in local timezone.
**Reads:** `bd` CLI output via subprocess; nothing from app state.
**Writes:** nothing (read-only toward bd).
**Called by:** `bead_panel.py` (`bd_show_text`, `bd_label_remove`); `app.py` (`project_db_map`, `load_tracked_beads` via `bead_panel` import chain).
**Calls out:** `subprocess` (`bd`); stdlib (`json`, `datetime`, `pathlib`).

---

### paths.py (34 LOC)

**Purpose:** Single source of truth for 7 APP_SUPPORT file paths under `~/Library/Application Support/com.brunowinter.monitor_cc_menubar/`: `SETTINGS_FILE`, `HOOKS_FILE`, `HOOKS_LOCK`, `PID_FILE`, `QUEUE_FILE` (`msg_queue.json`), `QUEUE_LOCK` (`queue.lock`), `GHOSTTY_CWD_UUID_FILE` (`ghostty_cwd_uuid.json`). Runs `_migrate_from_dotfiles()` at import.
**Reads:** old dotfile paths under `~` on first import (migration); nothing thereafter.
**Writes:** creates `_APP_SUPPORT` dir; moves old dotfiles to new paths on first import.
**Called by:** `app.py` (`SETTINGS_FILE`); `proc_cache.py` (`HOOKS_FILE`); `system.py` (`PID_FILE`); `queue.py` (`QUEUE_FILE`, `QUEUE_LOCK`, `GHOSTTY_CWD_UUID_FILE`). `hook_writer.py` and `ghostty.py` define equivalent paths inline (standalone / cycle-avoidance).
**Calls out:** `pathlib` only.

---

### queue.py (96 LOC)

**Purpose:** Message queue storage + Ghostty delivery for the menubar app side. `load_queue()` / `save_queue(q)` — atomic read/write of `APP_SUPPORT/msg_queue.json` (schema: `{session_id: [{text: str, state: "draft"|"queued"|"sent", sent_at: str|null}]}`). `load_queue` normalizes all legacy formats via `_normalize_entry` on read — migration is transparent on next save. Migration rules: bare string → `{state:"queued"}`; dict missing `state`: `sent_at` non-null → `state:"sent"`, else → `state:"queued"`. Drafts are only created via the + button, never from migration. `deliver_message(cwd, message)` — reads `ghostty_cwd_uuid.json` for terminal UUID, then `focus terminal id UUID` + System Events `keystroke + Return`; falls back to cwd-based focus. Hook delivery uses inline equivalents in `hook_writer.py` (standalone, can't import from package).
**Reads:** `QUEUE_FILE` (`msg_queue.json`); `GHOSTTY_CWD_UUID_FILE` (`ghostty_cwd_uuid.json`).
**Writes:** `QUEUE_FILE` (atomic via temp + `os.replace()`); osascript delivery to Ghostty.
**Called by:** `app.py:_PanelController` (`load_queue`, `save_queue`); `app.py:CCMenuBarApp._tick` and `_open_main_panel` (`load_queue`).
**Calls out:** `json`, `os`, `subprocess`; `.paths` (`QUEUE_FILE`, `QUEUE_LOCK`, `GHOSTTY_CWD_UUID_FILE`).

---

### app.py (714 LOC) ⚠ over 400 LOC ceiling — split-refactor deferred

**Purpose:** `CCMenuBarApp` (rumps.App subclass) + `_PanelController` (NSObject target for all button actions + NSTextField delegate) + `_tick` timer + blink + bar-icon + settings load/save + `_auto_abort_check`. Three-panel lifecycle: `_open/close_main_panel`, `_open/close_tracker_panel`, `_open/close_queue_panel`. Panel cycling via `_deferred_close_open(app, from, to)` (generic, dispatched through NSOperationQueue.mainQueue). Queue controller methods wired to queue panel: `addQueueRow_` (append empty draft; guard against stacking blanks), `toggleQueueEntry_` (draft↔queued flip), `removeQueueEntry_` (× delete), `commitQueueField_` (Enter → save draft text in-place), `controlTextDidEndEditing_` (blur → save draft text in-place). `_tick` caches sessions in `app._last_sessions`; `queue_changed` triggers `_rebuild_queue_panel` if queue panel is open.
**Reads:** `list_alive_sessions()` + `_scan_bg_sleep_timers()` on every tick and on panel open; `SETTINGS_FILE` on launch; `QUEUE_FILE` (via `load_queue()`) on every tick + on `_open_queue_panel`.
**Writes:** bar icon; `SETTINGS_FILE` on toggle/resize; `QUEUE_FILE` (via `save_queue()`) on queue UI add/remove/toggle/edit; `_queue_data`, `_queue_add_tags`, `_queue_remove_tags`, `_queue_toggle_tags`, `_pending_queue_tags`, `_last_sessions`, `_queue_displayed_names`.
**Called by:** `system.py:run()` (lazy import).
**Calls out:** `rumps`, `AppKit`, `Foundation`, `objc`, `subprocess`, `threading`; `.panel`, `.bead_panel`, `.queue_panel`, `.hotkey`, `.system`, `.discover`, `.bg_timer`, `.paths`, `.queue` (`load_queue`, `save_queue`); `.setup_menubar` (lazy).

---

### hotkey.py (259 LOC)

**Purpose:** Carbon global hotkey registration. Two public APIs: `register_cmd_l(callback)` — installs the Cmd+L panel-toggle hotkey at app start, kept alive for process lifetime by caller (`app._hotkey_cb`, `app._hotkey_ref`). `register_cmd_digits(callback_map)` / `unregister_hotkeys(refs)` — installs Cmd+1..9 hotkeys lazily on first panel-open, unregisters on panel-close. Module-level state: `_DIGIT_HANDLER_CB` / `_DIGIT_HANDLER_REF` persist the InstallEventHandler across register/unregister cycles (CRITICAL: GC'ing the CFUNCTYPE while the handler is still in Carbon's dispatch chain crashes with SIGSEGV on the next hotkey event); `_DIGIT_CALLBACKS` is the mutable slot→callback map the handler reads. Both `register_cmd_l._handler` and the digit handler filter via `GetEventParameter(kEventParamDirectObject, typeEventHotKeyID)` and return `eventNotHandledErr (-9874)` for unknown IDs so the other handler receives its event unswallowed.
**Reads:** nothing.
**Writes:** Carbon event handlers + hotkey registrations via CDLL; mutates module-level `_DIGIT_CALLBACKS` dict.
**Called by:** `app.py:CCMenuBarApp.__init__` (`register_cmd_l`); `app.py:_reregister_digit_hotkeys` (`register_cmd_digits`, `unregister_hotkeys`).
**Calls out:** `ctypes` (Carbon framework CDLL).

---

### system.py (76 LOC)

**Purpose:** `run()` entry point + singleton lock (`_acquire_singleton_lock`) + Ghostty click-to-focus (`_focus_session`). Owns the process-lifecycle concerns; no AppKit dependency.
**Reads:** `PID_FILE` (`APP_SUPPORT/menubar.pid`, lock file); `get_ghostty_terminal_id(cwd)` from `ghostty.py` on click.
**Writes:** `PID_FILE` (`APP_SUPPORT/menubar.pid`); `/tmp/monitor_cc_menubar_focus.log` (focus results via osascript).
**Called by:** `workflow.py` (via `from src.menubar import run` → `__init__.py` → `system.run`); `app.py:_PanelController.focusSession_` + `CCMenuBarApp._tick` (`_focus_session`).
**Calls out:** `fcntl`, `os`, `subprocess` (osascript), `sys`; `.ghostty` (`get_ghostty_terminal_id`); lazy `.app` (`CCMenuBarApp`) inside `run()` only.

---

### discover.py (176 LOC)

**Purpose:** Session discovery entry point. `SessionInfo` now includes `session_id: str` (JSONL stem = CC session identifier; key for `msg_queue.json` queue). `list_alive_sessions` calls `_write_cwd_uuid_map()` after each tick so `APP_SUPPORT/ghostty_cwd_uuid.json` stays current for hook delivery.
**Reads:** `~/.claude/projects/*/` JSONL mtimes + last lines; delegates to `proc_cache.py`; Ghostty mapping via `ghostty.py`.
**Writes:** nothing directly. Delegates writes to submodules (incl. `_write_cwd_uuid_map`).
**Called by:** `app.py:CCMenuBarApp._tick`, `app.py:_open_main_panel`, `app.py:_PanelController.*Queue*` methods.
**Calls out:** `session_finder.get_project_directories`; `.proc_cache`; `.ghostty` (`_refresh_ghostty_tty_to_id`, `_write_cwd_uuid_map`).

---

### proc_cache.py (137 LOC)

**Purpose:** Process and state caches — CC process pid→(tty,cwd) mapping, tmux session state, proxy log mtime lookup, hook state reader. All caches have TTL-based refresh (10s for proc/proxy/hook, 3s for tmux). Owns `_TASKS_BASE` and `_has_active_bg()` (in-progress task detection).
**Reads:** `ps -A` + `lsof -d cwd` (CC process cache); `tmux list-sessions` (tmux state); `_PROXY_LOG_DIR/api_requests_*.jsonl` mtimes; `HOOKS_FILE` (`APP_SUPPORT/hooks.json`, hook state).
**Writes:** module-level caches (`_cc_proc_cache`, `_tmux_state_cache`, `_proxy_log_mtime_cache`, `_hook_state_cache`).
**Called by:** `discover.py:list_alive_sessions` (refresh calls); `discover.py:_process_project_dir` (query calls); `ghostty.py:_tty_for_cwd` (`_cc_proc_cache` import); `bg_timer.py:_scan_bg_sleep_timers` (`_cc_proc_cache` import); `bg_timer.py:_abort_bg_sleep_timers` (`_TASKS_BASE` import).
**Calls out:** `subprocess` (ps, lsof, tmux).

---

### ghostty.py (152 LOC)

**Purpose:** Ghostty terminal UUID mapping via OSC 2 title-marker probe. Maintains `_ghostty_tty_to_id` (tty → UUID) populated incrementally. Exposes `get_ghostty_terminal_id(cwd)` for click-to-focus routing in `system.py`. Also writes `APP_SUPPORT/ghostty_cwd_uuid.json` = `{cwd: uuid}` via `_write_cwd_uuid_map()` (called from `discover.py:list_alive_sessions` after each tick); used by `hook_writer.py` for queue delivery. `_APP_SUPPORT` defined inline (can't import `paths.py` — would create import cycle).
**Reads:** `ps -A` (Ghostty PID + child TTYs); `/dev/ttys<NNN>` (OSC 2 marker writes); `osascript` (terminal id|||name pairs); `_cc_proc_cache`.
**Writes:** `/dev/ttys<NNN>` (probe + cleanup); `_ghostty_tty_to_id`, `_ghostty_tty_last_refresh`, `_ghostty_cwd_uuid_last` (module state); `APP_SUPPORT/ghostty_cwd_uuid.json` (atomic, change-detected).
**Called by:** `discover.py:list_alive_sessions` (`_refresh_ghostty_tty_to_id`, `_write_cwd_uuid_map`); `system.py:_focus_session` (`get_ghostty_terminal_id`).
**Calls out:** `json`, `subprocess`, `time`; `.proc_cache` (`_cc_proc_cache`).

---

### bg_timer.py (122 LOC)

**Purpose:** Background sleep-timer scanning, per-project attribution, and abort. Detects Opus `sleep N && echo done` background timers via `ps`; attributes each to a project via ancestry-chain walk → `_cc_proc_cache → cwd → cwd_to_project` lookup (walks up to 5 levels from the zsh parent to handle intermediate shell layers between CC and zsh). Returns `Dict[str, BgSleepInfo]` keyed by project_name ('unknown' bucket for unattributed timers). `_abort_bg_sleep_timers` kills PIDs via SIGTERM and writes `aborted\n` to in-progress task files.
**Reads:** `ps -A -o pid=,ppid=,etime=,args=` (timer detection); `_cc_proc_cache` (ancestry→cwd attribution); `_TASKS_BASE` task dirs (for abort file writes).
**Writes:** `signal.SIGTERM` to sleep PIDs; `'aborted\n'` to 0-byte `*.output` task files under `_TASKS_BASE`.
**Called by:** `app.py:CCMenuBarApp._tick` (`_scan_bg_sleep_timers`); `app.py:_PanelController.abortBgTimer_` (`_scan_bg_sleep_timers`, `_abort_bg_sleep_timers`); `app.py:_PanelController.windowDidEndLiveResize_` (`_scan_bg_sleep_timers`); `app.py:_auto_abort_check` (`_abort_bg_sleep_timers`).
**Calls out:** `subprocess` (ps); `.proc_cache` (`_TASKS_BASE`, `_cc_proc_cache`).

---

### hook_writer.py (182 LOC)

**Purpose:** CC hook handler — reads JSON payload on stdin; updates `hooks.json`; on Stop/StopFailure additionally delivers the first `state="queued"` entry from `msg_queue.json` for the session. Skips `state="draft"` and `state="sent"` entries. Delivery path: `_queue_get_first_unsent` (flock `queue.lock` → find first entry where `state=="queued"`) → `_deliver_message` (UUID focus + System Events keystroke; cwd fallback) → on success: `_queue_mark_sent` (flock → set `state="sent"` + `sent_at=utc-iso` in-place). On delivery failure: entry left unchanged, next Stop retries. Messages are never removed by the hook — only the panel's `×` button removes entries. `_normalize_entry` handles all legacy formats inline (mirrors `queue.py`). Standalone script; defines all 3 APP_SUPPORT paths inline.
**Reads:** stdin (CC hook JSON); `APP_SUPPORT/hooks.json` (inside flock); `APP_SUPPORT/msg_queue.json` (inside flock); `APP_SUPPORT/ghostty_cwd_uuid.json` (UUID lookup).
**Writes:** `APP_SUPPORT/hooks.json` (atomic); `APP_SUPPORT/msg_queue.json` (atomic, inside flock — mark `sent_at` in-place, never removes entries); `APP_SUPPORT/queue.lock`; osascript delivery to Ghostty terminal.
**Called by:** CC hook system (`async: true`). Never imported.
**Calls out:** stdlib (`datetime`, `fcntl`, `json`, `os`, `subprocess`, `time`).

**Usage:** `python3 src/menubar/hook_writer.py` (stdin = CC hook JSON). Install via `hook_setup.py`.

---

### hook_setup.py (141 LOC)

**Purpose:** Idempotent installer with two defense layers. **Layer 1 — Worktree Guard:** `_guard_not_worktree()` checks `Path(__file__).resolve().parts` for consecutive `.claude`/`worktrees` components; exits 2 with a clear error message if the script is running from a worktree path — preventing dead-path registration. **Layer 2 — Stale-hook Sweep:** `_sweep_stale_hooks()` iterates ALL event keys in `settings["hooks"]`, checks every `python3 <path>` entry, and removes any whose script path fails `os.path.exists()`; drops now-empty groups, saves atomically, then runs the normal add-loop. Re-running heals stale entries from any source.
**Reads:** `~/.claude/settings.json`.
**Writes:** `~/.claude/settings.json` (atomic via temp + `os.replace()`; up to two saves per run — one after sweep if stale entries found, one after add-loop if new entries installed).
**Called by:** User manually (`python3 src/menubar/hook_setup.py` from Monitor_CC root). Never imported.
**Calls out:** stdlib only (`json`, `os`, `pathlib`, `sys`).

**Usage:** `python3 src/menubar/hook_setup.py` — run once after clone or when hooks need reinstalling. Re-run any time to heal stale hook entries. Restart CC to activate.

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

hotkey.py      → ctypes only
panel.py       → AppKit, Foundation, itertools
queue_panel.py → AppKit, Foundation; .panel (constants + helpers); .queue (load_queue, save_queue)
system.py      → fcntl, os, subprocess, sys; .ghostty, .paths (PID_FILE)
                 lazy(.app) inside run() only
queue.py       → json, os, subprocess; .paths (QUEUE_FILE, QUEUE_LOCK, GHOSTTY_CWD_UUID_FILE)
app.py         → rumps, objc, AppKit, Foundation, time, threading, json, os, sys
                 .panel, .bead_panel, .queue_panel, .hotkey, .system, .discover,
                 .bg_timer, .paths (SETTINGS_FILE), .queue
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
| `CCMenuBarApp._abort_btns_by_project` | panel.py | `Dict[str, NSButton]` | panel.py (`_rebuild_panel`) | Per-project abort button references. `{}` when no CC sleep timers running. Checked by `_tick` to detect set-change (`new_abort_projs != set(_abort_btns_by_project)`). |
| `CCMenuBarApp._abort_project_for_tag` | app.py | `Dict[int, str]` | panel.py (`_rebuild_panel`) | Maps NSButton integer tag → project_name for `abortBgTimer_` dispatch. Tags start at 1000 (above session row tags 1..N). |
| `CCMenuBarApp._toggle_btn` | panel.py | `NSButton` | panel.py (`_make_nspanel`) | Auto-Jump toggle button in fixed top_bar. Created by `_make_nspanel()`; target/action wired in lazy-init tick; title updated by `_rebuild_panel` and `toggleAutoJump_`. |
| `CCMenuBarApp._panel` | panel.py | `NSPanel` | panel.py (`_make_nspanel`) | The sticky dropdown panel. Created in `__init__`. Resized by `_resize_panel`. |
| `CCMenuBarApp._panel_sv` | panel.py | `NSStackView` | panel.py (`_make_nspanel`) | Vertical NSStackView filling content area. Arranged subviews rebuilt on each `_rebuild_panel`. |
| `CCMenuBarApp._panel_quit_btn` | app.py | `NSButton` | panel.py creates, app.py wires | Restart button in fixed footer (right). Target/action wired in lazy-init tick. |
| `CCMenuBarApp._panel_kill_btn` | app.py | `NSButton` | panel.py creates, app.py wires | Kill button in fixed footer (left of Restart, 8pt gap). Wired to `killApp_` in lazy-init tick. |
| `CCMenuBarApp._panel_controller` | app.py | `_PanelController` | app.py | Single PyObjC NSObject as ObjC target for all button actions. Held to prevent ARC GC. |
| `CCMenuBarApp._auto_focus` | app.py | `bool` | app.py | Whether auto-focus is enabled. Loaded from settings; toggled by `toggleAutoJump_`. |
| `CCMenuBarApp._panel_width` | app.py | `int` | app.py owns, panel.py uses | Current panel width in pts. Loaded from settings (fallback: `PANEL_WIDTH=380`). Reset to `PANEL_WIDTH` on user-initiated fresh open via `togglePanel_` (runtime only, no save). Updated by `windowDidResize_` on user drag. Cycling (`_deferred_close_open`) preserves current value. |
| `CCMenuBarApp._panel_min_height` | app.py | `int` | app.py owns, panel.py uses | Height floor for panel. Reset to `PANEL_HEIGHT` on user-initiated fresh open via `togglePanel_` (runtime only, no save). `_rebuild_panel` sizes to `max(_panel_min_height, required_h)`. Updated by `windowDidResize_` on user drag. Cycling preserves current value. |
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
| `_ghostty_cwd_uuid_last` | ghostty.py | `dict` | module | Previous write state for `ghostty_cwd_uuid.json` change-detection (skip write if unchanged). |
| `CCMenuBarApp._queue_open` | app.py | `bool` | app.py | True while queue NSPanel is visible. |
| `CCMenuBarApp._queue_panel` | queue_panel.py | `NSPanel` | `_make_queue_nspanel` | The standalone queue panel. Created in `__init__`. Resized by `_resize_queue_panel`. |
| `CCMenuBarApp._queue_sv` | queue_panel.py | `NSStackView` | `_make_queue_nspanel` | Vertical NSStackView for queue panel content. |
| `CCMenuBarApp._queue_toggle_btn` | queue_panel.py | `NSButton` | `_make_queue_nspanel` | Auto-Jump toggle button in queue panel top_bar. Wired to `toggleAutoJump_` in lazy-init tick. |
| `CCMenuBarApp._queue_displayed_names` | app.py | `set` | queue_panel.py (`_rebuild_queue_panel`) | Set of main session names currently displayed in queue panel. Used by `_tick` to detect session-set changes. |
| `CCMenuBarApp._last_sessions` | app.py | `list` | app.py (`_tick`) | Last `list_alive_sessions()` result. Updated each tick. Used by queue panel rebuild in controller methods. |
| `CCMenuBarApp._queue_data` | app.py | `dict` | app.py | `{session_id: [{text: str, state: "draft"\|"queued"\|"sent", sent_at: str\|null}]}` refreshed from `msg_queue.json` on every tick and on `_open_queue_panel`. |
| `CCMenuBarApp._pending_queue_tags` | app.py | `dict` | queue_panel.py (`_rebuild_queue_panel`) | `{NSTextField_tag → (session_id, idx)}`. Reset on each rebuild. Used by `commitQueueField_` and `controlTextDidEndEditing_` to locate the draft entry to update. |
| `CCMenuBarApp._queue_add_tags` | app.py | `dict` | queue_panel.py (`_rebuild_queue_panel`) | `{+ button tag → session_id}`. Tags 2000+. Reset on each rebuild. |
| `CCMenuBarApp._queue_remove_tags` | app.py | `dict` | queue_panel.py (`_rebuild_queue_panel`) | `{× button tag → (session_id, idx)}`. Tags 3000+. Reset on each rebuild. |
| `CCMenuBarApp._queue_toggle_tags` | app.py | `dict` | queue_panel.py (`_rebuild_queue_panel`) | `{↑/↓ button tag → (session_id, idx)}`. Tags 5000+. Reset on each rebuild. Used by `toggleQueueEntry_`. Only draft and queued entries have a toggle button; sent entries have none. |

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

- **Session status detection** (Workers + Mains): Priority-1/2/3 fallback chain with threshold values — see `decisions/menubar_session_status.md` for full IST chain.
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
- **Dynamic panel height (grow-only)** (`panel.py`): `_rebuild_panel` calls `_compute_required_height` → `_resize_panel(app, max(app._panel_min_height, required_h))`. Panel never shrinks below user-set floor. `NSBoxSeparator` containers require explicit `heightAnchor().constraintEqualToConstant_(18.0)` — plain `NSView` has no `intrinsicContentSize`. NSGridView additionally turns off TAMIC on ALL content views (via `addRowWithViews_`), so any `NSView` placed in a grid cell MUST carry a `heightAnchor` AND `widthAnchor` constraint; without height: `height=0`, `yPlacement=top` pins origin to row top, subviews bleed up; without width: AutoLayout assigns `w=0`, merged-cell content is invisible. `_make_separator_view` (panel.py) sets only `heightAnchor`. `_make_expand_view` (bead_panel.py) sets both: `heightAnchor = total`, `widthAnchor = panel_width` (non-scroll path) or `widthAnchor = sv.contentView().widthAnchor()` (NSScrollView path).
- **Cursor handling on panel edges** (`panel.py`): `_PanelContentView(NSView)` uses NSTrackingArea + `mouseMoved_` for edge detection; `_set_hovered_edge` calls `invalidateCursorRectsForView_` on state change; `resetCursorRects` installs a single full-bounds rect for the current edge state (state-driven, winit pattern). `_CursorlessLabel(NSTextField)` and `_CursorlessButton(NSButton)` suppress child-view `resetCursorRects` to prevent override of edge cursors. Note: `LSUIElement=1` accessory-app context blocks cursor-rect dispatch in practice (cursor change not visible to user); implementation is mechanically correct but AppKit dispatch is suppressed — see `decisions/OldThemes/menubar_overhaul_2026-05-19.md` Iteration 9.
- **Status-change is panel-no-op**: working↔idle transitions NEVER trigger `_rebuild_panel` or `_resize_panel`. Open panel: status changes go through `_update_panel_inplace`. Closed panel: only trigger `_blink`. Only two events trigger `_rebuild_panel`: (1) session-set change; (2) abort-button None↔Some transition (panel open only). Queue panel has no in-place update path — any change triggers full `_rebuild_queue_panel`.
- **Three-panel cycling** (`app.py`): Sessions → Beads → Queue → Sessions (Cmd+→); reverse (Cmd+←). Each `_open_*_panel` registers BOTH Cmd+→ and Cmd+←; each `_close_*_panel` unregisters both. Generic `_deferred_close_open(app, from, to)` handles all 6 transition combinations dispatched via `NSOperationQueue.mainQueue()`. `unregister_cmd_arrow_*(None)` is a no-op — safe when opposite direction was not registered.
- **NSTextField in nonactivating panel** (`queue_panel.py`, `panel.py`): `NSWindowStyleMaskNonactivatingPanel` prevents the *app* from activating (Ghostty stays frontmost). However the default NSPanel implementation also returns `canBecomeKeyWindow=False` for this mask — this silently prevents `makeFirstResponder_` from routing keyboard events to NSTextField. Fix: `_KeyablePanel(NSPanel)` in `panel.py` overrides `canBecomeKeyWindow` to return True; all three panels use `_KeyablePanel.alloc()`. `makeKeyAndOrderFront_(None)` + `makeFirstResponder_(tf)` in `_rebuild_queue_panel` then correctly grants keyboard focus to the input field without stealing app activation.
- **NSPanel ObjC attribute constraint**: NSPanel (and all PyObjC-bridged ObjC objects) reject arbitrary Python attribute assignment — `panel.my_attr = x` raises `AttributeError`. `_make_nspanel()` returns `(panel, stack, quit_btn)` as a Python tuple.
- **NSStackView gravity**: requires BOTH `addView_inGravity_(view, 1)` AND `setDistribution_(-1)` (`NSStackViewDistributionGravityAreas`). `setDistribution_(0)` ignores gravity entirely. Enum values: `GravityTop=1`, `GravityCenter=2`, `GravityBottom=3`; `DistGravityAreas=-1`, `DistFill=0`.
- **Badge column alignment**: main-session rows only — `[*]`/`[ ]` fixed 3 chars; `[B M:SS]` variable 3–9 chars but nothing follows it, so no misalignment. Worker rows carry no badge column.
- **Settings backwards-compat** (`app.py:_load_settings`): reads `panel_min_height` first, falls back to legacy `panel_max_height`, then `PANEL_HEIGHT=460`. Old files migrate transparently.
- **Auto-abort task-file write is global** (`bg_timer.py:_abort_bg_sleep_timers`): after killing sleep PIDs, writes `aborted\n` to ALL 0-byte `*.output` task files under `_TASKS_BASE`, not just those belonging to the aborted project. Pre-existing behavior shared with manual abort. If project B has live 0-byte task files when project A is auto-aborted, B's `[B]` badge may transiently disappear. In practice rare (requires simultaneous multi-project bg tasks).
- **Per-project abort button (Option B):** abort button is embedded inline in the project's separator row via `_make_separator_view(project_name, pw, proj_min_remaining)`. Returns `(NSView, Optional[NSButton])`. Zero height cost — no extra `_ROW_H` row. Button styled in `systemRedColor` Menlo font, static label `abort`. Target/action wired in `_rebuild_panel`; label is static so no per-tick update. Tag range: 1000+ (above session row tags starting at 1).
- **Ancestry-chain walk** (`bg_timer.py:_scan_bg_sleep_timers`): attribution now walks up to 5 levels from the zsh's parent to find a CC process in `_cc_proc_cache`, instead of a single `gppid = parent[0]` lookup. Handles intermediate shell layers between CC and the zsh (e.g., `CC → sh → zsh → sleep`). Does NOT fix PID-recycling cross-project attribution (narrow timing window; deferred).
- **`_aggregate_bg` removed from `app.py` import:** `_tick` now passes `bg_by_project` directly to panel functions. Session row badge countdown (`min_remaining`) is computed inside panel functions from `bg_by_project.values()`. Manual `abortBgTimer_` uses `_scan_bg_sleep_timers` directly scoped to the clicked project.
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
