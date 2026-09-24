# dev/dual_log_cli/

## Role

Regression suite plus one measurement probe for `src/dual_log_cli/`, proving msgs/reqs/search/
sessions/expand rendering rules against synthetic fixtures by calling the real functions directly.
Touch this when changing `src/dual_log_cli/` behavior. Do not add fixtures requiring a live
`MONITOR_CC_ROOT` or real `~/.claude/projects/` tree.

## Public Interface

No `__init__.py` in this directory. Entry path: run each script directly, e.g.
`./venv/bin/python dev/dual_log_cli/tests/test_reqs.py`.

## Flow

A test script builds synthetic dicts or writes a temp `_forwarded.jsonl`-shaped file, runs the real
`src.dual_log_cli` function under test, and compares the result against an expected value via a
local `check()` helper; a failure list drives the exit code. The probe instead globs the real
dual-log directory for `_original`/`_stripped` stem pairs, runs four corpus-wide measurements, and
writes a dated report to `md/`.

## Modules

### probe_sys_tool_original_chars.py (230 LOC)

**Purpose:** Measures whether the last `_original` request's own system/tools lists reliably
recover an earlier request's pre-strip size, backing the sys/tool overlay design.
**Reads:** every `*_original.jsonl`/`*_stripped.jsonl` pair under the resolved dual-log directory.
**Writes:** `dev/dual_log_cli/md/probe_sys_tool_original_chars_<date>.md`.
**Called by:** none — run manually.
**Calls out:** none.

---

### tests/test_local_time.py (106 LOC)

**Purpose:** Proves the UTC-to-local timestamp conversion and every renderer/filter built on it
agree, including a dynamically built day-boundary-crossing case.
**Reads:** nothing external — literal ISO strings plus the running machine's own timezone.
**Writes:** stdout (pass/fail per check); exits 1 on failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.discovery`, `.reader`, `.render_format`, `.usage`.

---

### tests/test_msgs_blocks.py (155 LOC)

**Purpose:** Proves `msgs`' block sub-lines render one indented line per block under a multi-block
message, unchanged single-block format, and correct tool labels.
**Reads:** nothing external — hand-built `render_msgs` input dicts.
**Writes:** stdout (pass/fail per check); exits 1 on failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.reader`, `.render_msgs`, `.timeline_turns`.

---

### tests/test_msgs_overlay.py (141 LOC)

**Purpose:** Proves `msgs`' strip/inject delta tail renders correctly for untouched, single-block
and multi-block lines, including the `by REQ n` suffix rule.
**Reads:** nothing external — hand-built `render_msgs` input dicts and overlay fixtures.
**Writes:** stdout (pass/fail per check); exits 1 on failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.render_msgs`.

---

### tests/test_msgs_req_range.py (124 LOC)

**Purpose:** Proves `msgs --req F [T]` resolves a REQ or range to the correct msg-index span and
raises on an unknown or ambiguous REQ number.
**Reads:** a temp `_forwarded.jsonl`-shaped file, written and deleted per case.
**Writes:** stdout (pass/fail per check); exits 1 on failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.timeline_boundaries`, `.timeline_markers`.

---

### tests/test_msgs_sys_delta.py (177 LOC)

**Purpose:** Proves `msgs`' sys/tool delta lines tag changed/new entries correctly, exclude the
billing header, and show only the owning re-fire boundary's lines.
**Reads:** a temp `_forwarded.jsonl`-shaped file, written and deleted per case.
**Writes:** stdout (pass/fail per check); exits 1 on failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.reader`, `.render_msgs`, `.timeline_boundaries`, `.timeline_markers`.

---

### tests/test_msgs_sys_tool_overlay.py (176 LOC)

**Purpose:** Proves the sys/tool strip-inject delta tail shows the original size with a measured
wire figure, never derived from raw stripped-text length.
**Reads:** nothing external — hand-built `render_msgs` input dicts with a payload added.
**Writes:** stdout (pass/fail per check); exits 1 on failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.render_msgs`, `.timeline_boundaries`.

---

### tests/test_msgs_usage.py (185 LOC)

