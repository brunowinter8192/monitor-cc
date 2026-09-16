# dev/proxy_dual_log/

## Role

Verification suite for the dual-log quartet (`_original`/`_forwarded`/`_stripped`/`_injected`)
written by `src/proxy/addon.py`. Proves losslessness of the forwarded-delta log, and completeness
of the strip/inject diff engine. Touch when changing the dual-log write side, the diff engine, or
read-side badge/render logic. Do not add features beyond verification.

## Public Interface

No `__init__.py` in this directory. Entry path: run each script directly, e.g.
`./venv/bin/python dev/proxy_dual_log/attribution_coverage.py` (most scripts expect to be run
from the project root so their own `sys.path`/`from src.` setup resolves).

## Flow

A script reads one or more dual-log JSONL files (real corpus data or synthetic fixtures). It
replays the delta chain, or runs the real `src/proxy`/`src/proxy_display` functions directly, over
that data. It either asserts an invariant via `check()`/exit code, or builds Markdown report lines
and writes them to its own `*_reports/`/`md/` directory. Sibling modules (algorithm, cases,
report-building, I/O) are plain helper imports; the CLI entry point owns ORCHESTRATOR.

## Modules

### verify_delta.py (279 LOC)

**Purpose:** Reconstructs the full forwarded payload from a `_forwarded.jsonl` delta stream and
verifies element counts match the delta's declared counts.
**Reads:** an `_original.jsonl` + `_forwarded.jsonl` pair (positional or `--original`/`--forwarded`).
**Writes:** a per-request table and PASS/FAIL summary to stdout.
**Called by:** none — manual CLI, exits 1 on a hard-check failure.
**Calls out:** none at import time — parses JSONL directly.

---

### tt_delta_skip_replay.py (277 LOC)

**Purpose:** Replays an `_original.jsonl` through the real modification/delta-build/accumulator
pipeline to prove the total_tokens badge-suppression fix.
**Reads:** a dual-log stem's `_original`/`_stripped`/`_injected` triplet under the main checkout's
`src/logs/dual_log`.
**Writes:** PASS/FAIL classification report to stdout.
**Called by:** none — manual CLI, exits 1 if a class regresses.
**Calls out:** `src.proxy.rules`, `src.proxy_display.dual_log_accumulator`, `src.proxy_display.proxy_badge`.

---

### diff_strip_inject.py (251 LOC)

**Purpose:** Span-level strip/inject diff of an original vs. forwarded proxy log pair, classifying
spans as equal/stripped/injected via `difflib`.
**Reads:** an `_original.jsonl` + `_forwarded.jsonl` pair (positional or `--original`/`--forwarded`).
**Writes:** per-request diff sections with IDENTICAL/REPLACED/STRIPPED/INJECTED tags to stdout.
**Called by:** none — manual CLI.
**Calls out:** `src.proxy.diff_engine`.

---

### span_inline_probe.py (49 LOC)

**Purpose:** CLI entry point for the Form A vs Form B inline-render data model probe, comparing
them on one fixed recorded session's blocks.
**Reads:** a fixed recorded session's dual-log files (hardcoded session reference).
**Writes:** `span_inline_probe_reports/<YYYYMMDD>.md`.
**Called by:** none — manual, one-off design-validation probe.
**Calls out:** `src.proxy.diff_engine` (loaded via `importlib`); `span_inline_probe_reconstruct.py`,
`_blocks.py`, `_report.py`.

### span_inline_probe_reconstruct.py (88 LOC)

**Purpose:** JSONL loading, per-model-family forwarded-delta chain reconstruction, and
original/forwarded request matching.
**Reads:** JSONL file objects passed in by the caller.
**Writes:** nothing — pure data transforms.
**Called by:** `span_inline_probe.py`.
**Calls out:** none.

### span_inline_probe_blocks.py (108 LOC)

**Purpose:** Locates the three representative probe blocks (sys full-replace, sys strip-to-dot,
message word-level-mixed) in a matched request list.
**Reads:** matched `(orig_entry, fwd_entry, fwd_state)` tuples; takes the diff function as a
parameter.
**Writes:** nothing — returns block-description dicts.
**Called by:** `span_inline_probe.py`.
**Calls out:** none.

### span_inline_probe_report.py (370 LOC)

**Purpose:** Builds the Markdown report — per-block span sequence, inline render mock, Form A/B
analysis, storage-cost table, design-tension and recommendation sections.
**Reads:** block-description dicts from `span_inline_probe_blocks.py`.
**Writes:** returns the report as a list of lines.
**Called by:** `span_inline_probe.py`.
**Calls out:** none.

---

### main_log_elimination_probe.py (45 LOC)

