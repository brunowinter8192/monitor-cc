# dev/dual_log_cli/

## Role
Regression suite plus one measurement probe for `src/dual_log_cli/`, proving msgs, reqs, search, sessions and expand rendering rules against synthetic fixtures by calling the real functions. Touch when changing `src/dual_log_cli/` behavior. Do not add fixtures requiring a live monitor root or a real Claude projects tree.

## Public Interface
No `__init__.py`. Each script is run directly, e.g. `./venv/bin/python dev/dual_log_cli/tests/test_reqs.py`.

## Flow
A test builds synthetic dicts or writes a temp forwarded-shaped file, runs the real function under test and compares against an expected value; a failing check raises so its strand aborts. The probe globs the real dual-log directory for original and stripped pairs, runs four corpus-wide measurements and writes a dated report to `md/`.
Converted suites run as parallel fail-fast strands through the strand runner in `dev/refactoring/`.

## Modules

### probe_sys_tool_original_chars.py (230 LOC)

**Purpose:** Measures whether the last original request reliably recovers an earlier request's pre-strip system and tool sizes, backing the overlay design.
**Reads:** every original and stripped log pair of the resolved dual-log directory.
**Writes:** `dev/dual_log_cli/md/probe_sys_tool_original_chars_<date>.md`.
**Called by:** none; run manually.
**Calls out:** none.

---

### tests/test_local_time.py (109 LOC)

**Purpose:** Proves the UTC-to-local timestamp conversion and every renderer and filter built on it agree, including a day-boundary case.
**Reads:** nothing external; literal ISO strings and the machine timezone.
**Writes:** stdout pass/fail per check; exits 1 on failure.
**Called by:** none; run manually.
**Calls out:** `src.dual_log_cli.discovery`, `.reader`, `.render_format`, `.usage`.

---

### tests/test_msgs_blocks.py (149 LOC)

**Purpose:** Proves msgs block sub-lines render one indented line per block under a multi-block message with correct tool labels.
**Reads:** nothing external; hand-built render inputs.
**Writes:** stdout pass/fail per check; exits 1 on failure.
**Called by:** none; run manually.
**Calls out:** `src.dual_log_cli.reader`, `.render_msgs`, `.timeline_turns`.

---

### tests/test_msgs_overlay.py (135 LOC)

**Purpose:** Proves the msgs strip/inject delta tail for untouched, single-block and multi-block lines, including the owner suffix rule.
**Reads:** nothing external; hand-built inputs and overlay fixtures.
**Writes:** stdout pass/fail per check; exits 1 on failure.
**Called by:** none; run manually.
**Calls out:** `src.dual_log_cli.render_msgs`.

---

### tests/test_msgs_req_range.py (118 LOC)

**Purpose:** Proves msgs REQ and range selection resolves to the right message span and raises on unknown or ambiguous numbers.
**Reads:** a temp forwarded-shaped file per case.
**Writes:** stdout pass/fail per check; exits 1 on failure.
**Called by:** none; run manually.
**Calls out:** `src.dual_log_cli.timeline_boundaries`, `.timeline_markers`.

---

### tests/test_msgs_sys_delta.py (171 LOC)

**Purpose:** Proves msgs system and tool delta lines tag changed and new entries, exclude the billing header and show only the owning boundary.
**Reads:** a temp forwarded-shaped file per case.
**Writes:** stdout pass/fail per check; exits 1 on failure.
**Called by:** none; run manually.
**Calls out:** `src.dual_log_cli.reader`, `.render_msgs`, `.timeline_boundaries`, `.timeline_markers`.

---

### tests/test_msgs_sys_tool_overlay.py (170 LOC)

**Purpose:** Proves the system and tool overlay tail shows original size with a measured wire figure, never derived from stripped-text length.
**Reads:** nothing external; hand-built inputs with a payload.
**Writes:** stdout pass/fail per check; exits 1 on failure.
**Called by:** none; run manually.
**Calls out:** `src.dual_log_cli.render_msgs`, `.timeline_boundaries`.

---

### tests/test_msgs_usage.py (179 LOC)

