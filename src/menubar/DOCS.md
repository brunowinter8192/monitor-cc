# src/menubar/

## Role
Standalone macOS status-bar (menubar) application that shows every currently-running Claude Code
session on the machine, with working/idle status and a background-task badge. Independent of the
tmux TUI — launched via `workflow.py --mode menubar` or by launchd running the installed py2app
bundle. macOS-only (rumps/AppKit/Carbon/CoreGraphics Services). Touch this directory for anything
about the menubar UI, session discovery/status detection, Ghostty click-to-focus routing, global
hotkeys, or the RAG/Models side panels. Do not touch it for the tmux TUI, the proxy, or the
CLI-shared session-scanning primitives (`session_finder.py`, `tmux_launcher.py` at the project
root) — this package only consumes those.

## Public Interface
`run` — sole entry point; sets up the singleton lock and starts the AppKit runloop. Called by
`workflow.py --mode menubar` and, via `menubar_main.py`, by the py2app native launcher.

## Flow
1. `system.py:run()` sets `LSUIElement=1`, acquires the singleton lock (`paths.py:PID_FILE`),
   constructs `CCMenuBarApp` (`app.py`), starts the AppKit runloop.
2. `discovery_worker.py` runs `discover.py:list_alive_sessions()` + `bg_timer.py:_scan_bg_sleep_timers()`
   on a background daemon thread every ~1.5s and publishes a `DiscoverySnapshot`; the main thread
   only reads the latest snapshot via `sessions_controller.py` — no discovery I/O on the main thread.
3. `app.py:_tick` (main thread, 1.5s timer) ticks `rag_controller.py` (status label) and
   `launch_controller.py` (occupied-desktop refresh while the Launch tab is open), then delegates panel rendering to `panel_manager.py`
   (full rebuild only on session-set or abort-button change, otherwise an in-place dot/badge update).
4. A click on a session routes through `system.py:_focus_session`/`_focus_worker` (Ghostty AppleScript
   focus via `ghostty.py`'s tty→UUID map) or `_open_or_focus_monitor` (per-project tmux monitor
   launch via `tmux_launcher.py`).

## Modules

### panel.py (318 LOC)

**Purpose:** NSPanel/NSView/NSButton/NSTextField factory helpers, cursor-tracking view subclasses, and pure layout-computation helpers for the main sessions panel.
**Reads:** function parameters only (sessions, bg_by_project, panel_width passed by callers).
**Writes:** NSPanel frame (`_reposition_panel`); constructs NSView/NSButton/NSTextField UI objects returned to callers.
**Called by:** `panel_lifecycle.py`, `panel_manager.py`, `rag_controller.py`, `model_controller.py`, `model_panel_ui.py`.
**Calls out:** `AppKit`, `Foundation`, `itertools`, `objc`; `.menubar_log` (`log_menubar`); `.panel_dims` (`PANEL_*`).

---

### panel_dims.py (7 LOC)

**Purpose:** Main-panel outer dimension constants (`PANEL_WIDTH`/`PANEL_HEIGHT`/`PANEL_MIN_WIDTH`/`PANEL_MIN_HEIGHT`/`PANEL_GAP`).
**Called by:** `panel.py`, `app.py`, `app_settings.py`, `model_panel_ui.py`, `rag_controller.py`.
**Calls out:** nothing (leaf node).

---

### panel_grid.py (8 LOC)

**Purpose:** NSGridView column-width constants for the main sessions panel's 6-column layout.
**Called by:** `panel_manager.py`.
**Calls out:** nothing (leaf node).

---

### bar_icons.py (5 LOC)

**Purpose:** Menubar status-item icon glyph constants (normal/blink) and baseline offset.
**Called by:** `app.py`.
**Calls out:** nothing (leaf node).

---

### panel_manager.py (221 LOC)

**Purpose:** Per-concern controller owning the main sessions panel's NSPanel/lookup state and the full-rebuild / in-place-update rendering logic.
**Reads:** `app.settings.panel_width`/`.panel_min_height`; `sessions` and `bg_by_project` from callers.
**Writes:** `self._lookups` (a fresh `_PanelLookups` per rebuild — `cwd_map`, `worker_tag_map`, `desktop_to_cwd`, abort maps, `displayed_items`); `self._widgets.panel` frame.
**Called by:** `app.py` (construction, `_tick`, all `_PanelController` click handlers), `panel_lifecycle.py` (open/close/background/cycle).
**Calls out:** `AppKit`, `Foundation`, `itertools.groupby`, `collections.Counter`; `.panel` (factories + non-cluster constants); `.panel_grid` (`_GRID_*` constants); `.panel_tabs` (`tab_header_text`).

---

### rag_controller.py (166 LOC)

**Purpose:** Per-concern controller for the RAG status side panel — reads the RAG indexing lock file and renders a single status label.
**Reads:** `~/.rag-locks/rag.lock`; `app.settings.panel_width`/`.panel_min_height`.
**Writes:** `self._rag_status_label` text (in-place, every tick); `self._rag_panel` frame.
**Called by:** `app.py` (construction, `_tick`, resize), `panel_lifecycle.py` (open/close/cycle).
**Calls out:** `AppKit`, `Foundation`, `json`, `os`, `errno`, `datetime`, `pathlib`; `.panel` (constants + helpers); `.panel_dims` (`PANEL_*`); `.panel_tabs` (`tab_header_text`).

---

### model_controller.py (219 LOC)

**Purpose:** Per-concern controller for the Models side panel — main/worker model plus effort plus max_tokens plus thinking cycle rows, and the Apply action.
**Reads:** `MODEL_SELECTION_FILE`, `PROXY_RULES_FILE` (via `model_selection.py`, on open and after each cycle click); `app.settings.panel_width`/`.panel_min_height`.
**Writes:** `MODEL_SELECTION_FILE`, `PROXY_RULES_FILE` (atomic, only on an explicit Apply click); `self._pending`'s 8 fields (in-memory, on cycle clicks); `self._models_panel` frame.
**Called by:** `app.py` (construction, all cycle/apply `_PanelController` delegates, resize), `panel_lifecycle.py` (open/close/cycle).
**Calls out:** `AppKit`, `Foundation`, `sys`, `threading`; `.panel` (constants + `_make_line_separator`); `.model_selection` (`_PendingSelection`, `_thinking_is_enabled`); `.model_panel_ui` (factories + `_APPLY_*` constants); `.panel_tabs` (`tab_header_text`).