**Purpose:** CLI entry point for the feasibility probe on eliminating the main proxy log in favor
of the dual-log quartet.
**Reads:** a dual-log quartet plus the corresponding main proxy log for one session.
**Writes:** `main_log_elimination_probe_reports/<date>.md`.
**Called by:** none — manual, one-off feasibility probe.
**Calls out:** `main_log_elimination_io.py`, `_questions.py`, `_report.py`.

### main_log_elimination_io.py (60 LOC)

**Purpose:** Project-root/log-path resolution, required-file existence check, and JSONL loaders.
**Reads:** `MONITOR_CC_ROOT` env var or `__file__`-relative fallback; log files on disk.
**Writes:** nothing — exits 1 via `_check_paths` if a required log is missing.
**Called by:** `main_log_elimination_probe.py`.
**Calls out:** none.

### main_log_elimination_reconstruct.py (143 LOC)

**Purpose:** Delta-chain reconstruction, cache_control-aware element normalization/comparison, and
raw_payload field classification tables.
**Reads:** nothing — pure data transforms over passed-in entries.
**Writes:** nothing.
**Called by:** `main_log_elimination_questions.py`, `_report.py`.
**Calls out:** none.

### main_log_elimination_questions.py (149 LOC)

**Purpose:** Answers whether forwarded-reconstruction matches the main-log payload, and whether
is_error tool_result extraction matches `tool_errors.jsonl`.
**Reads:** main-log entries, forwarded-delta entries, `_original` entries, tool_errors records.
**Writes:** nothing — returns result dicts.
**Called by:** `main_log_elimination_probe.py`.
**Calls out:** `main_log_elimination_reconstruct.py`.

### main_log_elimination_report.py (213 LOC)

**Purpose:** Builds the Markdown report — header, content-match/divergence/field-classification
sections, and the migration verdict.
**Reads:** the question A/B result dicts.
**Writes:** the report file; returns its path.
**Called by:** `main_log_elimination_probe.py`.
**Calls out:** `main_log_elimination_reconstruct.py`.

---

### green_overlay_probe.py (212 LOC)

**Purpose:** CLI entry point reproducing a green-overlay false-injection bug and validating a
char-level diff fix against real and synthetic cases.
**Reads:** one recorded session's dual-log files (hardcoded session reference).
**Writes:** `green_overlay_probe_reports/green_overlay_probe.md`.
**Called by:** none — manual, one-off bug-repro probe.
**Calls out:** `green_overlay_probe_diff.py`, `_cases.py`.

### green_overlay_probe_diff.py (194 LOC)

**Purpose:** The three diff variants under comparison, marker-based attribution copies, fidelity
checking, and span formatting helpers.
**Reads:** nothing — pure text-diff functions.
**Writes:** nothing.
**Called by:** `green_overlay_probe.py`, `_cases.py`.
**Calls out:** none — self-contained.

### green_overlay_probe_cases.py (124 LOC)

**Purpose:** Live `_injected.jsonl` gating-soundness scan, plus the primary bug case and regression
cases used by the report.
**Reads:** one recorded session's dual-log files; all `*_injected.jsonl` under `src/logs/dual_log`.
**Writes:** nothing — returns case tuples/dicts.
**Called by:** `green_overlay_probe.py`.
**Calls out:** `green_overlay_probe_diff.py`.

---

### groundtruth_message_spans_probe.py (90 LOC)

**Purpose:** CLI entry point validating the ground-truth span-construction algorithm that replaces
blind diffing for messages.
**Reads:** recorded `_original.jsonl` dual-log payloads (re-runs `apply_modification_rules` on them).
**Writes:** `groundtruth_message_spans_probe_reports/groundtruth_spans_<timestamp>.md`.
**Called by:** none — manual, one-off design-validation probe.
**Calls out:** `groundtruth_spans_cases.py`, `_report.py`.

### groundtruth_spans_algorithm.py (165 LOC)

**Purpose:** The ground-truth algorithm under test, the current-production diff baseline, minimal
src/ mirror helpers, and fidelity checks.
**Reads:** nothing — pure text/span functions.
**Writes:** nothing.
**Called by:** `groundtruth_spans_cases.py`, `_report.py`.
**Calls out:** none.

### groundtruth_spans_cases.py (169 LOC)

**Purpose:** `apply_modification_rules` re-run wrapper and the 4 real-log case builders.
**Reads:** recorded `_original.jsonl`/`_forwarded.jsonl` dual-log payloads (two hardcoded stems).
**Writes:** nothing — returns case dicts.
**Called by:** `groundtruth_message_spans_probe.py`.
**Calls out:** `src.proxy.rules`; `groundtruth_spans_algorithm.py`.

### groundtruth_spans_report.py (244 LOC)

