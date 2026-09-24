# dev/proxy_instrumentation/

## Role

Reconstructs and measures the proxy's real strip/inject pipeline output straight from recorded
dual-log payloads, through the real production code (`message_passes.py`, `rule_ops.py`,
`diff_engine.py`, `render_messages.py`) — no live proxy required. Touch when validating a
pane-render or span-computation change against real recorded data; use `dev/proxy_dual_log/`
instead for the dual-log invariant/verification suite.

## Public Interface

No `__init__.py` in this directory. Entry path: run each script directly, e.g.
`./venv/bin/python dev/proxy_instrumentation/post_restart_verification.py`.

## Flow

Each script loads one or more recorded dual-log JSONL files (a hardcoded stem, an mtime-newest
glob, or argv). It drives the real pass functions or render path over the payloads. It either
asserts an invariant (PASS/FAIL to stdout, non-zero exit on failure) or writes a findings report
to `md/`.

## Modules

### render_recorded_request.py (109 LOC)

**Purpose:** Reconstructs the pane render for one specific recorded request (by `request_id`)
straight from the on-disk dual-log, to verify a span-render fix.
**Reads:** a fixed recorded session's forwarded/stripped/injected dual-log files (hardcoded stem
and request_id) under src/logs/dual_log.
**Writes:** rendered output to stdout.
**Called by:** none — manual, one-off verification script.
**Calls out:** `src.proxy_display.forwarded_parser`, `src.proxy_display.parser`,
`src.proxy_display.render_messages`.

---

### p4_blocklist_223_probe.py (151 LOC)

**Purpose:** Verifies the CC 2.1.223 `TOOL_BLOCKLIST` extension end-to-end on the newest
main-session recording, asserting the post-strip tool set is the expected core set.
**Reads:** the newest main-session original/forwarded dual-log pair under src/logs/dual_log
(glob-driven, no hardcoded stem).
**Writes:** `md/blocklist_223_probe_report.md`.
**Called by:** none — manual, historical pin-bump verification.
**Calls out:** `proxy.tools`, `constants`, `src.proxy_display.forwarded_parser`.

---

### p5_mid_turn_user_msg_preserve_probe.py (112 LOC)

**Purpose:** Verifies the CC 2.1.223 mid-turn-user-message preserve guard in
`_apply_role_system_strip` against a recorded incident plus a noise-still-strips regression case.
**Reads:** two recorded sessions' original dual-log files under src/logs/dual_log.
**Writes:** `md/mid_turn_user_msg_preserve_probe_report.md`.
**Called by:** none — manual, historical incident-verification probe.
**Calls out:** `src.proxy.message_passes`.

---

### p6_no_flow_extra_prepend_probe.py (249 LOC)

**Purpose:** Verifies an expanded request body is exactly the request's own payload delta after
the out-of-window prepend mechanism was removed, plus a reintroduction guard.
**Reads:** two recorded sessions' forwarded/stripped/injected dual-log files under src/logs/dual_log
(overridable via argv).
**Writes:** `md/no_flow_extra_prepend_report.md`.
**Called by:** none — manual regression guard for the removed prepend mechanism.
**Calls out:** `src.proxy_display.forwarded_parser`, `src.proxy_display.parser`,
`src.proxy_display.render_messages`, `src.proxy_display.render_turn`.

---

### p7_blocklist_258_probe.py (207 LOC)

**Purpose:** Verifies the CC 2.1.258 `TOOL_BLOCKLIST` extension and the Edit/Write file-mutation
blocklist against the full live dual-log corpus.
**Reads:** all `*_original.jsonl` files present under src/logs/dual_log at run time.
**Writes:** `md/blocklist_258_probe_report.md`.
**Called by:** none — manual, historical pin-bump verification (also the standing Edit/Write
regression guard).
**Calls out:** `proxy.tools`, `proxy.payload_helpers`, `constants`.

---

### p1_measure_full_replacement_blast_radius.py (41 LOC)

**Purpose:** Entry point for the D2 blast-radius measurement — owns the corpus file list and
drives `blast_radius_engine`/`blast_radius_report` over it.
**Reads:** four recorded sessions' original dual-log files under src/logs/dual_log.
**Writes:** `md/full_replacement_blast_radius_20260729.md`.
**Called by:** none — manual, one-off measurement.
**Calls out:** `blast_radius_engine`, `blast_radius_report`.

### blast_radius_engine.py (191 LOC)

**Purpose:** Drives recorded message deltas through the real `message_passes.py` pass order and
classifies each resulting op as FULL/PARTIAL/STRUCTURAL.
**Reads:** nothing directly — `_scan_file` is handed a dual-log path by its caller.
**Writes:** nothing — returns per-op records to its caller.
**Called by:** `p1_measure_full_replacement_blast_radius.py`.
**Calls out:** `src.proxy.message_passes`, `src.proxy.message_passes_simple`,
`src.proxy.message_passes_wakeup`, `src.proxy.rule_ops`, `src.proxy.payload_helpers`,
`src.proxy.content_strip`.

### blast_radius_analysis.py (57 LOC)