**Purpose:** Proves the CR/CC prompt-cache separator renders only when a marker's flow_id resolves
in the usage map, built from a fixture projects tree.
**Reads:** a fixture `projects_root` tree (temp dir) and a temp `_response.jsonl`-shaped file.
**Writes:** stdout (pass/fail per check); exits 1 on failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.reader`, `.render_msgs`, `.usage`, `src.proxy_display.forwarded_parser`.

---

### tests/test_project_display.py (198 LOC)

**Purpose:** Proves the PROJECT-over-CONTEXT rework — stem-to-project resolution, display-stem
stripping, ambiguous-stem resolution, and the new PROJECT column.
**Reads:** a real temp directory of empty stem-shaped files (for `resolve_stem`).
**Writes:** stdout (pass/fail per check); exits 1 on failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.discovery`, `.render_expand`, `.render_sessions`,
`src.proxy_display.forwarded_parser`.

---

### tests/test_reqs.py (144 LOC)

**Purpose:** Proves `reqs`' fixed `REQ n HH:MM:SS CR c CC c` line form across padding, re-fires,
multi-session separation and empty results.
**Reads:** a temp `_forwarded.jsonl`-shaped file per case.
**Writes:** stdout (pass/fail per check); exits 1 on failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.reader`, `.render_reqs`, `.timeline_boundaries`.

---

### tests/test_reqs_gap.py (128 LOC)

**Purpose:** Proves `reqs --gap MINUTES`'s pairing rule, inclusive threshold, and the once-only rule
for a REQ bracketing two adjacent gaps.
**Reads:** a temp `_forwarded.jsonl`-shaped file per case.
**Writes:** stdout (pass/fail per check); exits 1 on failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.reader`, `.render_reqs`, `.timeline_boundaries`.

---

### tests/test_reqs_merged.py (120 LOC)

**Purpose:** Proves `reqs --merged` interleaves two sessions' REQs chronologically and that a gap
bridged by another session does not qualify.
**Reads:** a temp `_forwarded.jsonl`-shaped file per case.
**Writes:** stdout (pass/fail per check); exits 1 on failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.reader`, `.render_reqs`, `.timeline_boundaries`.

---

### tests/test_reqs_rebuild_drop.py (178 LOC)

**Purpose:** Proves `reqs --rebuild`/`--drop`'s predicates, strict-inequality boundary, REQ-1
exemption, and same-session predecessor rule under `--merged`.
**Reads:** a temp `_forwarded.jsonl`-shaped file per case.
**Writes:** stdout (pass/fail per check); exits 1 on failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.reader`, `.render_reqs`, `.timeline_boundaries`.

---

### tests/test_reqs_turn_and_family.py (127 LOC)

**Purpose:** Proves `reqs --turn` narrows the REQ sequence ahead of `--gap`/`--rebuild`/`--drop`,
and that `filter_by_family` selects correctly.
**Reads:** a temp `_forwarded.jsonl`-shaped file per case.
**Writes:** stdout (pass/fail per check); exits 1 on failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.discovery`, `.reader`, `.render_reqs`, `.timeline_boundaries`.

---

### tests/test_search_chars.py (101 LOC)

**Purpose:** Proves `search` reports a block's original-payload chars instead of an occurrence
count, one hit per matching block, with aligned columns.
**Reads:** nothing external — hand-built payloads run through the real pipeline.
**Writes:** stdout (pass/fail per check); exits 1 on failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.render_search`, `.search`.

---

### tests/test_sidecar_exclusion.py (144 LOC)

**Purpose:** Proves a zero-tool sidecar entry seeds no boundary, does not pollute the sys/tool
delta, and is skipped by session counts and `load_last_request`.
**Reads:** temp JSONL files shaped like the real dual-log streams, written and deleted per case.
**Writes:** stdout (pass/fail per check); exits 1 on failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.discovery`, `.reader`, `.timeline_boundaries`.

---

### tests/test_skip_reporting.py (146 LOC)

**Purpose:** Proves the stderr reporting and narrowed-exception paths: `report_skip` dedup, unreadable project-map inputs, malformed `_original` lines, `resolve_transcript` reasons, the numbering line's reason, timestamp raises, and `search` skipping only `FileNotFoundError`/`ValueError`.
**Reads:** temp files and directories built in-script.
**Writes:** stdout (pass/fail per check); exits 1 on failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.commands`, `.diagnostics`, `.project_map`, `.reader`, `.render_reqs`, `.usage`.