**Purpose:** Runs one case through both algorithms and builds every report section (summary,
per-case detail, fidelity, conclusion).
**Reads:** case dicts from `groundtruth_spans_cases.py`.
**Writes:** nothing — appends to the caller's line list.
**Called by:** `groundtruth_message_spans_probe.py`.
**Calls out:** `groundtruth_spans_algorithm.py`.

---

### composition_probe.py (211 LOC)

**Purpose:** CLI entry point proving multi-pass span composition over the original content,
validating two reconstruction invariants across the corpus.
**Reads:** the full dual-log corpus (`*_original.jsonl` and siblings) present at run time.
**Writes:** `01_reports/composition_probe_<date>.md`.
**Called by:** `test_composition_invariant.py` (imports it as a module); otherwise run manually.
**Calls out:** `src.proxy.strip_bg_completed`; `composition_probe_ops.py`, `_passes.py`, `_corpus.py`.

### composition_probe_ops.py (145 LOC)

**Purpose:** The span algebra — cache_control strip, inner-text extraction, op extraction, the core
span-list edit primitive, and invariant checking.
**Reads:** nothing — pure data transforms.
**Writes:** nothing.
**Called by:** `composition_probe.py`, `_passes.py`, `_corpus.py`, `test_composition_invariant.py`.
**Calls out:** none.

### composition_probe_passes.py (61 LOC)

**Purpose:** Runs the 8 production proxy passes plus wakeup-dedup in sequence, collecting per-block
ops from each pass's real return value.
**Reads:** message list passed in by the caller.
**Writes:** nothing — returns `(final_messages, ops_by_msg_blk)`.
**Called by:** `composition_probe.py`, `_corpus.py`, `test_composition_invariant.py`.
**Calls out:** `src.proxy.rules`; `composition_probe_ops.py`.

### composition_probe_corpus.py (135 LOC)

**Purpose:** Scans the 5 fixed corpus stems, running every modified block through the pass chain
and aggregating pass/fail stats.
**Reads:** the 5 fixed `LOG_STEMS`' `_original.jsonl` files under `src/logs/dual_log`.
**Writes:** nothing — returns stats dicts.
**Called by:** `composition_probe.py`.
**Calls out:** `composition_probe_ops.py`, `_passes.py`.

---

### attribution_coverage.py (39 LOC)

**Purpose:** CLI entry point for the read-only coverage analysis — can every stripped/injected
entry be attributed to a proxy function?
**Reads:** all `*_stripped.jsonl`/`*_injected.jsonl` pairs under `src/logs/dual_log`.
**Writes:** `attribution_coverage_reports/<YYYYMMDD>.md`.
**Called by:** none — manual CLI.
**Calls out:** `src.proxy.strip_vocab` (loaded via `importlib`); `attribution_coverage_analyse.py`,
`_report.py`.

### attribution_coverage_classify.py (83 LOC)

**Purpose:** Owns the top-level-field attribution maps, span-format detection, strip/inject message
classification, and coverage percentage calculation.
**Reads:** nothing — pure classification functions.
**Writes:** nothing.
**Called by:** `attribution_coverage_analyse.py`, `_report.py`, `attribution_coverage.py`.
**Calls out:** none.

### attribution_coverage_analyse.py (140 LOC)

**Purpose:** Pair discovery, JSONL loading, and the per-section strip+inject analysers that build
aggregated coverage stats.
**Reads:** paired `*_stripped.jsonl`/`*_injected.jsonl` files.
**Writes:** nothing — returns stats/residuals/false-positives.
**Called by:** `attribution_coverage.py`.
**Calls out:** `attribution_coverage_classify.py`.

### attribution_coverage_report.py (243 LOC)

**Purpose:** Builds the Markdown report — strip/inject attribution tables, residual analysis,
false-positive evidence, and gap-coverage status.
**Reads:** the aggregated stats from `attribution_coverage_analyse.py`.
**Writes:** returns the report as a string.
**Called by:** `attribution_coverage.py`.
**Calls out:** `attribution_coverage_classify.py`; `src.proxy.strip_vocab` (own `importlib` load).

---

### A_render_refactor_proof.py (108 LOC)

**Purpose:** CLI harness (capture/verify modes) for the byte-identical differential test of the
proxy_display render cluster.
**Reads:** fixture entries from `A_render_refactor_proof_cases.py`; `--mode verify` also reads a
baseline JSON.
**Writes:** `A_render_refactor_proof_reports/<name>.json` (capture mode).
**Called by:** none — manual, run around a render-cluster refactor.
**Calls out:** `src.proxy_display.format`; `A_render_refactor_proof_cases.py`.

### A_render_refactor_proof_fixtures.py (35 LOC)

**Purpose:** The 3 low-level fixture builders shared by every case.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `A_render_refactor_proof_cases.py`.
**Calls out:** none.

### A_render_refactor_proof_cases.py (232 LOC)

