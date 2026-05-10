# src/menubar/

## Role

Standalone macOS status-bar (menubar) application that shows all currently-running Claude Code sessions on this Mac with their working/idle status and background-task badge. Independent of the tmux TUI — launched via `workflow.py --mode menubar` or launchd. macOS only (rumps/AppKit).

## Public Interface

`from src.menubar.menubar import run` — `run()` is the sole entry point. Called by `workflow.py --mode menubar`.

## Flow

1. `run()` → sets `LSUIElement=1` env → instantiates `CCMenuBarApp` → `app.run()` starts AppKit runloop.
2. `CCMenuBarApp._tick()` fires every 1.5s → `list_alive_sessions()` → rebuild menu, blink on change.
3. `list_alive_sessions()` → refreshes CC-process cache (ps/lsof, every 10s) → refreshes Ghostty TTY-to-UUID mapping (OSC 2 probe, incremental) → scans `~/.claude/projects/*/` → picks newest JSONL per project → for workers checks tmux session existence; for mains applies 1h alive window → determines working/idle status per session type → checks `/tmp/claude-<uid>/` for in-progress tasks.
4. Click on a main session → `_focus_session(cwd)` → looks up Ghostty terminal UUID from mapping cache → `focus terminal id "<UUID>"` (Path A) or cwd-match fallback (Path B).

## Modules

### menubar.py (211 LOC)

**Purpose:** `CCMenuBarApp` rumps subclass + timer + blink logic + `_rebuild_menu` + `_focus_session` + `_register_hotkey` + `run()` entry point.
**Reads:** `list_alive_sessions()` result on every tick; `get_ghostty_terminal_id(cwd)` on click.
**Writes:** `app.title` (icon), `app.menu` (dropdown items).
**Called by:** `workflow.py` (`--mode menubar` route).
**Calls out:** `rumps`, `AppKit` (NSAttributedString/NSFont/NSColor), `subprocess` (osascript for click-to-focus), `threading.Timer`, `ctypes` (Carbon hotkey).

---

### discover.py (334 LOC)

**Purpose:** Session discovery — scans JSONL files, determines working/idle/background status per session type (main vs worker). Provides Ghostty terminal UUID mapping for reliable click-to-focus.
**Reads:** `~/.claude/projects/*/` JSONL mtimes + last lines; `/tmp/claude-<uid>/` task dirs; `ps`/`lsof` output (CC process cache); tmux session state; `/dev/ttysXXX` device files (OSC 2 marker writes for Ghostty mapping).
**Writes:** `/dev/ttysXXX` (transient OSC 2 probe marker + empty-string cleanup). Module-level cache: `_cc_proc_cache`, `_cc_proc_last_refresh`, `_ghostty_tty_to_id`, `_ghostty_tty_last_refresh`.
**Called by:** `menubar.py:CCMenuBarApp._tick` (`list_alive_sessions`), `menubar.py:_focus_session` (`get_ghostty_terminal_id`).
**Calls out:** `session_finder.get_project_directories`; `subprocess` (ps, lsof, tmux, pgrep, osascript).

---

## State

| Variable | Module | Type | Owner | Description |
|---|---|---|---|---|
| `CCMenuBarApp._last_statuses` | menubar.py | `dict` | app instance | `{name: status}` snapshot for blink-on-change detection |
| `_cc_proc_cache` | discover.py | `List[(pid, tty, cwd)]` | module | CC processes from `ps -A` + `lsof -d cwd`. Rebuilt every 10s. |
| `_cc_proc_last_refresh` | discover.py | `float` | module | Timestamp of last CC cache rebuild. |
| `_ghostty_tty_to_id` | discover.py | `Dict[str, str]` | module | tty → Ghostty terminal UUID. Populated incrementally by OSC 2 probe. |
| `_ghostty_tty_last_refresh` | discover.py | `float` | module | Timestamp of last probe cycle (updated only when a probe actually ran). |

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

## Title-Marker Mapping (tty → Ghostty terminal UUID)

**Problem:** Ghostty's AppleScript `working directory` property reflects the PTY's initial cwd, not the shell's current cwd. `focus (first terminal whose working directory is "...")` fails for sessions where the shell ran `cd X && python3 workflow.py --project Y` — Ghostty shows `X`, CC runs in `Y`. Ghostty does NOT expose `tty` or `pid` via AppleScript.

**Solution:** OSC 2 title-marker bootstrap. Each Ghostty tab has a direct child process (login shell) with a known TTY device (`/dev/ttysXXX`). Writing `\033]2;<marker>\007` to that device sets the Ghostty tab's `name` property. An AppleScript query immediately after returns `id|||name` pairs → marker appears in `name` → we learn the UUID for that TTY.

**Probe flow** (`_refresh_ghostty_tty_to_id`):

1. `pgrep -x ghostty` → Ghostty PID.
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
- **Ghostty binary name**: `pgrep` must use lowercase `ghostty` (matches `ps -o comm=` output), NOT `Ghostty` (the app display name). `pgrep -x Ghostty` returns nothing.
- **Ghostty AppleScript**: Ghostty.sdef exposes `id` (UUID, stable), `name` (current title), `working directory` per `terminal`. `focus` command takes a specifier: `focus terminal id "<UUID>"`. Does NOT expose `tty` or `pid`.
- **OSC 2 cleanup**: After the probe, `\033]2;\007` (empty-string OSC 2) written to the probed TTYs restores the shell's default title (CWD from PROMPT_COMMAND / precmd hook). Without cleanup, idle shells show `__GHT_XXXXXXXX` until next prompt display.
- **TTY ownership**: Ghostty children run as `/usr/bin/login` (root) but the `/dev/ttysXXX` device files are owned by the logged-in user → write access OK.
- **tmux exact-match**: `tmux has-session -t name` uses prefix matching; `=name` enforces exact match. `display-message -t name` works correctly once the session is confirmed to exist (no `=` needed there — exact match preferred before prefix by tmux's resolution order).
- **Badge column alignment**: ASCII badges `[*]/[ ]/[B]` are strictly fixed-width in Menlo. Both mains (prefix `● `) and workers (prefix `  `) use a 2-char prefix → badge column always at position 25.
- **Global hotkey Cmd+L**: registered in `CCMenuBarApp.__init__` via Carbon `RegisterEventHotKey` (ctypes, no pyobjc-framework-Carbon, no extra permissions). keycode 37 (`kVK_ANSI_L`), modifier `0x0100` (cmdKey). Callback fires on NSApp's CFRunLoop and calls `nsstatusitem.button().performClick_(None)` to open the dropdown. `app._hotkey_cb` and `app._hotkey_ref` are held on the instance to prevent GC of the ctypes callback.