---

### tests/test_tool_name_comparison.py (165 LOC)

**Purpose:** Proves `msgs`' NAME-based tool comparison ignores index shifts, tags removed/changed/
new correctly, and reproduces a real REQ-196 false positive.
**Reads:** a temp `_forwarded.jsonl`-shaped file per case.
**Writes:** stdout (pass/fail per check); exits 1 on failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.render_msgs`, `.timeline_boundaries`.

---

### tests/test_turns.py (251 LOC)

**Purpose:** Proves `reqs`' always-on turn grouping — opener classification, preview selection,
turn assignment, duration bands, `--turn N`, and separator survival under filters.
**Reads:** a temp `_forwarded.jsonl`-shaped file per case.
**Writes:** stdout (pass/fail per check); exits 1 on failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.reader`, `.render_format`, `.render_reqs`, `.timeline_boundaries`,
`.timeline_grouping`.

---

### tests/test_reqs_pane_numbering.py (57 LOC)

**Purpose:** Runner for the 19 pane-numbering checks of `reqs`, `msgs` and `expand --req`; prints the pass count and exits 1 on failure.
**Reads:** the check functions of the three `reqs_pane_numbering_*_checks.py` modules.
**Writes:** stdout (pass/fail per check); exits 1 on failure.
**Called by:** none — run manually.
**Calls out:** `tests/reqs_pane_numbering_basic_checks.py`, `tests/reqs_pane_numbering_ownership_checks.py`, `tests/reqs_pane_numbering_unmapped_checks.py`, `tests/reqs_pane_numbering_fixtures.py`.

---

### tests/reqs_pane_numbering_fixtures.py (270 LOC)

**Purpose:** Shared `check()` with the `PASS_LIST`/`FAIL_LIST` state and the synthetic forwarded, transcript and response builders for the pane-numbering checks.
**Reads:** nothing external — temp files it writes and removes.
**Writes:** `PASS_LIST`, `FAIL_LIST` (module state read by the runner).
**Called by:** the runner and the three check modules.
**Calls out:** `src.dual_log_cli.numbering`, `.reader`, `.render_reqs`, `.timeline_boundaries`, `src.proxy_display.forwarded_parser`.

---

### tests/reqs_pane_numbering_basic_checks.py (150 LOC)

**Purpose:** Ten checks for continue detection, numbering, the REQ listing, `--gap`, msgs numbers, owner rule, fallback, folded creates, hidden sessions and the empty result.
**Reads:** synthetic fixtures.
**Writes:** results via `check()`.
**Called by:** `tests/test_reqs_pane_numbering.py`.
**Calls out:** `tests/reqs_pane_numbering_fixtures.py`, `src.dual_log_cli.*`.

---

### tests/reqs_pane_numbering_ownership_checks.py (117 LOC)

**Purpose:** Six checks for msg start of creates and continues, `--req` ranges, unlocated continues, continue separators and `expand --req`.
**Reads:** synthetic ownership fixture.
**Writes:** results via `check()`.
**Called by:** `tests/test_reqs_pane_numbering.py`.
**Calls out:** `tests/reqs_pane_numbering_fixtures.py`, `src.dual_log_cli.*`.

---

### tests/reqs_pane_numbering_unmapped_checks.py (40 LOC)

**Purpose:** Three checks for unmapped REQ rows — turn placement by send time, exclusion from gap pairs, visible non-200 status.
**Reads:** synthetic unmapped-turn fixture.
**Writes:** results via `check()`.
**Called by:** `tests/test_reqs_pane_numbering.py`.
**Calls out:** `tests/reqs_pane_numbering_fixtures.py`.

---

## State

No shared or mutating state across modules — each test file owns its own module-level
`PASS_LIST`/`FAIL_LIST`, populated only by its own `check()` calls during that file's own run.