**Purpose:** The 14 fixed test cases covering every render branch (new/stripped messages,
dual-span formats, tools, system blocks, expand-all fixpoint).
**Reads:** nothing — synthetic in-script fixture data.
**Writes:** nothing.
**Called by:** `A_render_refactor_proof.py`.
**Calls out:** `A_render_refactor_proof_fixtures.py`.

---

### proxy_176_agent_types_tests.py (142 LOC)

**Purpose:** Unit tests for the CC 2.1.176 agent-types system-reminder strip and its attribution
code.
**Reads:** nothing — synthetic in-script fixture text.
**Writes:** PASS/FAIL lines to stdout.
**Called by:** none — manual CLI.
**Calls out:** `proxy.message_passes`, `.strip_inject_delta`, `.diff_engine`, `.logging`,
`.rule_ops` (via direct `sys.path` insertion).

---

### proxy_176_bg_launch_ack_tests.py (66 LOC)

**Purpose:** CLI runner for the CC 2.1.176 background-launch-ack strip unit tests — imports and
sequences every test case.
**Reads:** nothing.
**Writes:** PASS/FAIL lines to stdout.
**Called by:** none — manual CLI.
**Calls out:** `proxy_176_bg_launch_ack_cases.py`, `_cases_w3.py`.

### proxy_176_bg_launch_ack_fixtures.py (106 LOC)

**Purpose:** Wording 1/2/3 launch-ack fixture texts, their expected hold-message replacements, and
false-positive fixtures.
**Reads:** nothing — pure constants.
**Writes:** nothing.
**Called by:** `proxy_176_bg_launch_ack_cases.py`, `_cases_w3.py`.
**Calls out:** none.

### proxy_176_bg_launch_ack_report.py (10 LOC)

**Purpose:** The shared `check()` PASS/FAIL-line printer and its ANSI color constants.
**Reads:** nothing.
**Writes:** PASS/FAIL lines to stdout (via `check`).
**Called by:** `proxy_176_bg_launch_ack_cases.py`, `_cases_w3.py`.
**Calls out:** none.

### proxy_176_bg_launch_ack_cases.py (256 LOC)

**Purpose:** Wording 1/2 launch-ack replacement, false-positive, and attribution tests for the
background-launch-ack strip.
**Reads:** nothing — synthetic fixture text via `proxy_176_bg_launch_ack_fixtures.py`.
**Writes:** PASS/FAIL lines to stdout (via `check`).
**Called by:** `proxy_176_bg_launch_ack_tests.py`.
**Calls out:** `proxy.message_passes_simple`, `.strip_inject_delta`, `.diff_engine`, `.logging`,
`.rule_ops`, `.strip_vocab`.

### proxy_176_bg_launch_ack_cases_w3.py (172 LOC)

**Purpose:** Wording 3 (auto-backgrounded-on-timeout) tests plus the full-replacement-span-shape
and main-vs-worker wording pins.
**Reads:** nothing — synthetic fixture text via `proxy_176_bg_launch_ack_fixtures.py`.
**Writes:** PASS/FAIL lines to stdout (via `check`).
**Called by:** `proxy_176_bg_launch_ack_tests.py`.
**Calls out:** `proxy.message_passes_simple`, `.strip_inject_delta`, `.diff_engine`, `.logging`,
`.rule_ops`, `.strip_vocab`, `.strip_bg_launch_ack`.

---

### proxy_176_strip_tests.py (169 LOC)

**Purpose:** Unit tests for two CC 2.1.176 proxy drift fixes — the Workflow tool blocklist entry
and the role=system message strip.
**Reads:** nothing — synthetic in-script fixture text.
**Writes:** PASS/FAIL lines to stdout.
**Called by:** none — manual CLI.
**Calls out:** `proxy.tools`, `.message_passes`, `.strip_inject_delta`, `.diff_engine`, `.logging`
(via direct `sys.path` insertion).

---

### test_composition_invariant.py (111 LOC)

**Purpose:** CI-style regression test asserting the two composition invariants hold for every
modified block in a synthetic fixture corpus.
**Reads:** `fixtures/invariant_corpus.jsonl`.
**Writes:** PASS/FAIL summary to stdout; exits 1 on any invariant violation.
**Called by:** none — manual CLI, exit code suitable for CI use.
**Calls out:** `composition_probe` (same-directory module, re-exports helpers from its sibling
modules).

---

## State

No shared or mutating state across modules. Each CLI entry point owns its own report-writing
(`REPORT_DIR`/`_REPORT_DIR` constants); sibling helper modules are pure functions with no
module-level mutable state, except `tt_delta_skip_replay.py`'s `has_content_map`, which
monkeypatches and restores `_accumulator._msgs_delta_is_substantial` for the duration of one
baseline comparison call.
