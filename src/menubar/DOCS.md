# src/menubar/

## Role

Standalone macOS status-bar application showing every running Claude Code session with working/idle status and a background-task badge. Independent of the tmux TUI; macOS-only. Touch for menubar UI, session discovery and status, Ghostty click-to-focus, global hotkeys, side panels. Not for the TUI, proxy or shared `src/` root primitives.

## Public Interface

`__init__.py` re-exports the single entry point, which sets up the singleton lock and starts the AppKit run loop. Called by `workflow.py --mode menubar` and, via `menubar_main.py`, by the py2app native launcher.

## Flow

1. `system.py` acquires the singleton lock and starts the app class in `app.py`.
2. `discovery_worker.py` runs discovery and background-timer scans on a daemon thread and publishes snapshots; the main thread only reads them via `sessions_controller.py`.
3. `app.py` ticks the per-concern controllers and delegates panel rendering to `panel_manager.py`.
4. A session click routes through `system.py` (Ghostty AppleScript focus via the tty-to-UUID map in `ghostty.py`, or per-project monitor launch via `tmux_launcher.py`).

## Modules

### panel.py (274 LOC)

**Purpose:** AppKit panel, view, button and label factories, pure layout helpers, the shared tab header and side-panel scaffolding.
**Reads:** function parameters only.
**Writes:** NSPanel frames; returns constructed UI objects.
**Called by:** `panel_lifecycle.py`, `panel_manager.py`, `rag_controller.py`, `model_controller.py`, `launch_controller.py`, `model_panel_ui.py`, `launch_panel_ui.py`, `app.py`.
**Calls out:** `AppKit`, `Foundation`.

---

### panel_views.py (148 LOC)

**Purpose:** NSView and NSPanel subclasses: edge-resize content view, cursorless label and button, keyable panel with Cmd editing shortcuts.
**Reads:** cursor-debug environment switch.
**Writes:** `menubar.log` (cursor category, debug only).
**Called by:** `panel.py`, `model_panel_ui.py`, `launch_panel_ui.py`.
**Calls out:** `AppKit`, `objc`.

---

### panel_dims.py (7 LOC)

**Purpose:** Outer dimension values of the main panel.
**Reads:** nothing; module constants only.
**Writes:** nothing.
**Called by:** `panel.py`, `app.py`, `app_settings.py`, `model_panel_ui.py`, `rag_controller.py`.
**Calls out:** none.

---

### panel_grid.py (9 LOC)

**Purpose:** Column-width values of the main sessions grid.
**Reads:** nothing; module constants only.
**Writes:** nothing.
**Called by:** `panel_manager.py`.
**Calls out:** none.

---

### bar_icons.py (5 LOC)

**Purpose:** Menubar status-item icon glyphs and baseline offset.
**Reads:** nothing; module constants only.
**Writes:** nothing.
**Called by:** `app.py`.
**Calls out:** none.

---

### panel_manager.py (212 LOC)

**Purpose:** Controller of the main sessions panel: panel state plus full-rebuild versus in-place-update rendering.
**Reads:** panel settings; sessions and background-timer data from callers.
**Writes:** its lookup state (rebuilt per full rebuild) and the panel frame.
**Called by:** `app.py`, `panel_lifecycle.py`.
**Calls out:** `AppKit`, `Foundation`.

---

### rag_controller.py (112 LOC)

**Purpose:** Controller of the RAG status side panel; renders the indexing-lock state as one status label.
**Reads:** the RAG indexing lock file; panel settings.
**Writes:** status label text every tick; panel frame.
**Called by:** `app.py`, `panel_lifecycle.py`.
**Calls out:** `AppKit`, `Foundation`.

---

### model_controller.py (183 LOC)

**Purpose:** Controller of the Models side panel: model, effort, token and thinking cycle rows plus the Apply action.
**Reads:** the model-selection and proxy-rules files on open and after each cycle click; panel settings.
**Writes:** both files (atomic) only on an explicit Apply click; its in-memory pending selection.
**Called by:** `app.py`, `panel_lifecycle.py`.
**Calls out:** `AppKit`, `Foundation`.

---

### model_selection.py (176 LOC)

**Purpose:** Pure file-I/O persistence for model, effort, token and thinking selection, including the pending-selection state object.
**Reads:** the model-selection and proxy-rules files.
**Writes:** both files (atomic temp-file replace).
**Called by:** `model_controller.py`; `dev/model_selector/verify_model_cycle_and_io.py`; `dev/menubar/model_controller_byte_identity.py`.
**Calls out:** none.

---

### model_panel_ui.py (25 LOC)