**Purpose:** Proves the prompt-cache separator renders only when a marker's flow id resolves in the usage map.
**Reads:** a fixture projects tree and a temp response-shaped file.
**Writes:** stdout pass/fail per check; exits 1 on failure.
**Called by:** none; run manually.
**Calls out:** `src.dual_log_cli.reader`, `.render_msgs`, `.usage`, `src.proxy_display.forwarded_parser`.

---

### tests/test_project_display.py (192 LOC)

**Purpose:** Proves the project-over-context rework: stem-to-project resolution, display-stem stripping, ambiguous stems and the project column.
**Reads:** a temp directory of empty stem-shaped files.
**Writes:** stdout pass/fail per check; exits 1 on failure.
**Called by:** none; run manually.
**Calls out:** `src.dual_log_cli.discovery`, `.render_expand`, `.render_sessions`, `src.proxy_display.forwarded_parser`.

---

### tests/test_reqs.py (138 LOC)

**Purpose:** Proves the fixed reqs line form across padding, re-fires, multi-session separation and empty results.
**Reads:** a temp forwarded-shaped file per case.
**Writes:** stdout pass/fail per check; exits 1 on failure.
**Called by:** none; run manually.
**Calls out:** `src.dual_log_cli.reader`, `.render_reqs`, `.timeline_boundaries`.

---

### tests/test_reqs_gap.py (165 LOC)

**Purpose:** Proves the reqs gap pairing rule, inclusive threshold and the once-only rule for a REQ bracketing two gaps.
**Reads:** a temp forwarded-shaped file per case.
**Writes:** stdout pass/fail per check; exits 1 on failure.
**Called by:** none; run manually.
**Calls out:** `src.dual_log_cli.reader`, `.render_reqs`, `.timeline_boundaries`.

---

### tests/test_reqs_merged.py (132 LOC)

**Purpose:** Proves merged mode interleaves two sessions chronologically and that a gap bridged by another session does not qualify.
**Reads:** a temp forwarded-shaped file per case.
**Writes:** stdout pass/fail per check; exits 1 on failure.
**Called by:** none; run manually.
**Calls out:** `src.dual_log_cli.reader`, `.render_reqs`, `.timeline_boundaries`.

---

### tests/test_reqs_rebuild_drop.py (172 LOC)

**Purpose:** Proves the rebuild and drop predicates, strict boundary, first-REQ exemption and same-session predecessor rule under merged mode.
**Reads:** a temp forwarded-shaped file per case.
**Writes:** stdout pass/fail per check; exits 1 on failure.
**Called by:** none; run manually.
**Calls out:** `src.dual_log_cli.reader`, `.render_reqs`, `.timeline_boundaries`.

---

### tests/test_reqs_turn_and_family.py (121 LOC)

**Purpose:** Proves turn narrowing ahead of the other filters and that family filtering selects correctly.
**Reads:** a temp forwarded-shaped file per case.
**Writes:** stdout pass/fail per check; exits 1 on failure.
**Called by:** none; run manually.
**Calls out:** `src.dual_log_cli.discovery`, `.reader`, `.render_reqs`, `.timeline_boundaries`.

---

### tests/test_search_chars.py (95 LOC)

**Purpose:** Proves search reports a block's original-payload chars instead of an occurrence count, one hit per block, with aligned columns.
**Reads:** nothing external; hand-built payloads through the real pipeline.
**Writes:** stdout pass/fail per check; exits 1 on failure.
**Called by:** none; run manually.
**Calls out:** `src.dual_log_cli.render_search`, `.search`.

---

### tests/test_sidecar_exclusion.py (138 LOC)

**Purpose:** Proves a zero-tool sidecar entry seeds no boundary, does not pollute the system/tool delta and is skipped by session counts and last-request loading.
**Reads:** temp JSONL files shaped like real dual-log streams.
**Writes:** stdout pass/fail per check; exits 1 on failure.
**Called by:** none; run manually.
**Calls out:** `src.dual_log_cli.discovery`, `.reader`, `.timeline_boundaries`.

---

### tests/test_skip_reporting.py (155 LOC)

