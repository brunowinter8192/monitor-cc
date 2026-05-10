# src/menubar/

## Role

Standalone macOS status-bar (menubar) application that shows all currently-running Claude Code sessions on this Mac with their working/idle status and background-task badge. Independent of the tmux TUI — launched via `workflow.py --mode menubar` or launchd. macOS only (rumps/AppKit).

## Public Interface

`from src.menubar.menubar import run` — `run()` is the sole entry point. Called by `workflow.py --mode menubar`.

## Flow

1. `run()` → sets `LSUIElement=1` env → instantiates `CCMenuBarApp` → `app.run()` starts AppKit runloop.
2. `CCMenuBarApp._tick()` fires every 1.5s → `list_alive_sessions()` → rebuild menu, blink on change.
3. `list_alive_sessions()` → refreshes CC-process cache (ps/lsof, every 10s) → scans `~/.claude/projects/*/` → picks newest JSONL per project → for workers checks tmux session existence; for mains applies 1h alive window → determines working/idle status per session type → checks `/tmp/claude-<uid>/` for in-progress tasks.

## Modules

### menubar.py (127 LOC)

**Purpose:** `CCMenuBarApp` rumps subclass + timer + blink logic + `_rebuild_menu` + `_focus_session` helper + `run()` entry point.
**Reads:** `list_alive_sessions()` result on every tick.
**Writes:** `app.title` (icon), `app.menu` (dropdown items).
**Called by:** `workflow.py` (`--mode menubar` route).
**Calls out:** `rumps`, `AppKit` (NSAttributedString/NSFont/NSColor), `subprocess` (osascript for click-to-focus), `threading.Timer`.

---

### discover.py (228 LOC)

**Purpose:** Session discovery — scans JSONL files, determines working/idle/background status per session type (main vs worker).
**Reads:** `~/.claude/projects/*/` JSONL mtimes + last lines; `/tmp/claude-<uid>/` task dirs; `ps`/`lsof` output (CC process cache); tmux session state.
**Writes:** nothing (pure read + return). Module-level cache: `_cc_proc_cache`, `_cc_proc_last_refresh`.
**Called by:** `menubar.py:CCMenuBarApp._tick`.
**Calls out:** `session_finder.get_project_directories`; `subprocess` (ps, lsof, tmux).

---

## State

- `CCMenuBarApp._last_statuses` — instance state, owned exclusively by app instance. Dict `{name: status}` for blink-on-change detection.
- `_cc_proc_cache` (discover.py) — module-level `List[(pid, tty, cwd)]` of CC processes. Rebuilt every `_PROC_REFRESH_INTERVAL=10s` via `ps -A -o pid,tty,comm` + `lsof -a -d cwd -p`.
- `_cc_proc_last_refresh` (discover.py) — float timestamp of last cache rebuild.

## Activity Detection (per session type)

**Workers** (tmux sessions):
- Alive iff `tmux has-session -t =worker-{project_basename}-{worker_name}` returns 0. Exact-match `=` prefix prevents prefix-matching false positives.
- Session name reconstructed from worker JSONL cwd: split on `/.claude/worktrees/`, `basename(left)` = project basename.
- Status: `tmux display-message -p '#{window_activity}'` → unix timestamp; `working` if age ≤ 10s.
- Fallback (cwd unreadable): `ALIVE_WINDOW_SECS=3600` JSONL age check + 10s mtime threshold.

**Mains** (Ghostty terminals):
- Alive if JSONL mtime within `ALIVE_WINDOW_SECS=3600` (1h).
- Status: CC process TTY mtime via `os.stat('/dev/{tty}').st_mtime`; `working` if age ≤ 3s.
- TTY lookup: `_cc_proc_cache` maps `cwd → tty`. Cache rebuilt every 10s.
- Fallback (no CC process for cwd): JSONL mtime ≤ 10s = working.

## Gotchas

- `app.menu = [...]` clears the entire menu including the quit button. `_rebuild_menu` always re-appends `app._quit_button` explicitly.
- Background task detection: `/tmp/claude-<uid>/` uses the numeric Unix UID (`os.getuid()`). `*.output` files with `st_size == 0` = in-progress; `done\n` (5 bytes) = completed.
- `LSUIElement=1` must be set before `app.run()` to suppress the Dock icon. Set in `run()` via `os.environ.setdefault`.
- Launched via launchd: `KeepAlive=true` auto-restarts on crash. Logs → `/tmp/monitor_cc_menubar.{log,err}`.
- **Ghostty AppleScript**: Ghostty.sdef (`/Applications/Ghostty.app/Contents/Resources/Ghostty.sdef`) exposes `working directory` and `id` per `terminal` class, but NOT `tty` or `pid`. Click-to-focus uses `focus (first terminal whose working directory is "{cwd}")` + `activate`. If Ghostty is not running, the osascript call times out silently — no crash.
- **tmux exact-match**: `tmux has-session -t name` uses prefix matching; `=name` enforces exact match. `display-message -t name` works correctly once the session is confirmed to exist (no `=` needed there — exact match preferred before prefix by tmux's resolution order).
- **Badge column alignment**: ASCII badges `[*]/[ ]/[B]` are strictly fixed-width in Menlo. Both mains (prefix `● `) and workers (prefix `  `) use a 2-char prefix → badge column always at position 25.