**Purpose:** Row and Apply-button factories for the Models panel.
**Reads:** nothing.
**Writes:** returns constructed UI objects.
**Called by:** `model_controller.py`.
**Calls out:** `Foundation`.

---

### paths.py (20 LOC)

**Purpose:** Single source of truth for on-disk path values (app-support directory, shared-rules files, repo root).
**Reads:** the project-root environment variable via the shared root resolver.
**Writes:** creates the app-support directory at import.
**Called by:** `app.py`, `proc_cache.py`, `system.py`, `session_launch.py`, `ghostty.py`, `model_selection.py`, `monitor_sweep_scheduler.py`, `menubar_log.py`, `app_settings.py`.
**Calls out:** none.

---

### root_report.py (14 LOC)

**Purpose:** Reporter handed (bound to the log path) to the shared `monitor_root` module by `paths.py` — appends the resolved root and its source to `menubar.log`.
**Reads:** —
**Writes:** one `[paths]` line in `menubar.log`, same line format as `log_menubar`; written directly because `menubar_log` imports `paths`, so calling `log_menubar` from the import-time resolution is a cycle.
**Called by:** `paths.py`.
**Calls out:** —

---

### app.py (351 LOC)

**Purpose:** The rumps app class: owns the per-concern controllers, the main-thread tick timer and the action target for every button and hotkey.
**Reads:** the latest discovery snapshot each tick; the settings file on launch.
**Writes:** bar icon; settings file on resize; `menubar.log`.
**Called by:** `system.py` (lazy import to break an import cycle).
**Calls out:** `rumps`, `AppKit`, `Foundation`, `objc`.

---

### app_settings.py (34 LOC)

**Purpose:** Load and save of the panel-preference pair.
**Reads:** the settings file.
**Writes:** the settings file (atomic swap).
**Called by:** `app.py`.
**Calls out:** none.

---

### panel_lifecycle.py (136 LOC)

**Purpose:** Open, close, background and cycle lifecycle of the four panels driven by one ring order, including hotkey re-registration.
**Reads:** app controller state; the status-item.
**Writes:** panel frames and order; hotkey registration; the backgrounded flag.
**Called by:** `app.py`, `launch_controller.py`.
**Calls out:** `Foundation`.

---

### sessions_controller.py (25 LOC)

**Purpose:** Main-thread cache of the discovery worker's latest snapshot; does no I/O itself.
**Reads:** the discovery worker snapshot (lock-protected).
**Writes:** its last-sessions cache.
**Called by:** `app.py`, `panel_lifecycle.py`.
**Calls out:** none.

---

### discovery_worker.py (70 LOC)

**Purpose:** Background daemon thread that produces session-discovery snapshots off the main thread, self-paced.
**Reads:** nothing directly; delegates to discovery, background-timer and orphan-scan modules.
**Writes:** the shared snapshot (lock-protected); latency lines in `menubar.log`.
**Called by:** `app.py`, `sessions_controller.py`.
**Calls out:** none.

---

### monitor_sweep_scheduler.py (70 LOC)

**Purpose:** At-most-once-per-24h tick-driven sweep of stale monitor tmux sessions, gated by an on-disk timestamp.
**Reads:** the sweep state file.
**Writes:** the state file (atomic); `menubar.log`.
**Called by:** `app.py`.
**Calls out:** none.

---

### focus_controller.py (13 LOC)

**Purpose:** Tracks session status changes for the bar-icon blink.
**Reads:** its last-status memory.
**Writes:** its last-status memory.
**Called by:** `app.py`.
**Calls out:** none.

---

### hotkey_controller.py (120 LOC)

**Purpose:** Global Cmd+L/Cmd+K hotkey registration plus the controller for digit and arrow hotkey lifecycle.
**Reads:** nothing.
**Writes:** Carbon event handlers and hotkey registrations; `menubar.log`.
**Called by:** `app.py`, `panel_lifecycle.py`.
**Calls out:** none.

---

### hotkey_carbon.py (73 LOC)

**Purpose:** Shared Carbon FFI plumbing for all hotkey registration paths.
**Reads:** nothing.
**Writes:** nothing; read-only FFI configuration.
**Called by:** `hotkey_controller.py`, `hotkey_digits.py`, `hotkey_arrows.py`.
**Calls out:** none.

---

### hotkey_digits.py (69 LOC)

**Purpose:** Cmd+1..9 hotkey registration via a persistent Carbon handler re-registered on each panel open.
**Reads:** nothing.
**Writes:** Carbon hotkey registrations; its callback table; `menubar.log`.
**Called by:** `hotkey_controller.py`.
**Calls out:** none.