---

### model_selection.py (162 LOC)

**Purpose:** Pure file-I/O persistence for model/effort/max_tokens/thinking selection — cycle-value tuples, a custom `proxy_rules.json` serializer, and the `_PendingSelection` state object.
**Reads:** `MODEL_SELECTION_FILE`, `PROXY_RULES_FILE` (`path=` parameters, defaulting to the real files).
**Writes:** `MODEL_SELECTION_FILE`, `PROXY_RULES_FILE` (atomic tempfile + `os.replace`, only via `_write_model_selection`/`_write_proxy_rules_model_params`).
**Called by:** `model_controller.py` (`_PendingSelection`, sole import); `dev/model_selector/verify_model_cycle_and_io.py`; `dev/menubar/model_controller_byte_identity.py` (dynamic import).
**Calls out:** `json`, `os`; `.paths` (`MODEL_SELECTION_FILE`, `PROXY_RULES_FILE`).

---

### model_panel_ui.py (76 LOC)

**Purpose:** NSPanel/NSButton construction factories for the Models panel.
**Reads:** nothing — pure AppKit object factories.
**Writes:** nothing — returns constructed NSPanel/NSStackView/NSButton objects to callers.
**Called by:** `model_controller.py`, `panel_lifecycle.py`.
**Calls out:** `AppKit`, `Foundation`; `.panel_dims` (`PANEL_*`); `.panel` (`_TOP_BAR_H`, `_ROW_H`, `_CursorlessButton`, `_KeyablePanel`).

---

### paths.py (53 LOC)

**Purpose:** Single source of truth for on-disk path constants (per-machine app-support dir and cross-repo shared-rules dir) plus one-time legacy-location migration.
**Reads:** old dotfile/bundle-id locations under `~` (migration, first import only); `PROJECT_ROOT` env var (`MONITOR_CC_ROOT`).
**Writes:** creates `_APP_SUPPORT` dir; moves legacy runtime files to their new paths on first import (idempotent — new wins, no clobber).
**Called by:** `app.py` (`SETTINGS_FILE`), `proc_cache.py` (`HOOKS_FILE`), `system.py` (`PID_FILE`, `MONITOR_CC_ROOT`), `session_launch.py` (`MONITOR_CC_ROOT`), `ghostty.py` (`_APP_SUPPORT`), `model_selection.py` (`MODEL_SELECTION_FILE`, `PROXY_RULES_FILE`), `monitor_sweep_scheduler.py` (`MONITOR_SWEEP_STATE_FILE`, `MONITOR_CC_ROOT`), `menubar_log.py` (`_APP_SUPPORT`), `app_settings.py` (`SETTINGS_FILE`).
**Calls out:** `pathlib`, `os`.

---

### app.py (317 LOC)

