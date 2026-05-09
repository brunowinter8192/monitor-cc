# src/menubar/

## Role

Standalone macOS status-bar (menubar) application that shows all currently-running Claude Code sessions on this Mac with their working/idle status and background-task badge. Independent of the tmux TUI — launched via `workflow.py --mode menubar` or launchd. macOS only (rumps/AppKit).

## Public Interface

`from src.menubar.menubar import run` — `run()` is the sole entry point. Called by `workflow.py --mode menubar`.

## Flow

1. `run()` → sets `LSUIElement=1` env → instantiates `CCMenuBarApp` → `app.run()` starts AppKit runloop.
2. `CCMenuBarApp._tick()` fires every 1.5s → `list_alive_sessions()` → rebuild menu, blink on change.
3. `list_alive_sessions()` → scans `~/.claude/projects/*/` → picks newest JSONL per project → filters by 5-min alive window → reads last line for `cwd` → checks `/tmp/claude-<uid>/` for in-progress tasks.

## Modules

### menubar.py (56 LOC)

**Purpose:** `CCMenuBarApp` rumps subclass + timer + blink logic + `run()` entry point.
**Reads:** `list_alive_sessions()` result on every tick.
**Writes:** `app.title` (icon), `app.menu` (dropdown items).
**Called by:** `workflow.py` (`--mode menubar` route).
**Calls out:** `rumps`, `threading.Timer`.

---

### discover.py (73 LOC)

**Purpose:** Session discovery — scans JSONL files, determines working/idle/background status.
**Reads:** `~/.claude/projects/*/` JSONL mtimes + last lines; `/tmp/claude-<uid>/` task dirs.
**Writes:** nothing (pure read + return).
**Called by:** `menubar.py:CCMenuBarApp._tick`.
**Calls out:** `session_finder.get_project_directories`.

---

## State

No module-level mutable state. `CCMenuBarApp._last_statuses` is instance state, owned exclusively by the app instance.

## Gotchas

- `app.menu = [...]` clears the entire menu including the quit button. `_rebuild_menu` always re-appends `app._quit_button` explicitly.
- Background task detection: `/tmp/claude-<uid>/` uses the numeric Unix UID (`os.getuid()`). `*.output` files with `st_size == 0` = in-progress; `done\n` (5 bytes) = completed.
- `LSUIElement=1` must be set before `app.run()` to suppress the Dock icon. Set in `run()` via `os.environ.setdefault`.
- Launched via launchd: `KeepAlive=true` auto-restarts on crash. Logs → `/tmp/monitor_cc_menubar.{log,err}`.