---

### hotkey_arrows.py (80 LOC)

**Purpose:** Cmd+arrow hotkey registration driving the panel cycling gesture.
**Reads:** nothing.
**Writes:** Carbon hotkey registrations; its callback table; `menubar.log`.
**Called by:** `hotkey_controller.py`.
**Calls out:** none.

---

### menubar_log.py (48 LOC)

**Purpose:** Unified append-only log sink for all menubar diagnostic categories with retention cleanup.
**Reads:** `menubar.log` (cleanup only).
**Writes:** `menubar.log` (append).
**Called by:** nearly every module in this directory; `dev/hotkey_latency/analyze_latency.py` reads the log file (not an import).
**Calls out:** none.

---

### system.py (235 LOC)

**Purpose:** Process entry point, singleton lock and Ghostty click-to-focus and monitor-launch routing for sessions, workers and monitors.
**Reads:** the lock file; Ghostty terminal-id lookups; process table; the plist template; tmux session state.
**Writes:** the lock file; focus log; `menubar.log`; new Ghostty window and tmux session on monitor launch; stale-id repair in the Ghostty map.
**Called by:** `__init__.py`, `workflow.py` (via the package export), `app.py`, `hotkey_controller.py`, `session_launch.py`, `skill_insert.py`.
**Calls out:** none.

---

### panel_tabs.py (9 LOC)

**Purpose:** Tab names, ring keys and the per-tab header pieces.
**Reads:** nothing; module constants only.
**Writes:** nothing; returns the header piece list.
**Called by:** `panel.py`, `panel_lifecycle.py`, `app.py`.
**Calls out:** none.

---

### launch_config.py (15 LOC)

**Purpose:** Fixed list of launchable project paths and selectable desktop numbers.
**Reads:** nothing; module constants only.
**Writes:** nothing.
**Called by:** `launch_controller.py`, `session_launch.py`.
**Calls out:** none.

---

### launch_panel_ui.py (60 LOC)

**Purpose:** Button and row factories for the Launch tab.
**Reads:** nothing.
**Writes:** returns constructed UI objects.
**Called by:** `launch_controller.py`.
**Calls out:** `AppKit`, `Foundation`.

---

### launch_controller.py (96 LOC)

**Purpose:** Controller of the Launch tab: desktop selection, the event-post access request and starting a launch on a background thread.
**Reads:** the current sessions' desktop numbers; panel settings.
**Writes:** its panel; `menubar.log`; closes the panel on launch.
**Called by:** `app.py`, `panel_lifecycle.py`.
**Calls out:** `AppKit`, `Foundation`.

---

### session_launch.py (51 LOC)

**Purpose:** Launch workflow: validate desktop and project, switch desktop, open a Ghostty window and start the main session.
**Reads:** the repo root; the launch lists.
**Writes:** a new Ghostty window (via `system.py`); `menubar.log`.
**Called by:** `launch_controller.py`.
**Calls out:** none.

---

### space_switch.py (88 LOC)

**Purpose:** Switches the active Mission Control desktop by posting a synthetic hotkey and waiting until the target space is active.
**Reads:** CGS active-space state; the event-post permission state.
**Writes:** synthetic key events; the permission request.
**Called by:** `session_launch.py`, `launch_controller.py`.
**Calls out:** none.

---

### skill_discovery.py (131 LOC)

**Purpose:** Discovers the skills offered for one main session (project, personal and enabled-plugin skills).
**Reads:** Claude Code settings, plugin manifests and skill files, project and personal skill directories.
**Writes:** `menubar.log` (failure lines).
**Called by:** `skill_controller.py`.
**Calls out:** none.

---

### skill_insert.py (52 LOC)

**Purpose:** Types the skill activation text into a session's input field via Ghostty AppleScript without submitting.
**Reads:** the Ghostty tty-to-terminal map.
**Writes:** the input field of one Ghostty terminal; `menubar.log`.
**Called by:** `skill_controller.py`.
**Calls out:** `osascript` (subprocess).

---

### skill_controller.py (52 LOC)

**Purpose:** Controller of the skill dropdown: builds and pops up the menu and forwards the choice to the insert step.
**Reads:** skill discovery result on each click.
**Writes:** which row's menu is open; `menubar.log`.
**Called by:** `app.py`.
**Calls out:** `AppKit`, `Foundation`.

---

### discover.py (246 LOC)