**Purpose:** `CCMenuBarApp` (rumps.App subclass) — owns the per-concern controllers, the `_tick` timer loop, and `_PanelController` (the NSObject target for every button/hotkey action).
**Reads:** `sessions.refresh()` + `sessions.bg_by_project` (via `SessionsController`, backed by `discovery_worker.py`'s background snapshot) every tick; `SETTINGS_FILE` on launch.
**Writes:** bar icon; `SETTINGS_FILE` (via `app_settings.py`, on resize); `menubar.log` (`[abort]`/`[tick]`/`[latency]` categories).
**Called by:** `system.py:run()` (lazy import, to break the app↔system circular import).
**Calls out:** `rumps`, `AppKit`, `Foundation`, `objc`, `subprocess`, `threading`; `.sessions_controller`, `.focus_controller`, `.rag_controller`, `.model_controller`, `.panel_manager`, `.panel`, `.bar_icons`, `.panel_dims`, `.hotkey_controller`, `.system`, `.discovery_worker`, `.monitor_sweep_scheduler`, `.bg_timer`, `.app_settings`, `.panel_lifecycle`, `.launch_controller`, `.menubar_log`.

---

### app_settings.py (31 LOC)

**Purpose:** Settings load/save for the panel-preference pair (`panel_width`, `panel_min_height`).
**Reads:** `SETTINGS_FILE`.
**Writes:** `SETTINGS_FILE` (atomic tempfile swap).
**Called by:** `app.py`.
**Calls out:** `json`, `os`; `.paths` (`SETTINGS_FILE`); `.panel_dims` (`PANEL_*` defaults/clamping).

---

### panel_lifecycle.py (139 LOC)

**Purpose:** Four-panel (Sessions/RAG/Models/Launch) open/close/background/cycle lifecycle driven by one ring order — reposition, show/hide, hotkey (re)registration.
**Reads:** `app.panel`/`.rag`/`.models`/`.launch`/`.hotkey`/`.sessions` state; `app._nsapp.nsstatusitem`.
**Writes:** NSPanel frame/order via each controller's panel ref; hotkey registration/unregistration via `app.hotkey`; `app.panel._panel_backgrounded`.
**Called by:** `app.py` (`togglePanel_`, Cmd+K, Cmd+→/← lambdas); `launch_controller.py` (`_close_launch_panel`).
**Calls out:** `sys`, `Foundation.NSOperationQueue`; `.panel` (`_reposition_panel`); `.rag_controller` (`_reposition_rag_panel`); `.model_panel_ui` (`_reposition_models_panel`); `.launch_panel_ui` (`_reposition_launch_panel`).

---

### sessions_controller.py (25 LOC)

**Purpose:** Main-thread session snapshot cache — reads the discovery worker's latest published snapshot without doing any I/O itself.
**Reads:** `discovery_worker.py:get_latest_snapshot()` (lock-protected).
**Writes:** `self._last_sessions`, `self._last_bg_by_project` on each `refresh()` call.
**Called by:** `app.py` (construction, `_tick`, abort, resize), `panel_lifecycle.py:_open_main_panel`.
**Calls out:** `.discovery_worker` (`get_latest_snapshot`).

---

### discovery_worker.py (63 LOC)

**Purpose:** Background daemon thread producing session-discovery snapshots off the main thread, self-paced at ~1.5s.
**Reads:** nothing directly — delegates to `discover.py:list_alive_sessions()` + `bg_timer.py:_scan_bg_sleep_timers()` + `bg_task_orphans.py:scan_bg_task_orphans()`.
**Writes:** module-level `_snapshot` (lock-protected); `menubar.log` (`[latency] bg_refresh`, over-threshold cycles only — `bg_task_orphans.py`'s own `[bg_orphan]` lines are written from inside that call, not here).
**Called by:** `app.py` (`start_discovery_worker`), `sessions_controller.py` (`get_latest_snapshot`).
**Calls out:** `threading`, `sys`, `time`; `.discover` (`list_alive_sessions`, `get_last_session_timings`); `.bg_timer` (`_scan_bg_sleep_timers`); `.bg_task_orphans` (`scan_bg_task_orphans`); `.menubar_log` (`log_menubar`).

---

### monitor_sweep_scheduler.py (60 LOC)

**Purpose:** At-most-once-per-24h tick-driven sweep of stale `monitor_cc_*` tmux sessions, gated by an on-disk survives-a-restart timestamp.
**Reads:** `paths.py:MONITOR_SWEEP_STATE_FILE` (lazy, once per process).
**Writes:** `MONITOR_SWEEP_STATE_FILE` (atomic); `os.environ['MONITOR_CC_ROOT']` (`setdefault` only); `menubar.log` (`monitor_sweep` category).
**Called by:** `app.py:_tick`.
**Calls out:** `json`, `os`, `threading`; `.paths` (`MONITOR_SWEEP_STATE_FILE`, `MONITOR_CC_ROOT`); `.menubar_log` (`log_menubar`); lazy `..monitor_janitor` (`sweep_workflow`).

---

### focus_controller.py (13 LOC)

**Purpose:** Per-concern controller tracking session status changes for the bar-icon blink.
**Reads:** `self._last_statuses`; `sessions` from callers.
**Writes:** `self._last_statuses`.
**Called by:** `app.py` (construction, `_tick`).
**Calls out:** nothing (leaf node).

---

### hotkey_controller.py (123 LOC)

**Purpose:** Cmd+L/Cmd+K global hotkey registration, plus `HotkeyController` — the per-concern controller for digit (Cmd+1..9) and arrow (Cmd+→/←) hotkey lifecycle.
**Reads:** nothing.
**Writes:** Carbon event handlers + hotkey registrations via CDLL; `menubar.log` (`[hotkey]`/`[latency]` on each press).
**Called by:** `app.py` (construction, `register_cmd_l`/`register_cmd_k`, `reregister_digits`), `panel_lifecycle.py` (register/unregister arrow + digit hotkeys on panel open/close).
**Calls out:** `ctypes`; `.menubar_log` (`log_menubar`); `.system` (`_focus_session`); `.hotkey_carbon` (shared plumbing); `.hotkey_digits` (`register_cmd_digits`, `unregister_hotkeys`); `.hotkey_arrows` (`register/unregister_cmd_arrow_*`).

---

### hotkey_carbon.py (65 LOC)

**Purpose:** Shared Carbon FFI plumbing (CDLL bindings, structures, constants) used by all 4 hotkey registration paths.
**Reads:** nothing.
**Writes:** nothing — read-only CDLL configuration.
**Called by:** `hotkey_controller.py`, `hotkey_digits.py`, `hotkey_arrows.py`.
**Calls out:** `ctypes` (Carbon framework CDLL); `.menubar_log` (`log_menubar`).

---

### hotkey_digits.py (69 LOC)

**Purpose:** Cmd+1..9 digit-hotkey registration — a persistent Carbon handler re-registered against the current desktop-to-cwd map on each panel open.
**Reads:** nothing.
**Writes:** Carbon hotkey registrations via CDLL; module-level `_DIGIT_CALLBACKS` dict; `menubar.log` (`[hotkey]`/`[latency]` on each matched press).
**Called by:** `hotkey_controller.py:HotkeyController.reregister_digits`/`unregister_digits`.
**Calls out:** `ctypes`; `.menubar_log` (`log_menubar`); `.hotkey_carbon` (shared plumbing).

---

### hotkey_arrows.py (80 LOC)

**Purpose:** Cmd+→/← arrow-hotkey registration — a persistent Carbon handler driving the three-panel cycling gesture.
**Reads:** nothing.
**Writes:** Carbon hotkey registrations via CDLL; module-level `_ARROW_CALLBACKS` dict; `menubar.log` (`[hotkey]`/`[latency]` on each matched press).
**Called by:** `hotkey_controller.py:HotkeyController.register/unregister_arrow_right/left`.
**Calls out:** `ctypes`; `.menubar_log` (`log_menubar`); `.hotkey_carbon` (shared plumbing).

---

### menubar_log.py (35 LOC)

**Purpose:** Unified append-only log sink for all menubar diagnostic categories, with 7-day retention cleanup.
**Reads:** `_APP_SUPPORT/menubar.log` (`cleanup_old_lines` only).
**Writes:** `_APP_SUPPORT/menubar.log` (append per call).
**Called by:** `hotkey_controller.py`, `app.py`, `bg_timer.py`, `panel.py`, `desktop_detection.py`, `system.py`, `monitor_sweep_scheduler.py`, `hotkey_carbon.py`, `hotkey_digits.py`, `hotkey_arrows.py`, `discovery_worker.py`, `launch_controller.py`, `session_launch.py`; `dev/hotkey_latency/analyze_latency.py` (reads the log file, not an import).
**Calls out:** `datetime`; `.paths` (`_APP_SUPPORT`).

---

### system.py (226 LOC)

**Purpose:** Process entry point (`run()`), singleton lock, and Ghostty click-to-focus/monitor-launch routing for main sessions, worker viewers, and per-project monitors — every successful focus AppleScript now also activates Ghostty app-wide (one combined osascript call, `focus` before `activate`, never on a failed/MISS attempt); worker-viewer focus self-heals one stale-id failure via a single reprobe-and-retry, main-session focus unchanged otherwise.
**Reads:** `PID_FILE` (lock); `get_ghostty_terminal_id(cwd)`/`get_ghostty_terminal_id_for_tty(tty)` from `ghostty.py` on click; `ps -A` output (worker-viewer tty lookup); the plist template (PATH source for `_resolve_launch_python3`); `MONITOR_CC_ROOT`; `tmux has-session` (via `tmux_launcher.py`).
**Writes:** `PID_FILE`; `/tmp/monitor-cc-menubar_focus.log` (main-session path only); `menubar.log` (`[latency]`/`[monitor]` categories — `_focus_worker`'s line now carries `status=OK`/`status=ERR rc=... stderr=...`/`status=TIMEOUT` plus `attempt=1`; on a non-OK first attempt, a `focus_worker_reprobe` line (tty, cost, fresh id or `miss`) and, if the reprobe found a fresh id, a second `focus_worker ... attempt=2` line — the reprobe path is the ONLY thing that adds cost, never runs on a first-attempt success); `.ghostty.py`'s `_ghostty_tty_to_id[tty]` (in place, via the imported `_reprobe_single_tty`, on a successful reprobe); a new Ghostty window + tmux session on monitor launch.
**Called by:** `__init__.py` (re-export), `workflow.py` (via `__init__.py:run`), `app.py` (`_focus_session`, `_focus_worker`, `_open_or_focus_monitor`), `hotkey_controller.py` (`_focus_session`), `session_launch.py` (`_launch_monitor_ghostty_native`).
**Calls out:** `fcntl`, `os`, `re`, `shlex`, `shutil`, `subprocess`, `sys`; `.ghostty` (`get_ghostty_terminal_id`, `get_ghostty_terminal_id_for_tty`, `_reprobe_single_tty`); `..tmux_launcher` (`generate_session_name`, `check_session_exists`, `kill_session`); lazy `.app` (`CCMenuBarApp`) inside `run()` only.

---

### panel_tabs.py (7 LOC)

**Purpose:** Tab names in ring order plus the single builder of the shared header text that marks the active tab.
**Called by:** `panel_manager.py`, `rag_controller.py`, `model_controller.py`, `launch_controller.py`.
**Calls out:** nothing (leaf node).

---

### launch_config.py (15 LOC)

**Purpose:** The fixed list of launchable project paths and the selectable desktop numbers, shared by the Launch controller and the launcher.
**Called by:** `launch_controller.py`, `session_launch.py`.
**Calls out:** nothing (leaf node).

---

### launch_panel_ui.py (119 LOC)

**Purpose:** NSPanel factory, reposition helper and button/row factories for the Launch tab (desktop selector row, project rows).
**Reads:** nothing — pure AppKit object factories.
**Writes:** nothing — returns constructed NSPanel/NSView/NSButton objects to callers.
**Called by:** `launch_controller.py`, `panel_lifecycle.py`.
**Calls out:** `AppKit`, `Foundation`; `.panel_dims` (`PANEL_*`); `.panel` (`_TOP_BAR_H`, `_ROW_H`, `_MENLO`, `_CursorlessButton`, `_CursorlessLabel`, `_KeyablePanel`).

---

### launch_controller.py (109 LOC)

**Purpose:** Per-concern controller for the Launch tab — desktop selection, occupied-desktop marking from session desktop numbers, and starting a launch on a background thread.
**Reads:** `app.sessions.refresh()` (main sessions' `desktop_no`); `app.settings.panel_width`/`.panel_min_height`.
**Writes:** its panel stack and header; `menubar.log` (`[launch]` category, ignored/refused clicks); closes the Launch panel on a launch click.
**Called by:** `app.py` (construction, `_tick`, `selectDesktop_`/`launchProject_` actions, resize), `panel_lifecycle.py` (open/close/cycle).
**Calls out:** `AppKit`, `Foundation`, `threading`; `.launch_config`; `.launch_panel_ui`; `.panel` (constants + `_make_line_separator`); `.panel_lifecycle` (`_close_launch_panel`); `.panel_tabs`; `.session_launch` (`launch_workflow`); `.menubar_log`.

---

### session_launch.py (51 LOC)

**Purpose:** Launch workflow — validate desktop and project, switch to the desktop, open a Ghostty window and start the main session there.
**Reads:** `MONITOR_CC_ROOT`; the launch lists from `launch_config.py`.
**Writes:** a new Ghostty window (via `system.py`); `menubar.log` (`[launch]` OK/FAILED line with stage and detail).
**Called by:** `launch_controller.py` (launch thread).
**Calls out:** `shlex`, `time`; `.launch_config`; `.menubar_log`; `.paths` (`MONITOR_CC_ROOT`); `.space_switch`; `.system` (`_launch_monitor_ghostty_native`).

---

### space_switch.py (85 LOC)

**Purpose:** Switches the active Mission Control desktop by posting the Ctrl+N hotkey through CGEventPost and waiting until the target space is active.
**Reads:** CGS active space and space map; the PostEvent permission state.
**Writes:** synthetic Ctrl+N key events to the session event tap; may raise the PostEvent permission request.
**Called by:** `session_launch.py`.
**Calls out:** `ctypes` (CoreGraphics, CoreFoundation); `.desktop_detection` (`_build_space_map`).

---

### discover.py (218 LOC)

**Purpose:** Session discovery — scans `~/.claude/projects/*/` and returns the list of live main/worker `SessionInfo`, with status, background-task flag, and (for mains) Mission Control desktop number.
**Reads:** `~/.claude/projects/*/` JSONL mtimes + last lines; delegates process/tmux/hook state to `proc_cache.py`, Ghostty mapping to `ghostty.py`, desktop numbers to `desktop_detection.py`.
**Writes:** delegates `ghostty_cwd_uuid.json` write to `ghostty.py:_write_cwd_uuid_map`; module-level `_last_timings` (per-phase durations, read via `get_last_session_timings()`).
**Called by:** `discovery_worker.py:_worker_loop` (sole caller, off the main thread); `dev/menubar_nspanel/p1_nspanel_probe.py`; `dev/menubar/discover_byte_identity.py` (dynamic import).
**Calls out:** `session_finder.get_project_directories`, `session_finder.encode_project_path`; `.proc_cache`; `.ghostty` (`_refresh_ghostty_tty_to_id`, `_write_cwd_uuid_map`, `_ghostty_tty_to_id`); `.desktop_detection` (`detect_main_desktop_numbers`).

---

### desktop_detection.py (338 LOC)

**Purpose:** Batch detection of macOS Mission Control desktop numbers for all main sessions via private CoreGraphics Services (CGS) APIs plus one AppleScript round-trip.
**Reads:** CGS APIs (`CGSCopyManagedDisplaySpaces`, `CGSCopySpacesForWindows`, `CGWindowListCopyWindowInfo`) via ctypes; `osascript` (Ghostty window name/list); `cwd_uuid_map` + `cwd_tty_map` from caller.
**Writes:** module-level caches (`_det_cache`, `_det_cache_ts`, `_det_cache_cwds`, `_last_result`, `_cwd_desktop_lkg`); `[detection]` lines to `menubar.log`.
**Called by:** `discover.py:list_alive_sessions`; `space_switch.py` (`_build_space_map`).
**Calls out:** `ctypes` (CoreGraphics + libobjc), `subprocess` (osascript); `.menubar_log` (`log_menubar`).

---

### proc_cache.py (184 LOC)

**Purpose:** Process and state caches shared by discovery — CC process pid→(tty,cwd) map, tmux session-name set, background-task open-handle snapshot (plus per-file holder pids), proxy-log mtime lookup, hook-state reader.
**Reads:** `ps -A` + `lsof -d cwd` (CC process cache); `lsof +D _TASKS_BASE -Fpn` (bg-task open-handle + holder-pid cache); `tmux list-sessions`; `tmux display-message #{window_activity}` (per-session, on demand); `_PROXY_LOG_DIR/api_requests_*.jsonl` mtimes; `HOOKS_FILE`.
**Writes:** module-level caches (`_cc_proc_cache` — lock-protected; `_tmux_state_cache`, `_bg_task_open_paths`, `_bg_task_holder_pids`, `_proxy_log_mtime_cache`, `_hook_state_cache`).
**Called by:** `discovery_worker.py:_worker_loop` (via `discover.py`, all refresh calls) — sole refresh caller; `discover.py:_process_project_dir` (query calls, same thread); `ghostty.py:_tty_for_cwd` (`cc_proc_cache_snapshot()`, cross-thread); `bg_timer.py:_scan_bg_sleep_timers` (`_cc_proc_cache` import); `bg_task_orphans.py` (`_cc_proc_cache` import, `bg_task_holder_pids_snapshot()`).
**Calls out:** `subprocess` (ps, lsof, tmux); `threading` (`_cc_proc_cache_lock`).

---

### ghostty.py (182 LOC)

**Purpose:** Ghostty terminal UUID mapping via an OSC 2 title-marker probe — maps every Ghostty child tty (main sessions and worker viewers alike) to its terminal UUID for click-to-focus; also exposes a scoped single-tty reprobe (query immediately, one retry on a miss, no fixed sleep — see Gotchas) for repairing one stale entry without a full re-scan.
**Reads:** `ps -A` (Ghostty PID + child ttys); `/dev/ttys<NNN>` (OSC 2 marker writes); `osascript` (terminal `id|||name` pairs for the batch refresh; `id of (first terminal whose name is ...)` for the scoped single-tty reprobe, up to twice per call).
**Writes:** `/dev/ttys<NNN>` (probe + cleanup); `_ghostty_tty_to_id`, `_ghostty_tty_last_refresh`, `_ghostty_cwd_uuid_last` (module state — `_reprobe_single_tty` also writes `_ghostty_tty_to_id[tty]` in place, outside the batch refresh's own throttle); `APP_SUPPORT/ghostty_cwd_uuid.json` (atomic, change-detected — via its own inline path, not `paths.py:GHOSTTY_CWD_UUID_FILE`).
**Called by:** `discover.py:list_alive_sessions` (discovery-worker thread); `system.py:_focus_session`/`_focus_worker` (main thread); `system.py:_retry_focus_worker_after_reprobe` (`_reprobe_single_tty`, main thread, only after a real Ghostty focus failure).
**Calls out:** `json`, `os`, `subprocess`, `time`; `.paths` (`_APP_SUPPORT`); `.proc_cache` (`_cc_proc_cache`, `cc_proc_cache_snapshot`).

---

### bg_timer.py (163 LOC)

**Purpose:** Orchestrator wake-up-process scanning (`worker-cli wait` plus legacy `sleep` timers), per-project attribution, and manual abort.
**Reads:** `ps -A -o pid=,ppid=,etime=,args=` (wake-up-process detection); `_cc_proc_cache` (ancestry→cwd attribution); `lsof -p <pid> -a -d 1,2 -Fn` per killed PID (own-output-file resolution).
**Writes:** `SIGTERM` to wake-up-process PIDs; `'aborted\n'` to the one resolved 0-byte `*.output` file per killed PID; `menubar.log` (`[abort]` category).
**Called by:** `discovery_worker.py:_worker_loop` (`_scan_bg_sleep_timers`, off the main thread); `app.py:_PanelController.abortBgTimer_` (`_abort_bg_sleep_timers`, main thread, manual abort); `dev/timer-loop/test_abort_stamp_scope.py`; `dev/menubar_nspanel/p1_nspanel_probe.py`.
**Calls out:** `subprocess` (ps, lsof); `datetime`; `pathlib`; `.proc_cache` (`_cc_proc_cache`); `.menubar_log` (`log_menubar`).

---

### bg_task_orphans.py (115 LOC)

**Purpose:** Detects `*.output` task-file handle holders whose ancestry chain contains no live Claude process, freshly reconfirms each one immediately before acting, and SIGTERMs the confirmed orphans — the subprocesses that poison `worker-cli wait` forever.
**Reads:** `proc_cache.py:bg_task_holder_pids_snapshot()` (file path -> holder pids); `_cc_proc_cache` (live-Claude membership test); `ps -A -o pid=,ppid=` (ancestry walk, own probe, up to 5 hops per holder); `lsof -p <pid> -Fn` per orphan candidate, immediately before any kill (fresh pid-still-holds-this-exact-file reconfirmation — the 10s-old cache alone is not trusted for a kill decision).
**Writes:** `SIGTERM` to confirmed-orphan pids; `menubar.log` (`[bg_orphan]` category — `orphan_detected` once per newly-seen orphan pid, deduped via module-level `_logged_orphan_pids`; `kill_action`/`kill_failed`/`kill_skipped` on every kill attempt, always naming pid + file).
**Called by:** `discovery_worker.py:_worker_loop` (`scan_bg_task_orphans`, off the main thread, self-throttled to once per 10s independent of the 1.5s discovery cadence).
**Calls out:** `os`, `signal`, `subprocess` (ps, lsof); `.proc_cache` (`_cc_proc_cache`, `bg_task_holder_pids_snapshot`); `.menubar_log` (`log_menubar`).

---

### hook_writer.py (65 LOC)

**Purpose:** CC hook handler (stdin JSON) writing working/idle status to `hooks.json` — `proc_cache.py`'s primary status signal.
**Reads:** stdin (CC hook JSON); `APP_SUPPORT/hooks.json` (inside flock).
**Writes:** `APP_SUPPORT/hooks.json` (atomic, inside flock).
**Called by:** CC hook system (async subprocess, `python3 src/menubar/hook_writer.py`); `dev/model_selector/verify_hook_writer_split.py` (dynamic import, test). Never imported as a package module.
**Calls out:** `fcntl`, `json`, `os`, `sys`, `time` (stdlib only).

---

### hook_setup.py (107 LOC)

**Purpose:** Idempotent installer for the activity-monitor hooks (`UserPromptSubmit`/`Stop`/`StopFailure`) in `~/.claude/settings.json`, with a worktree guard and a stale-entry sweep.
**Reads:** `~/.claude/settings.json`.
**Writes:** `~/.claude/settings.json` (atomic, up to two saves per run).
**Called by:** User manually (`python3 src/menubar/hook_setup.py` from the project root). Never imported.
**Calls out:** `json`, `os`, `pathlib`, `sys` (stdlib only).

---

### setup_menubar.py (30 LOC)

**Purpose:** Plist-writer utility for `app.py:restartApp_` — writes the LaunchAgent plist for either the dev/venv launcher or the py2app-installed bundle.
**Reads:** `src/menubar/com.brunowinter.monitor-cc-menubar.plist` (template); `PROJECT_ROOT` env var.
**Writes:** `~/Library/LaunchAgents/com.brunowinter.monitor-cc-menubar.plist`.
**Called by:** `app.py:restartApp_` (lazy import, branch-specific).
**Calls out:** `pathlib`, `os`.

---

### setup_py2app.py (200 LOC, at project root — not in src/menubar/)

**Purpose:** py2app build + install + bootstrap script producing the codesigned menubar.app bundle.
**Reads:** `src/menubar/menubar_main.py` (entry point); `src/menubar/com.brunowinter.monitor-cc-menubar.plist` (bundled data file + plist-substitution source).
**Writes:** `dist/monitor-cc-menubar.app/`; `~/Applications/monitor-cc-menubar.app/`; `~/Library/LaunchAgents/com.brunowinter.monitor-cc-menubar.plist`.
**Called by:** User manually (one-time build + after a Python upgrade).
**Calls out:** `py2app`, `setuptools`, `shutil`, `pathlib`, `os`, `subprocess`, `time`.

---

### menubar_main.py (7 LOC)

**Purpose:** py2app entry wrapper (`from src.menubar import run; run()`), kept minimal so modulegraph's import trace excludes non-menubar packages.
**Reads:** nothing.
**Writes:** nothing — delegates entirely to `system.py:run()`.
**Called by:** py2app native launcher at bundle start (`Contents/MacOS/monitor-cc-menubar`).
**Calls out:** `.system` (via `src.menubar.__init__`, which re-exports `run`).

---

## State

| Variable | Module | Owner | Description |
|---|---|---|---|
| `CCMenuBarApp.settings` | app.py | app.py | `PanelSettings` — the persisted panel-preference pair: `.panel_width`, `.panel_min_height`. Read by `panel_manager.py`, `rag_controller.py`, `model_controller.py`, `launch_controller.py`. |
| `CCMenuBarApp.panel` | app.py | panel_manager.py | `PanelManager` — owns `_panel_open`, `_panel_backgrounded`, `_initialized`, `_rebuild_in_progress`, `_lookups` (`_PanelLookups`: `displayed_items`/`cwd_map`/`worker_tag_map`/`desktop_to_cwd`/`abort_btns_by_project`/`abort_project_for_tag`), `_widgets` (`_PanelWidgets`: `panel`/`stack`/`quit_btn`/`header_btn`/`kill_btn`). |
| `CCMenuBarApp.rag` | app.py | rag_controller.py | `RagController` — owns `_rag_open`, `_rag_panel`, `_rag_sv`, `_rag_header_btn`, `_rag_status_label`. |
| `CCMenuBarApp.models` | app.py | model_controller.py | `ModelController` — owns `_models_open`, `_models_panel`, `_models_sv`, `_models_header_btn`, `_pending` (a `model_selection.py:_PendingSelection`, incl. per-side `main_thinking`/`worker_thinking`), `_buttons` (a `_ModelRowButtons`, incl. `main_thinking`/`worker_thinking` rows). |
| `CCMenuBarApp.focus` | app.py | focus_controller.py | `FocusController` — owns `_last_statuses` (blink/transition detection). |
| `CCMenuBarApp.launch` | app.py | launch_controller.py | `LaunchController` — owns `_launch_open`, `_launch_panel`, `_launch_sv`, `_launch_header_btn`, `_selected_desktop`, `_occupied`, `_desktop_btns`, `_launch_in_progress` (cleared in a `finally` on the launch thread). |
| `CCMenuBarApp.sessions` | app.py | sessions_controller.py | `SessionsController` — owns `_last_sessions`, `_last_bg_by_project`, refreshed from `discovery_worker.py`'s published snapshot. |
| `CCMenuBarApp.hotkey` | app.py | hotkey_controller.py | `HotkeyController` — owns digit/arrow GC refs plus `global_handles` (the Cmd-L/Cmd-K `(cb, ref, cb, ref)` tuple, set by `CCMenuBarApp.__init__` right after registration). |
| `_cc_proc_cache` | proc_cache.py | proc_cache.py (written only from the discovery-worker thread) | `Dict[pid, (tty, cwd)]` of live CC processes. Read cross-thread only via `cc_proc_cache_snapshot()`. |
| `_tmux_state_cache` | proc_cache.py | proc_cache.py | `set` of live tmux session names, refreshed every 3s. |
| `_hook_state_cache` | proc_cache.py | proc_cache.py | `Dict[session_id, {status, cwd, updated_ts}]`, sourced from `HOOKS_FILE`, TTL 1s. |
| `_ghostty_tty_to_id` | ghostty.py | ghostty.py (discovery-worker thread) | `Dict[tty, uuid]`, populated incrementally by the OSC 2 probe; read on the main thread via `get_ghostty_terminal_id(_for_tty)`. |
| `_DIGIT_CALLBACKS`/`_DIGIT_HANDLER_CB`/`_DIGIT_HANDLER_REF` | hotkey_digits.py | hotkey_digits.py | Cmd+1..9 dispatch table plus the persistent Carbon handler anchors — installed once, never dropped. |
| `_ARROW_CALLBACKS`/`_ARROW_HANDLER_CB`/`_ARROW_HANDLER_REF` | hotkey_arrows.py | hotkey_arrows.py | Cmd+→/← dispatch table plus the persistent Carbon handler anchors — same pattern as the digit module. |
| `_det_cache`/`_det_cache_ts`/`_det_cache_cwds`/`_last_result`/`_cwd_desktop_lkg` | desktop_detection.py | desktop_detection.py | Desktop-number result cache (`_DET_CACHE_TTL=10s`) plus the last-known-good per-cwd desktop map used across detection failures. |

## Gotchas
- Singleton lock (`system.py:_acquire_singleton_lock`) MUST exit 0 on failure — launchd `KeepAlive=true` only respawns on non-zero exit.
- The installed menubar is a FROZEN py2app bundle (`~/Applications/monitor-cc-menubar.app`) — restarting or killing it re-launches the same bundle, it does NOT pick up edited `src/menubar/*.py`. Any code change needs `./venv/bin/python setup_py2app.py py2app` to reach production.
- `killApp_` runs `launchctl bootout`, which removes the plist from the launchd domain — `KeepAlive=true` no longer respawns until a manual `launchctl bootstrap` or login (`RunAtLoad=true`).
- `LSUIElement=1` must be set (`os.environ.setdefault`) before `app.run()`, or the Dock icon appears.
- launchd's default `PATH` lacks Homebrew — the plist's `EnvironmentVariables/PATH` must prepend `/opt/homebrew/bin` or `tmux`/`lsof` lookups in `proc_cache.py` fail silently.
- launchd runs under the `ascii` locale — every `subprocess.run(..., text=True)` call in this package must carry `encoding='utf-8', errors='replace'`, or non-ASCII CC output (emoji, umlauts) raises `UnicodeDecodeError`. Any new `text=True` call must follow the same pattern.
- Discovery runs exclusively on `discovery_worker.py`'s background thread since the module-level caches in `proc_cache.py`/`ghostty.py`/`desktop_detection.py` are single-writer. The one cross-thread read (`ghostty.py:_tty_for_cwd`, from `system.py:_focus_session` on the main thread) MUST go through `proc_cache.py:cc_proc_cache_snapshot()` — a direct `_cc_proc_cache.items()` iteration from another thread raises `RuntimeError: dictionary changed size during iteration`.
- `_refresh_ghostty_tty_to_id`'s `if not new_ttys:` early-return branch (`ghostty.py`) must still set `_ghostty_tty_last_refresh = now` before returning, or `_GHOSTTY_TTY_REFRESH_INTERVAL=10.0`'s TTL guard never re-arms and the two `ps -A` calls run on every discovery cycle instead of once per 10s.
- `_has_active_bg` (`proc_cache.py`) is handle-based (`lsof` open-write-handle check), not file-size-based — a task's `*.output` file can be non-zero within seconds of starting while the task still runs for minutes, so size alone is not a reliable liveness signal.
- `bg_timer.py:_abort_bg_sleep_timers` MUST resolve each killed PID's own `.output` file (`lsof -p <pid> -a -d 1,2 -Fn`) BEFORE sending SIGTERM — the open write handle, and `lsof`'s ability to see it, disappears the instant the process exits.
- Carbon hotkey CFUNCTYPE/handler refs (`hotkey_carbon.py`/`hotkey_digits.py`/`hotkey_arrows.py`/`hotkey_controller.py`, and `HotkeyController.global_handles`) must stay referenced for the app's lifetime — garbage collection corrupts the IMP pointer table and crashes the process (SIGSEGV/SIGABRT) on the next hotkey event.
- `desktop_detection.py`'s module-level CFUNCTYPE refs (`_FT_vv`, `_FT_vvv`, …) must likewise stay module-level for the same reason.
- Ghostty exposes no `tty`/`pid` via AppleScript — tty→UUID mapping (`ghostty.py`) and desktop detection's per-window resolution (`desktop_detection.py`) both bootstrap the mapping via an OSC 2 title-marker write plus an AppleScript name query; `_osc2_inject_match` only works when the target tab is the FOCUSED tab of its Ghostty window (background tabs don't propagate OSC-2 to `kCGSWindowTitle`).
- `desktop_detection.py` needs Screen Recording (TCC) permission for `kCGWindowName` visibility — only effective when the process keeps a stable codesign identity across rebuilds (`setup_py2app.py`'s `monitor-cc Code Signing` identity, not the ad-hoc fallback).
- `panel_manager.py`'s panel rebuild triggers on exactly two events: session-set change, or an abort-button None↔Some transition (panel open only). A bare working↔idle status flip never rebuilds — open panel updates in place, closed panel only blinks the bar icon.
- NSGridView (`panel.py`/`panel_manager.py`) disables TAMIC on every cell content view — any `NSView` placed in a grid cell needs an explicit `heightAnchor` AND `widthAnchor` constraint, or it renders at zero size / bleeds out of its row.
- `_KeyablePanel` (`panel.py`) overrides `canBecomeKeyWindow` to return `True` — `NSWindowStyleMaskNonactivatingPanel` otherwise also blocks key-window status by default, which would silently break keyboard routing to any future editable field.
- `proc_cache.py:_PROXY_LOG_DIR` is a hardcoded absolute path, not derived from `MONITOR_CC_ROOT` or an env var — breaks if the checkout moves.
- `ghostty.py` writes `ghostty_cwd_uuid.json` via its own inline path, not via `paths.py:GHOSTTY_CWD_UUID_FILE` — the constant exists for external/future consumers only, and has no reader inside this package. `paths.py:ORCHESTRATOR_SIGNALS_FILE` is in the same position: written by the iterative-dev plugin's `worker-cli send`, no reader in this package.
- `system.py:_open_or_focus_monitor` always kills an existing `monitor_cc_*` tmux session before relaunching — there is no focus-only branch, because that session commonly outlives its Ghostty window and a focus-only click would silently no-op on a closed window.
- `hook_setup.py` refuses to run from a worktree path (`_guard_not_worktree`) — hooks must be installed from the main repo checkout, or the registered command path goes dead the moment the worktree is removed.
- `proc_cache.py:_bg_task_open_paths`/`_bg_task_holder_pids` are REASSIGNED (not mutated in place) on every `_refresh_bg_task_cache` call, unlike `_cc_proc_cache` (mutated via `.update()`/`del`, same object forever). A `from .proc_cache import _bg_task_holder_pids` in another module would bind to the dict object that existed at import time and go stale after the first refresh — `bg_task_orphans.py` reads it exclusively through `bg_task_holder_pids_snapshot()` for this reason; any future module needing that cache must do the same, not a direct import.
- `system.py`'s three focus AppleScripts (`_focus_session`'s two routes, `_focus_terminal_by_id`
  shared by both `_focus_worker` attempts) all call app-level `activate` again as of 2026-09-20,
  AFTER the terminal-level `focus`/`focus (first terminal whose ...)` command, in the SAME
  osascript invocation — this reverses part of `process-docs/ghostty_foreground/
  cmd_n_ghostty_foreground.md` (2026-06), which removed `activate` because it brought Ghostty
  forward on every desktop. That constraint was explicitly retracted by the user
  (`process-docs/menubar_worker_focus/`, 2026-09-20) in favor of one narrower one: a Ghostty
  window must never change its own desktop. `activate` is only ever reached after a successful
  focus (inside the cwd route's `try` block, before `return "MATCH"`; naturally unreached on the
  id route if `focus terminal id` itself throws, since an unhandled AppleScript error halts the
  `tell` block before the next line). Do not reintroduce `activate` as a standalone/first
  command, and do not split it into a second `osascript` call — both were deliberately rejected
  (order matters, one round trip only).
- `ghostty.py:_reprobe_single_tty` deliberately has NO fixed sleep after writing the OSC2 marker, unlike `_refresh_ghostty_tty_to_id`'s batch path (120ms). Measured live (60 trials, `process-docs/menubar_worker_focus/`): an immediate query finds the marker ~88% of the time; on a miss, one immediate retry query found it 100% of the time (0 double-misses observed) — average total cost ~92ms vs ~210ms with the fixed sleep. This finding applies ONLY to the single-tty reprobe path, verified and changed there; `_refresh_ghostty_tty_to_id`'s own 120ms sleep was not re-measured or touched — do not assume the same conclusion carries over there without separately measuring it (different call shape: N markers written before one shared query, not one marker before an immediately-following query).
- Launch tab (`session_launch.py`/`space_switch.py`): needs the PostEvent permission for the menubar bundle. Without it the click only logs `[launch] FAILED ... postevent_not_granted` and nothing switches — there is no fallback path, by design. Grants survive rebuilds only while the bundle stays signed with the `monitor-cc Code Signing` identity. The bundle MUST be built from the main checkout: `MONITOR_CC_ROOT` comes from the plist's `PROJECT_ROOT`, which `setup_py2app.py` fills with the build directory.
- Launch tab: `launch_workflow` blocks ~1.5s (switch + 1s settle) and therefore runs on a daemon thread started by `LaunchController`; a busy flag drops clicks while it runs.
- `panel_lifecycle.py` derives ring neighbours from `_RING`; adding a tab means one entry in `_RING`, one in `panel_tabs.py:TABS`, and the panel/open/close cases.
