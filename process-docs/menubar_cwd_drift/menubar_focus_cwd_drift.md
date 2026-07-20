# Menubar Focus — cwd Drift Bug (2026-05-27)

## Symptom

Cmd+digit hotkeys (Cmd+1..9) don't trigger a focus jump for some main sessions. Concretely observed: Cmd+1 (Monitor_CC) and Cmd+4 (searxng) jump immediately to the Ghostty terminal; Cmd+2 (Reddit) and Cmd+3 (Trading) do nothing visible.

Carbon-handler reception + app-callback fires are correct for ALL four sessions (visible in the new `src/logs/menubar.log` hotkey logging, commit `b840f16`).

## Evidence

**Hotkey log (src/logs/menubar.log):**
- Every press generates `[hotkey] cmd+N` (Carbon layer) + `[hotkey] cmd+N → focus <cwd>` (app layer)
- cwd values for [1] and [4]: project root (`/Users/.../Monitor_CC`, `/Users/.../searxng`) → focus works
- cwd values for [2] and [3]: deep subdirs (`/Users/.../Reddit/dev/subreddit_discovery/08_layer4_top5_per_sub_reports`, `/Users/.../Trading/concepts/phase_b_signal_exploration/ai/plots/01_signal_exploration`) → focus runs into nothing

**Focus log (`/tmp/monitor_cc_menubar_focus.log`):**
- [1]/[4]: `OK id=<UUID>` — Path A in `_focus_session()` (Ghostty UUID lookup) succeeded
- [2]/[3]: `OK cwd=<deep-subdir>` — Path A returns None, falls back to Path B (AppleScript `focus first terminal whose working directory is "<cwd>"`); Path B's `try/on error/end try` silently swallows the no-match and returns rc=0 — hence a false "OK"

**JSONL inspection (Trading session):**
- The most recent entries (`type=assistant`, `type=system`) all contain the same `cwd` field with the DEEP subdirectory
- CC writes the current working directory into every message line at the time of the entry
- As soon as the user runs Bash `cd <subdir>` in the CC session, the `cwd` field "drifts" in subsequent JSONL lines

## Root Cause

`_cwd_from_jsonl()` (`src/menubar/discover.py` L63) reads the last 10 JSONL entries and returns the last populated `cwd` field. That is the "current position" of the session — semantically the value for "where is the session working now", but NOT the terminal's launch cwd.