**Purpose:** Session discovery: scans project directories and returns live main and worker sessions with status, background flag and desktop number.
**Reads:** project JSONL mtimes and last lines; delegates process, tmux and hook state to `proc_cache.py`, terminal mapping to `ghostty.py`, desktop numbers to `desktop_detection.py`.
**Writes:** per-phase timing state (module level).
**Called by:** `discovery_worker.py`; `dev/menubar_nspanel/p1_nspanel_probe.py`; `dev/menubar/discover_byte_identity.py`.
**Calls out:** none.

---

### desktop_detection.py (362 LOC)

**Purpose:** Batch detection of Mission Control desktop numbers for all main sessions via private CoreGraphics Services plus one AppleScript round-trip.
**Reads:** CGS and window-list APIs; Ghostty window names via `osascript`; maps from the caller.
**Writes:** module-level result caches; `menubar.log`.
**Called by:** `discover.py`, `space_switch.py`.
**Calls out:** `osascript` (subprocess).

---

### proc_cache.py (202 LOC)

**Purpose:** Process and state caches shared by discovery: CC processes, tmux sessions, background-task handles, proxy-log mtimes and hook state.
**Reads:** process table, `lsof`, tmux; proxy log mtimes; the hook state file.
**Writes:** module-level caches.
**Called by:** `discovery_worker.py` (via `discover.py`), `discover.py`, `ghostty.py`, `bg_timer.py`, `bg_task_orphans.py`.
**Calls out:** `ps`, `lsof`, `tmux` (subprocess).

---

### ghostty.py (223 LOC)

**Purpose:** Ghostty terminal UUID mapping via an OSC title-marker probe, plus a scoped single-tty reprobe for repairing one stale entry.
**Reads:** process table; terminal device files; `osascript` terminal id and name queries.
**Writes:** terminal device files (probe and cleanup); module-level mapping state; the cwd-to-UUID map file.
**Called by:** `discover.py`, `system.py`, `skill_insert.py`.
**Calls out:** `osascript` (subprocess).

---

### bg_timer.py (157 LOC)

**Purpose:** Scans orchestrator wake-up processes, attributes them per project and aborts them on request.
**Reads:** process table; the CC process cache; per-PID open files via `lsof`.
**Writes:** SIGTERM to wake-up processes; a marker line to the resolved task output file; `menubar.log`.
**Called by:** `discovery_worker.py`, `app.py`; `dev/timer-loop/test_abort_stamp_scope.py`; `dev/menubar_nspanel/p1_nspanel_probe.py`.
**Calls out:** `ps`, `lsof` (subprocess).

---

### bg_task_orphans.py (117 LOC)

**Purpose:** Detects task-file handle holders with no live Claude ancestor, reconfirms each and terminates the confirmed orphans.
**Reads:** the holder-pid snapshot; the CC process cache; process table; `lsof` per candidate.
**Writes:** SIGTERM to confirmed orphans; `menubar.log`.
**Called by:** `discovery_worker.py`.
**Calls out:** `ps`, `lsof` (subprocess).

---

### hook_writer.py (85 LOC)

**Purpose:** Claude Code hook handler writing working/idle status to the hook state file, the primary status signal for discovery.
**Reads:** stdin (hook JSON); the hook state file (inside a file lock).
**Writes:** the hook state file (atomic, inside a file lock).
**Called by:** Claude Code hook system (async subprocess); `dev/model_selector/verify_hook_writer_split.py`. Never imported as a package module.
**Calls out:** none.

---

### hook_setup.py (90 LOC)

**Purpose:** Idempotent installer for the activity-monitor hooks in the user settings file, with a worktree guard and stale-entry sweep.
**Reads:** the user settings file.
**Writes:** the user settings file (atomic).
**Called by:** run manually from the project root; never imported.
**Calls out:** none.

---

### setup_menubar.py (29 LOC)

**Purpose:** Plist writer for the app restart action: dev launcher or installed bundle.
**Reads:** the plist template; the repo root.
**Writes:** the LaunchAgent plist.
**Called by:** `app.py` (lazy import).
**Calls out:** none.

---

### menubar_main.py (19 LOC)

**Purpose:** py2app entry wrapper kept minimal so the bundle import trace excludes non-menubar packages.
**Reads:** nothing.
**Writes:** nothing; delegates to the package entry.
**Called by:** the py2app native launcher at bundle start.
**Calls out:** none.

---

## State

Each controller on the app object owns its own panel and UI state and is the only mutator of it; `app.py` owns the persisted panel settings. Discovery caches (process, tmux, hook state, Ghostty map, desktop numbers) are module-level, single-writer on the discovery-worker thread, and read by the main thread only through snapshot accessors. Hotkey handler references live at module level for the app's lifetime.