**Purpose:** Trim/ratio/distribution helpers plus a real `compose_block` + `_render_span_content`
render comparison for one classified record.
**Reads:** nothing — pure functions over records passed in.
**Writes:** nothing.
**Called by:** `blast_radius_report.py`.
**Calls out:** `src.proxy.diff_engine`, `src.proxy_display.render_messages`.

### blast_radius_report.py (268 LOC)

**Purpose:** Builds the D2 markdown report, one function per section, composed by `_build_report`.
**Reads:** nothing — takes records/corpus metadata as arguments.
**Writes:** nothing — returns the report text to its caller.
**Called by:** `p1_measure_full_replacement_blast_radius.py`.
**Calls out:** `blast_radius_engine` (classification constants), `blast_radius_analysis`.

---

### p8_answering_model_probe_test.py (103 LOC)

**Purpose:** Unit-level regression guard for `response_model_probe.make_answering_model_probe`'s
SSE model-name extraction and pass-through fidelity.
**Reads:** no on-disk data — synthetic SSE byte fixtures defined in the module.
**Writes:** stdout verdict per strand; `md/p8_answering_model_probe_test.md` (fixed name). Each `_test_*` function runs as a parallel fail-fast strand via `dev/refactoring/strand_runner.py`.
**Called by:** none — manual regression guard, re-run after any `response_model_probe.py` change.
**Calls out:** `proxy.response_model_probe`.

---

### p9_response_entry_abort_survival_test.py (143 LOC)

**Purpose:** Unit-level regression guard for `addon._write_response_entry` and the
`response()`/`error()` dual-hook wiring across abort/duplicate/override scenarios.
**Reads:** no on-disk data — fake flow/response/metadata objects defined in the module.
**Writes:** stdout verdict per strand; `md/p9_response_entry_abort_survival_test.md` (fixed name). Each `_test_*` function runs as a parallel fail-fast strand via `dev/refactoring/strand_runner.py`. Temp files live in a `TemporaryDirectory` per test and are removed.
**Called by:** none — manual regression guard, re-run after any change to `addon.py`'s
`response`/`error`/`_write_response_entry`.
**Calls out:** `proxy.addon`.

---

### response_model_corpus_report.py (195 LOC)

**Purpose:** Reads every recorded `*_response.jsonl` dual-log and reports `answering_model`
coverage and header values across the corpus.
**Reads:** all `*_response.jsonl` files under the main checkout's `src/logs/dual_log` (hardcoded
`MAIN_REPO_ROOT`).
**Writes:** `md/response_model_corpus_report.md`.
**Called by:** none — manual, re-run after a proxy restart to check whether the corpus picked up
the new fields.
**Calls out:** none.

---

### p10_model_mismatch_warning_test.py (204 LOC)

**Purpose:** Unit-level regression guard for `addon._write_model_mismatch_entry`/
`_write_response_and_mismatch` covering exactly-one-sentence, dedup, and real pane rendering.
**Reads:** no on-disk data — fake flow/response/paths/identity objects and a synthetic payload
defined in the module.
**Writes:** stdout verdict per strand; `md/p10_model_mismatch_warning_test.md` (fixed name). Each `_test_*` function runs as a parallel fail-fast strand via `dev/refactoring/strand_runner.py`. Temp files live in a `TemporaryDirectory` per test and are removed.
**Called by:** none — manual regression guard, re-run after any change to `addon.py`'s
mismatch-writing or `warnings_pane`.
**Calls out:** `proxy.addon`, `proxy.logging`, `src.panes.warnings_pane`, `src.panes.warnings_render`,
`src.colors`.

---

### p11_request_identity_encoding_test.py (59 LOC)

**Purpose:** Unit-level regression guard for `addon._request_identity_encoding` — verifies it sets
and overwrites `accept-encoding: identity` on the outbound request.
**Reads:** no on-disk data — a fake flow/request/headers object defined in the module.
**Writes:** stdout verdict per strand; `md/p11_request_identity_encoding_test.md` (fixed name). Each `_test_*` function runs as a parallel fail-fast strand via `dev/refactoring/strand_runner.py`.
**Called by:** none — manual regression guard, re-run after any change to `addon.py`'s
`request()`/`_request_identity_encoding`.
**Calls out:** `proxy.addon`.

---

### post_restart_verification.py (325 LOC)

**Purpose:** The one script a zero-context agent runs after a proxy restart to check whether this
branch's proxy-side changes took real effect, never vacuously.
**Reads:** the newest session's six dual-log files (by `*_original.jsonl` mtime) under
`POST_RESTART_VERIFY_LOG_DIR` or the main checkout's `src/logs/dual_log`.
**Writes:** stdout (per-claim PASS/CONTRADICTED/MISSING DATA report);
`md/post_restart_verification_<timestamp>.md`.
**Called by:** none — manual CLI, run once per proxy restart.
**Calls out:** `proxy.strip_bg_launch_ack`, `proxy.message_passes_simple`, `proxy.inject_poread`,
`src.proxy_display.forwarded_parser`.

---

## State

No shared mutable state across modules. Each probe owns its own module-level `LOG_DIR`/
`REPORT_PATH` constants. `blast_radius_engine.py`'s `PASS_CLASS`/`FIRST_PASS_BRANCH_CLASS` are
read-only classification tables read by `blast_radius_report.py`, never mutated after import.
