# dev/timer-loop/

## Role
Measurement and verification scripts around the background-task wake-up chain. `p1_` inventories
real background-task completion/kill notice wordings in the recorded corpus, independent of any one
mechanism. `p3_` is a dead probe for a now-removed proxy-side pending-background-task tracking design
(kept only as historical record — see Gotchas). `test_abort_stamp_scope.py` is a live regression guard
for the menubar-side abort-scoping fix (`src/menubar/bg_timer.py`), a separate mechanism in the same
wake-up chain.

## Flow
`p1_scan_bg_completion_wordings.py` scans the dual-log corpus for wording variety and writes a
findings report. `test_abort_stamp_scope.py` drives the real menubar abort function against real
spawned subprocesses and asserts on file/process state.

## Modules

### p1_scan_bg_completion_wordings.py (466 LOC)

**Purpose:** Inventories distinct background-task completion/kill notice wordings in the recorded
corpus, split main vs. worker session, deduplicated per session by exact raw text (robust to
non-monotonic message-count resets seen in some worker sessions), and evaluates the real
task-notification task-id extraction against each wording.
**Reads:** all `*_original.jsonl` files under src/logs/dual_log (corpus dir overridable via the first
CLI argument).
**Writes:** `md/bg_completion_wordings_<date>.md`.
**Called by:** none — manual, measurement only.
**Calls out:** `src/proxy/strip_sn_notice.py`, `src/proxy/strip_bg_completed.py`,
`src/proxy/payload_helpers.py`.

---

### p3_project_scope_incident_probe.py (243 LOC)

**Purpose:** Replays a cross-project false-block incident where one project's main session was
blocked by another project's pending background-task entry in a shared state file — was meant to
drive the real project-scoping hook end-to-end via subprocess with a seeded state file and a named
cwd.
**Reads:** nothing persistent — seeded its own state file per case under a temp directory.
**Writes:** `md/p3_project_scope_incident_probe_report.md`.
**Called by:** none — DEAD CODE. Both the hook module and the state-writer module it imports do not
exist under `src/`; the script cannot run.
**Calls out:** none reachable — its imports (a hook module and a pending-state module, both under
`src/`) do not exist; `src/proxy/addon.py` (`ProxyAddon`, `_derive_worker_context`) is still live
but unreachable since the script fails at import time.

---

### test_abort_stamp_scope.py (122 LOC)

**Purpose:** Integration regression guard for the menubar abort-stamp scoping fix
(`_abort_bg_sleep_timers`/`_resolve_pid_output_file`). Spawns two real `sleep` subprocesses with
stdout/stderr redirected to fake output files (mirrors CC's own background-launch fd shape) plus one
unrelated zero-byte file, calls the real abort function with only one PID, and asserts only that
file/process pair is touched.
**Reads:** nothing persistent — spawns its own subprocesses and temp directory.
**Writes:** a temp directory (removed in `finally`); appends to the real menubar app-support log file.
**Called by:** none — manual CLI, run via `python3 dev/timer-loop/test_abort_stamp_scope.py`.
**Calls out:** `src.menubar.bg_timer` (`_abort_bg_sleep_timers`, dynamic import), `src.menubar.paths`
(dynamic import); spawns `sleep` as fixture subprocesses.

---

## Gotchas
- `p1_`'s corpus (src/logs/dual_log) is a moving target — counts are a lower bound, not final; a
  rescan can only add deduplicated occurrences, never remove them.
- `p3_project_scope_incident_probe.py` is non-functional on the current tree — the hook and
  state-writer modules it targets do not exist under `src/`. Kept in place as a record of the
  incident it replays, not as a runnable check.