**Purpose:** Proves the stderr reporting and narrowed-exception paths: skip dedup, unreadable inputs, malformed lines, transcript reasons and search skipping.
**Reads:** temp files and directories built in-script.
**Writes:** stdout pass/fail per check; exits 1 on failure.
**Called by:** none; run manually. Each test function runs as its own parallel strand.
**Calls out:** `src.dual_log_cli.commands`, `.diagnostics`, `.project_map`, `.reader`, `.render_reqs`, `.usage`; the strand runner in `dev/refactoring/`.

---

### tests/test_tool_name_comparison.py (159 LOC)

**Purpose:** Proves msgs name-based tool comparison ignores index shifts, tags removed, changed and new correctly and reproduces a real false positive.
**Reads:** a temp forwarded-shaped file per case.
**Writes:** stdout pass/fail per check; exits 1 on failure.
**Called by:** none; run manually.
**Calls out:** `src.dual_log_cli.render_msgs`, `.timeline_boundaries`.

---

### tests/test_turns.py (245 LOC)

**Purpose:** Proves reqs always-on turn grouping: opener classification, preview, assignment, duration bands, turn selection and separators under filters.
**Reads:** a temp forwarded-shaped file per case.
**Writes:** stdout pass/fail per check; exits 1 on failure.
**Called by:** none; run manually.
**Calls out:** `src.dual_log_cli.reader`, `.render_format`, `.render_reqs`, `.timeline_boundaries`, `.timeline_grouping`.

---

### tests/test_reqs_pane_numbering.py (55 LOC)

**Purpose:** Runner for the pane-numbering checks of reqs, msgs and expand; prints the pass count and exits 1 on failure.
**Reads:** the check functions of the three pane-numbering check modules.
**Writes:** stdout pass/fail per check; exits 1 on failure.
**Called by:** none; run manually.
**Calls out:** the three `reqs_pane_numbering_*_checks.py` modules and the fixtures module.

---

### tests/reqs_pane_numbering_fixtures.py (268 LOC)

**Purpose:** Shared raising check helper plus synthetic forwarded, transcript and response builders for the pane-numbering checks.
**Reads:** nothing external; temp files it writes and removes.
**Writes:** nothing; the helper prints a pass line or raises.
**Called by:** the runner and the three check modules.
**Calls out:** `src.dual_log_cli.numbering`, `.reader`, `.render_reqs`, `.timeline_boundaries`, `src.proxy_display.forwarded_parser`.

---

### tests/reqs_pane_numbering_basic_checks.py (150 LOC)

**Purpose:** Ten checks for continue detection, numbering, REQ listing, gap, msgs numbers, owner rule, fallback, folded creates and hidden sessions.
**Reads:** synthetic fixtures.
**Writes:** results via the shared check helper.
**Called by:** `tests/test_reqs_pane_numbering.py`.
**Calls out:** the fixtures module, `src.dual_log_cli.*`.

---

### tests/reqs_pane_numbering_ownership_checks.py (117 LOC)

**Purpose:** Six checks for message starts of creates and continues, REQ ranges, unlocated continues, separators and expand by REQ.
**Reads:** a synthetic ownership fixture.
**Writes:** results via the shared check helper.
**Called by:** `tests/test_reqs_pane_numbering.py`.
**Calls out:** the fixtures module, `src.dual_log_cli.*`.

---

### tests/reqs_pane_numbering_unmapped_checks.py (40 LOC)

**Purpose:** Three checks for unmapped REQ rows: turn placement by send time, exclusion from gap pairs, visible non-200 status.
**Reads:** a synthetic unmapped-turn fixture.
**Writes:** results via the shared check helper.
**Called by:** `tests/test_reqs_pane_numbering.py`.
**Calls out:** the fixtures module.

---

### tests/strand_abort_probe.py (79 LOC)

**Purpose:** Proves the strand behavior of any converted suite by injecting one failing strand into a temporary copy and checking abort, finished siblings and exit code.
**Reads:** the converted suite files named on the command line.
**Writes:** a temporary mutated copy next to the suite, deleted before exit; stdout verdicts.
**Called by:** none; run manually after converting a suite.
**Calls out:** the suite under test, as a subprocess.

---

## State
No shared or mutating state. Each strand is its own subprocess and each test file owns its own raising check helper.
