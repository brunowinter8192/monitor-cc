# dev/timer-loop/

## Role
Measurement and verification scripts around the background-task wake-up chain: an inventory of real completion and kill notice wordings, a dead probe for a removed proxy-side design (historical), and a guard for the menubar-side abort-scoping fix.

## Public Interface
No `__init__.py`. Entry paths: `./venv/bin/python dev/timer-loop/p1_scan_bg_completion_wordings.py [log_dir]`, `dev/timer-loop/p3_project_scope_incident_probe.py` (dead) and `python3 dev/timer-loop/test_abort_stamp_scope.py`.

## Flow
The wording scan reads the dual-log corpus and writes a findings report. The abort test drives the real menubar abort function against spawned subprocesses and asserts on file and process state as one fail-fast strand.

## Modules

### p1_scan_bg_completion_wordings.py (47 LOC)

**Purpose:** Entry script: resolves the corpus dir, drives the per-file scan loop and writes the report.
**Reads:** all `*_original.jsonl` files of the dual log (dir overridable by first argument).
**Writes:** `md/bg_completion_wordings_<date>.md`.
**Called by:** none; manual measurement.
**Calls out:** `bg_completion_scan.py`, `bg_completion_report.py`.

---

### bg_completion_scan.py (154 LOC)

**Purpose:** Corpus scanning for the wording inventory: candidate extraction, structural filters, dedup and mechanism verdicts against the real extraction code.
**Reads:** nothing directly; works on data passed in.
**Writes:** nothing; mutates finding and counter dicts passed in.
**Called by:** `p1_scan_bg_completion_wordings.py`, `bg_completion_report.py`.
**Calls out:** `src/proxy/strip_sn_notice.py`, `src/proxy/strip_bg_completed.py`, `src/proxy/payload_helpers.py`.

---

### bg_completion_report.py (274 LOC)

**Purpose:** Report building for the wording inventory, one section per concern.
**Reads:** nothing; operates on the scanner's dicts.
**Writes:** nothing; returns the report text.
**Called by:** `p1_scan_bg_completion_wordings.py`.
**Calls out:** `bg_completion_scan.py`.

---

### p3_project_scope_incident_probe.py (215 LOC)

**Purpose:** Replays a cross-project false-block incident where one project's session was blocked by another's pending background-task entry.
**Reads:** nothing persistent; seeds its own state file per case in a temp dir.
**Writes:** a report that is never reached.
**Called by:** none. Dead code: the hook and state-writer modules it imports no longer exist, so it raises before completing.
**Calls out:** nothing reachable.

---

### test_abort_stamp_scope.py (130 LOC)

**Purpose:** Integration guard for the menubar abort-stamp scoping fix: spawns two subprocesses, aborts one PID and asserts only that pair is touched.
**Reads:** nothing persistent; spawns its own subprocesses and temp dir.
**Writes:** a temp dir with fixtures and a scratch menubar log, removed at the end; `md/test_abort_stamp_scope.md`.
**Called by:** none; manual CLI.
**Calls out:** `src.menubar.bg_timer`, `src.menubar.menubar_log` (dynamic imports), the strand runner in `dev/refactoring/`.

---

## State
The scanner owns and mutates the finding and counter dicts the entry script creates and passes through scan and report; the report module only reads them. The other scripts own only per-run temp files and subprocesses.
