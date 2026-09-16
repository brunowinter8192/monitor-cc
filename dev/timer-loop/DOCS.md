# dev/timer-loop/

## Role
Measurement and verification scripts around the background-task wake-up chain. `p1_` inventories
real background-task completion/kill notice wordings in the recorded corpus. `p3_` is a dead probe
for a removed proxy-side design (kept as historical record). `test_abort_stamp_scope.py` guards the
menubar-side abort-scoping fix, a separate mechanism in the same chain.

## Public Interface
No `__init__.py` in this directory. Entry paths: `./venv/bin/python
dev/timer-loop/p1_scan_bg_completion_wordings.py [log_dir]`, `./venv/bin/python
dev/timer-loop/p3_project_scope_incident_probe.py` (DEAD, see below), `python3
dev/timer-loop/test_abort_stamp_scope.py`.

## Flow
`p1_scan_bg_completion_wordings.py` scans the dual-log corpus for wording variety and writes a
findings report. `test_abort_stamp_scope.py` drives the real menubar abort function against real
spawned subprocesses and asserts on file/process state.

## Modules

### p1_scan_bg_completion_wordings.py (47 LOC)

**Purpose:** Entry script — resolves the corpus dir, drives the per-file scan loop, writes the
report.
**Reads:** all `*_original.jsonl` files under src/logs/dual_log (corpus dir overridable via the
first CLI argument).
**Writes:** `md/bg_completion_wordings_<date>.md`.
**Called by:** none — manual, measurement only.
**Calls out:** `bg_completion_scan.py`, `bg_completion_report.py`.

---

### bg_completion_scan.py (154 LOC)

**Purpose:** Corpus-scanning concern for p1 — candidate-block extraction, TN/bare structural
filters, dedup, and mechanism-verdict evaluation against the real extraction code.
**Reads:** nothing directly (operates on data passed in by the caller).
**Writes:** nothing (mutates the `findings`/counter dicts passed in by the caller).
**Called by:** `p1_scan_bg_completion_wordings.py`, `bg_completion_report.py`.
**Calls out:** `src/proxy/strip_sn_notice.py`, `src/proxy/strip_bg_completed.py`,
`src/proxy/payload_helpers.py`.

---

### bg_completion_report.py (274 LOC)

**Purpose:** Report-building concern for p1 — one function per markdown section, assembled by
`_build_report`.
**Reads:** nothing (operates on the `findings`/counter dicts built by `bg_completion_scan.py`).
**Writes:** nothing (returns the report text; the entry script writes the file).
**Called by:** `p1_scan_bg_completion_wordings.py`.
**Calls out:** `bg_completion_scan.py` (`_is_canonical_timer_command`, `_mechanism_verdict`,
`EXCLUDED_FILES`).

---

### p3_project_scope_incident_probe.py (213 LOC)

**Purpose:** Replays a cross-project false-block incident where one project's main session was
blocked by another project's pending background-task entry in a shared state file.
**Reads:** nothing persistent — seeded its own state file per case under a temp directory.
**Writes:** `md/p3_project_scope_incident_probe_report.md` — never reached; see Called by.
**Called by:** none — DEAD CODE. Both the hook module and the state-writer module it imports do
not exist under `src/`; the script raises `ModuleNotFoundError` partway through and never
completes.
**Calls out:** none reachable — its imports (a hook module and a pending-state module, both under
`src/`) do not exist; `src/proxy/addon.py` (`ProxyAddon`, `_derive_worker_context`) is still live
but unreachable since the script crashes before that import executes.

---

### test_abort_stamp_scope.py (120 LOC)

**Purpose:** Integration regression guard for the menubar abort-stamp scoping fix
(`_abort_bg_sleep_timers`/`_resolve_pid_output_file`) — spawns two real subprocesses, calls the
real abort function with only one PID, and asserts only that file/process pair is touched.
**Reads:** nothing persistent — spawns its own subprocesses and temp directory.
**Writes:** a temp directory (removed in `finally`); appends to the real menubar app-support log
file.
**Called by:** none — manual CLI, run via `python3 dev/timer-loop/test_abort_stamp_scope.py`.
**Calls out:** `src.menubar.bg_timer` (`_abort_bg_sleep_timers`, dynamic import), `src.menubar.paths`
(dynamic import); spawns `sleep` as fixture subprocesses.

---

## State
`bg_completion_scan.py`'s `_scan_file` owns and mutates the `findings`/`cmd_variant_counts`/
`raw_dup_counter`/`bare_hits`/`session_is_worker` dicts that `p1_scan_bg_completion_wordings.py`
creates and passes by reference through the whole scan -> report pipeline; `bg_completion_report.py`
only reads them. `p3_project_scope_incident_probe.py` and `test_abort_stamp_scope.py` each own and
mutate only their own per-run temp files / spawned subprocesses; neither persists state across runs.