`_cc_proc_cache` keyed by claude PID, value `(tty, proc_cwd)`. `proc_cwd` is the running OS process cwd, which does NOT change during the session (the user's `cd` runs in a Bash subprocess, then exits). Meaning: proc_cwd = launch cwd = stable.

The Ghostty terminal-UUID lookup in `_tty_for_cwd()` (`src/menubar/ghostty.py` L120) does an EXACT match between the passed cwd and proc_cwd. Passed cwd = JSONL cwd (drifted). proc_cwd = launch cwd. The mismatch is structural for any session where the user has ever `cd`'d.

## Launch-Pattern Invariant

The user starts all main sessions via `./src/claude_proxy_start.sh --project <ROOT>`. The script:
- `cd "$PROJECT"` before the `claude` invocation (L238)
- guarantees CC process cwd = PROJECT root
- CC's encoded JSONL dir = encode(launch_cwd) per CC's path encoding (`/`, `_`, `.` → `-`)

Meaning: for every main session we can reconstruct the mapping `encoded_dir → launch_cwd` by iterating `_cc_proc_cache` — computing `encode(proc_cwd)` for every PID and comparing it to encoded_dir → a match gives the canonical launch cwd.

**Further invariants (user-confirmed):**
- Never 2 main sessions in the same project
- Never 2 main sessions on the same desktop
- Workers by definition always live in `.claude/worktrees/<name>` subdirs → their own encoded_dirs, no conflict with the main mapping

## Fix Decision (pending dispatch)

**Primary — discover.py `_process_project_dir()` main branch:**
- After the `is_worker == False` branch: set `SessionInfo.cwd` not via `_cwd_from_jsonl()` but via a new helper `_proc_cwd_for_encoded_dir(encoded_dir, cc_proc_cache)`
- The helper iterates `_cc_proc_cache`, encodes each `proc_cwd`, compares it to `encoded_dir`, returns the match
- Fallback on no match (stale process, race): the existing `_cwd_from_jsonl()` behavior

**Hardening — system.py `_focus_session()` Path B:**
- Rework the AppleScript `try/on error number errnum from ... end try` block so no-match errors are detected and propagated
- On a miss: focus-log entry `MISS cwd=<...> reason=no-terminal-with-this-pwd` instead of a false `OK`

## Consequences

- The display name (`os.path.basename(SessionInfo.cwd)`) stops drifting → [3] shows `Trading` in the menubar again instead of `01_signal_exploration`
- Hook-writer queue delivery (also a consumer of `get_ghostty_terminal_id`) benefits transparently — the bug likely produced undiscovered edge cases there too
- Workers stay unchanged: their JSONL cwd in practice doesn't drift outside the worktree paths, and `_worker_tmux_session()` (`src/menubar/discover.py` L109) partitions on `/.claude/worktrees/` and stays robust as a result

## Phase B — Implementation (2026-05-27)

### What Was Implemented

**Fix 1 — `src/menubar/discover.py`:**
- Added `encode_project_path` to the top-level import from `..session_finder`
- New helper `_proc_cwd_for_encoded_dir(encoded_dir)`: iterates `_cc_proc_cache`, calls `encode_project_path(proc_cwd)` per entry, returns `proc_cwd` on a match, `None` if no running CC process matches
- `_process_project_dir()` main branch: replaced `cwd = _cwd_from_jsonl(jsonl)` with `cwd = _proc_cwd_for_encoded_dir(encoded_dir) or _cwd_from_jsonl(jsonl)`
- Workers unchanged (the is_worker branch stays on JSONL cwd)

**Fix 2 — `src/menubar/system.py`:**
- Path B AppleScript: added `return "MATCH"` on success + `on error errMsg number errNum → return "MISS:" & errNum & ":" & errMsg` instead of a silent `end try`
- Result parsing: `out.startswith('MISS:')` → logs `MISS {label} reason={...}`; `r.returncode != 0` → logs `ERR`; else `OK`
- Path A unchanged (no try/on error, no MATCH token) — `elif out.startswith('MISS:')` only hits Path B

**Fix 3 — `src/menubar/discover.py` main-branch exit detection (2026-05-28):**
- `_proc_cwd_for_encoded_dir()` was originally used only as a cwd resolver (proc_cwd preferred over JSONL cwd). Now it doubles as an exit-detection signal: a `None` return means no live CC process → `return None` immediately.
- Eliminates the up-to-1h visibility window for exited main sessions that existed when only the JSONL-stale check was present.
- The JSONL-stale check (`now - mtime > ALIVE_WINDOW_SECS`) remains as a safety net; in the normal flow, the proc check catches exits first (within the next tick, ~1.5s).
- The `_cwd_from_jsonl(jsonl)` fallback removed from the main branch — redundant once the proc check gates entry.

**Import smoke test:**
```
./venv/bin/python -c "from src.menubar.discover import _proc_cwd_for_encoded_dir; print('OK')"
# → OK
```

### Verification (user-side after a menubar restart)

```bash
launchctl kickstart -k gui/$(id -u)/com.brunowinter.monitor_cc_menubar
```

1. Open the menubar → `[2]` should read `Reddit`, `[3]` should read `Trading` (instead of the subdir names)
2. Press Cmd+2 → the Reddit terminal should focus
3. Press Cmd+3 → the Trading terminal should focus
4. `tail src/logs/menubar.log` after a press → the cwd in `[hotkey] cmd+N → focus <cwd>` should be the project root, not a subdir
5. `/tmp/monitor_cc_menubar_focus.log` → Path A entries (`OK id=<UUID>`) for all mains in the proc cache; Path B entries only in the edge case (stale process), then `MISS` instead of a false `OK`

## Sources

- `src/menubar/discover.py:_cwd_from_jsonl`, `_process_project_dir`, `_classify_encoded_dir`
- `src/menubar/ghostty.py:_tty_for_cwd`, `get_ghostty_terminal_id`
- `src/menubar/system.py:_focus_session`
- `src/menubar/proc_cache.py` (`_cc_proc_cache` structure)
- `src/claude_proxy_start.sh` (launch-pattern guarantee)
- `src/logs/menubar.log` (hotkey + abort live data)
- `/tmp/monitor_cc_menubar_focus.log` (focus attempts)
