# dev/proxy_instrumentation/

## Role
Reconstructs and measures the proxy's real strip/inject pipeline output from recorded dual-log payloads through the real production code, without a live proxy. Touch when validating a pane-render or span change against real recorded data; use `dev/proxy_dual_log/` for the dual-log invariant suite.

## Public Interface
No `__init__.py`. Each script is run directly, e.g. `./venv/bin/python dev/proxy_instrumentation/post_restart_verification.py`.

## Flow
Each script loads recorded dual-log JSONL files (hardcoded stem, mtime-newest glob or argument), drives the real pass functions or render path over them, and either asserts an invariant (pass/fail, non-zero exit) or writes a findings report to `md/`.

## Modules

### render_recorded_request.py (109 LOC)

**Purpose:** Reconstructs the pane render for one recorded request straight from the on-disk dual log to verify a span-render fix.
**Reads:** a fixed recorded session's forwarded, stripped and injected logs.
**Writes:** rendered output to stdout.
**Called by:** none; manual one-off verification.
**Calls out:** `src.proxy_display.forwarded_parser`, `.parser`, `.render_messages`.

---

### p4_blocklist_223_probe.py (151 LOC)

**Purpose:** Verifies the CC 2.1.223 tool-blocklist extension end to end on the newest main-session recording.
**Reads:** the newest main-session original and forwarded log pair.
**Writes:** `md/blocklist_223_probe_report.md`.
**Called by:** none; historical pin-bump verification.
**Calls out:** `proxy.tools`, `constants`, `src.proxy_display.forwarded_parser`.

---

### p5_mid_turn_user_msg_preserve_probe.py (112 LOC)

**Purpose:** Verifies the CC 2.1.223 mid-turn user-message preserve guard against a recorded incident plus a noise-still-strips case.
**Reads:** two recorded sessions' original logs.
**Writes:** `md/mid_turn_user_msg_preserve_probe_report.md`.
**Called by:** none; historical incident probe.
**Calls out:** `src.proxy.message_passes`.

---

### p6_no_flow_extra_prepend_probe.py (249 LOC)

**Purpose:** Verifies an expanded request body equals the request's own payload delta after the out-of-window prepend was removed, plus a reintroduction guard.
**Reads:** two recorded sessions' forwarded, stripped and injected logs (overridable via arguments).
**Writes:** `md/no_flow_extra_prepend_report.md`.
**Called by:** none; manual regression guard.
**Calls out:** `src.proxy_display.forwarded_parser`, `.parser`, `.render_messages`, `.render_turn`.

---

### p7_blocklist_258_probe.py (207 LOC)

**Purpose:** Verifies the CC 2.1.258 tool-blocklist extension and the Edit/Write file-mutation blocklist against the full live corpus.
**Reads:** all original logs present at run time.
**Writes:** `md/blocklist_258_probe_report.md`.
**Called by:** none; historical pin-bump verification and standing Edit/Write guard.
**Calls out:** `proxy.tools`, `proxy.payload_helpers`, `constants`.

---

### p1_measure_full_replacement_blast_radius.py (41 LOC)

**Purpose:** Entry point of the full-replacement blast-radius measurement: owns the corpus list and drives the engine and report.
**Reads:** four recorded sessions' original logs.
**Writes:** `md/full_replacement_blast_radius_20260729.md`.
**Called by:** none; one-off measurement.
**Calls out:** `blast_radius_engine.py`, `blast_radius_report.py`.

---

### blast_radius_engine.py (191 LOC)

**Purpose:** Drives recorded message deltas through the real pass order and classifies each resulting op as full, partial or structural.
**Reads:** nothing directly; a log path is handed in.
**Writes:** nothing; returns per-op records.
**Called by:** `p1_measure_full_replacement_blast_radius.py`.
**Calls out:** the message-pass, rule-ops, payload-helper and content-strip modules of `src.proxy`.

---

### blast_radius_analysis.py (52 LOC)

**Purpose:** Trim, ratio and distribution helpers plus a real compose-and-render comparison for one classified record.
**Reads:** nothing; pure functions.
**Writes:** nothing.
**Called by:** `blast_radius_report.py`.
**Calls out:** `src.proxy.diff_engine`, `src.proxy_display.render_messages`.

---

### blast_radius_report.py (268 LOC)

**Purpose:** Builds the blast-radius Markdown report, one section per concern.
**Reads:** nothing; records and metadata as arguments.
**Writes:** nothing; returns the report text.
**Called by:** `p1_measure_full_replacement_blast_radius.py`.
**Calls out:** `blast_radius_engine.py`, `blast_radius_analysis.py`.

---

### p8_answering_model_probe_test.py (103 LOC)

**Purpose:** Regression guard for the answering-model probe's SSE model-name extraction and pass-through fidelity, as parallel fail-fast strands.
**Reads:** nothing on disk; synthetic SSE fixtures.
**Writes:** stdout per strand; `md/p8_answering_model_probe_test.md`.
**Called by:** none; re-run after probe changes.
**Calls out:** `proxy.response_model_probe`; the strand runner in `dev/refactoring/`.

---

### p9_response_entry_abort_survival_test.py (143 LOC)

**Purpose:** Regression guard for the response-entry writer and the response/error dual-hook wiring across abort, duplicate and override scenarios.
**Reads:** nothing on disk; fake flow objects.
**Writes:** stdout per strand; `md/p9_response_entry_abort_survival_test.md`; per-test temp dirs.
**Called by:** none; re-run after addon response or error changes.
**Calls out:** `proxy.addon`.

---

### response_model_corpus_report.py (195 LOC)

**Purpose:** Reads every recorded response log and reports answering-model coverage and header values across the corpus.
**Reads:** all `*_response.jsonl` files of the main checkout's dual log (hardcoded root).
**Writes:** `md/response_model_corpus_report.md`.
**Called by:** none; re-run after a proxy restart to see whether the corpus picked up new fields.
**Calls out:** none.

---

### p10_model_mismatch_warning_test.py (204 LOC)

**Purpose:** Regression guard for the model-mismatch entry writers: exactly one sentence, dedup and real pane rendering.
**Reads:** nothing on disk; fake flow, response and identity objects.
**Writes:** stdout per strand; `md/p10_model_mismatch_warning_test.md`; per-test temp dirs.
**Called by:** none; re-run after mismatch-writing or warnings pane changes.
**Calls out:** `proxy.addon`, `proxy.logging`, `src.panes.warnings_pane`, `.warnings_render`, `src.colors`.

---

### p11_request_identity_encoding_test.py (59 LOC)

**Purpose:** Regression guard that the request hook sets and overwrites the identity accept-encoding header on the outbound request.
**Reads:** nothing on disk; fake flow.
**Writes:** stdout per strand; `md/p11_request_identity_encoding_test.md`.
**Called by:** none; re-run after request-hook changes.
**Calls out:** `proxy.addon`.

---

### post_restart_verification.py (325 LOC)

**Purpose:** The script a zero-context agent runs after a proxy restart to check that this branch's proxy-side changes took real effect, never vacuously.
**Reads:** the newest session's six dual-log files, from a log-dir env var or the main checkout.
**Writes:** stdout per-claim report; `md/post_restart_verification_<timestamp>.md`.
**Called by:** none; manual CLI, once per proxy restart.
**Calls out:** `proxy.strip_bg_launch_ack`, `proxy.message_passes_simple`, `proxy.inject_poread`, `src.proxy_display.forwarded_parser`.

---

## State
No shared mutable state. Each probe owns its own log and report path values; the blast-radius classification tables are read-only after import.
