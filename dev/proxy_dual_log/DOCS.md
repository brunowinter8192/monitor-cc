# dev/proxy_dual_log/

## Role
Verification suite for the dual-log quartet (`_original`/`_forwarded`/`_stripped`/`_injected`)
written by `src/proxy/addon.py` under src/logs/dual_log. Proves losslessness and self-consistency of
the forwarded-delta log against the original log, and completeness of the strip/inject diff engine
(`src/proxy/diff_engine.py`). Touch when changing the dual-log write side, the diff engine, or the
read-side badge/render logic that consumes `_stripped`/`_injected`.

## Flow
Each script reads one or more dual-log JSONL files (or synthetic fixtures), replays the delta chain
or the real modification pipeline, and either asserts an invariant (exit 1 on violation) or writes a
findings report to `md/`. Every top-level probe/test script here is a thin CLI entry point whose
INFRASTRUCTURE/ORCHESTRATOR/FUNCTIONS live in the file itself; scripts over ~400 LOC or with a
function at 50+ lines are split into same-directory sibling modules by concern (algorithm, case
data, report rendering, I/O) — each sibling is a plain `INFRASTRUCTURE` + `FUNCTIONS` helper module
(no `ORCHESTRATOR`, per the Utility-module exception) imported back into the CLI entry point.

## Modules

### verify_delta.py (294 LOC)

**Purpose:** Reconstructs the full forwarded payload from a `_forwarded.jsonl` delta stream
(per-model-family chain) and verifies element counts match the delta entry's own declared counts
(hard check), plus a soft diagnostic comparing message counts against the original log.
**Reads:** an `_original.jsonl` + `_forwarded.jsonl` pair (positional or `--original`/`--forwarded`).
**Writes:** a per-request table and PASS/FAIL summary to stdout.
**Called by:** none — manual CLI, exits 1 on a hard-check failure.
**Calls out:** none at import time — parses JSONL directly.

---

### tt_delta_skip_replay.py (299 LOC)

**Purpose:** Before/after proof for the read-side `<total_tokens>N tokens left</total_tokens>` badge
suppression (including its trailing-nudge variant). Replays an `_original.jsonl` through the real
`apply_modification_rules`, feeds the result into the real `_build_stripped_injected_deltas`, and
runs the resulting dual-log lines through the real `accumulate_dual_log`/`badge_flags`, comparing the
old one-to-one badge rule against the current one via `--compare`.
**Reads:** a dual-log stem's `_original.jsonl`/`_stripped.jsonl`/`_injected.jsonl` triplet under the
main checkout's src/logs/dual_log (gitignored runtime data).
**Writes:** PASS/FAIL classification report to stdout.
**Called by:** none — manual CLI, exits 1 if a class regresses.
**Calls out:** `src.proxy.rules` (`apply_modification_rules`), `src.proxy_display.dual_log_accumulator`,
`src.proxy_display.proxy_badge`.

---

### diff_strip_inject.py (252 LOC)

**Purpose:** Span-level strip/inject diff of an original vs. forwarded proxy log pair — reconstructs
the forwarded payload from the delta chain, aligns blocks (system by index, tools by name, messages
by index), and classifies spans as equal/stripped/injected via `difflib`. Word-level diff when
`SequenceMatcher.ratio() >= 0.1`, whole-block 2-span replacement below that threshold.
**Reads:** an `_original.jsonl` + `_forwarded.jsonl` pair (positional or `--original`/`--forwarded`).
**Writes:** per-request diff sections with IDENTICAL/REPLACED/STRIPPED/INJECTED tags to stdout.
**Called by:** none — manual CLI.
**Calls out:** `src.proxy.diff_engine`.

---

### span_inline_probe.py (68 LOC)

**Purpose:** CLI entry point for the Form A vs Form B inline-render data model probe — validates that
a full ordered span list per log (Form B) is the minimal data model letting the read side render
strip/inject inline without content duplication, by showing Form A's (offset+text anchor) empirical
failure on real diff data across three probed blocks from a fixed recorded session.
**Reads:** a fixed recorded session's dual-log files (hardcoded session reference).
**Writes:** `span_inline_probe_reports/<YYYYMMDD>.md`.
**Called by:** none — manual, one-off design-validation probe.
**Calls out:** `src.proxy.diff_engine` (`_diff_text`, loaded via `importlib`, standalone);
`span_inline_probe_reconstruct.py`, `span_inline_probe_blocks.py`, `span_inline_probe_report.py`.

### span_inline_probe_reconstruct.py (88 LOC)

**Purpose:** JSONL loading, per-model-family forwarded-delta chain reconstruction, and
original/forwarded request matching (by request_id, falling back to family-order position).
**Reads:** JSONL file objects passed in by the caller.
**Writes:** nothing — pure data transforms.
**Called by:** `span_inline_probe.py`.
**Calls out:** none.

### span_inline_probe_blocks.py (115 LOC)

**Purpose:** Locates the three representative probe blocks (B1 sys full-replace, B2 sys
strip-to-dot, B3 message word-level-mixed-with-cache_control-diff) in a matched request list.
**Reads:** matched `(orig_entry, fwd_entry, fwd_state)` tuples; takes the diff function as a
parameter rather than importing `diff_engine` itself.
**Writes:** nothing — returns block-description dicts.
**Called by:** `span_inline_probe.py`.
**Calls out:** none.

### span_inline_probe_report.py (384 LOC)

**Purpose:** Builds the Markdown report — per-block span sequence, inline render mock, Form A
position-offset empirical analysis, Form B per-log views + storage-cost table, plus the fixed
design-tension and recommendation sections.
**Reads:** block-description dicts from `span_inline_probe_blocks.py`.
**Writes:** returns the report as a list of lines.
**Called by:** `span_inline_probe.py`.
**Calls out:** none.

---

### main_log_elimination_probe.py (77 LOC)

**Purpose:** CLI entry point for the feasibility probe on eliminating the single main proxy log in
favor of the dual-log quartet — wires path resolution, both questions, and report writing together.
**Reads:** a dual-log quartet plus the corresponding main proxy log for one session (session suffix
via positional arg, default hardcoded).
**Writes:** `main_log_elimination_probe_reports/<date>.md`.
**Called by:** none — manual, one-off feasibility probe.
**Calls out:** `main_log_elimination_io.py`, `main_log_elimination_questions.py`,
`main_log_elimination_report.py`.

### main_log_elimination_io.py (66 LOC)

**Purpose:** Project-root/log-path resolution, required-file existence check, and JSONL loaders
(main log, tool_errors, generic).
**Reads:** `MONITOR_CC_ROOT` env var or `__file__`-relative fallback; log files on disk.
**Writes:** nothing — pure I/O helpers; exits 1 via `_check_paths` if a required log is missing.
**Called by:** `main_log_elimination_probe.py`.
**Calls out:** none.

### main_log_elimination_reconstruct.py (156 LOC)

**Purpose:** Delta-chain reconstruction (`_reconstruct_forwarded`), cache_control-aware element
normalization/comparison, and the top-level raw_payload field classification tables/maps
(delta-covered / must-add / metadata-pane-only).
**Reads:** nothing — pure data transforms over passed-in entries.
**Writes:** nothing.
**Called by:** `main_log_elimination_questions.py`, `main_log_elimination_report.py`.
**Calls out:** none — inlines the cache-control-strip and shape-normalization helpers from
`src/proxy/logging.py` verbatim.

### main_log_elimination_questions.py (153 LOC)

**Purpose:** Answers Question A (forwarded-reconstruction vs. main-log `raw_payload` content match,
per-request) and Question B (is_error tool_result extraction from `_original`, dedup by
tool_use_id, compared against `tool_errors.jsonl`).
**Reads:** main-log entries, forwarded-delta entries, `_original` entries, tool_errors records.
**Writes:** nothing — returns result dicts.
**Called by:** `main_log_elimination_probe.py`.
**Calls out:** `main_log_elimination_reconstruct.py`.

### main_log_elimination_report.py (218 LOC)

**Purpose:** Builds the Markdown report — header, Question A content-match/BP-divergence/
field-classification sections, Question B section, and the migration verdict.
**Reads:** the Question A/B result dicts.
**Writes:** the report file; returns its path.
**Called by:** `main_log_elimination_probe.py`.
**Calls out:** `main_log_elimination_reconstruct.py` (`_DELTA_COVERED`).

---

### green_overlay_probe.py (222 LOC)

**Purpose:** CLI entry point that reproduces a green-overlay false-injection bug in the word-level
diff path (JSON-escaped `\n` sequences merged into single "words" by `.split()`, causing a shared
prefix to be mis-tagged as both stripped and injected) and validates a char-level `SequenceMatcher`
fix against real log data plus synthetic regression cases.
**Reads:** one recorded session's dual-log files (hardcoded session reference).
**Writes:** `green_overlay_probe_reports/green_overlay_probe.md`.
**Called by:** none — manual, one-off bug-repro probe.
**Calls out:** `green_overlay_probe_diff.py`, `green_overlay_probe_cases.py`.

### green_overlay_probe_diff.py (210 LOC)

**Purpose:** The three diff variants under comparison (`diff_text_word` current-production,
`diff_text_char` candidate fix, `diff_text_char_gated` attribution-gated fix), the marker-based
attribution copies (`_STRIP_RULES_MARKERS`/`_MSG_CODE_TO_FN`), fidelity checking, and span
formatting/comparison helpers.
**Reads:** nothing — pure text-diff functions.
**Writes:** nothing.
**Called by:** `green_overlay_probe.py`, `green_overlay_probe_cases.py` (`_fn_for_inject`).
**Calls out:** none — self-contained, no `src/` imports at module level.

### green_overlay_probe_cases.py (135 LOC)

**Purpose:** Live `_injected.jsonl` gating-soundness scan, and the primary bug case +
3 real-log regression cases + 1 synthetic whitespace-collapse case used by the report.
**Reads:** one recorded session's dual-log files (hardcoded session reference); all
`*_injected.jsonl` files under `src/logs/dual_log` for the soundness scan.
**Writes:** nothing — returns case tuples / dicts.
**Called by:** `green_overlay_probe.py`.
**Calls out:** `green_overlay_probe_diff.py`.

---

### groundtruth_message_spans_probe.py (115 LOC)

**Purpose:** CLI entry point validating `build_message_spans(orig_text, fwd_text, stripped_chunks)`,
the ground-truth span-construction algorithm that replaces blind diffing for messages — builds spans
directly from the chunks `apply_modification_rules` recorded as stripped, rather than diffing
original against forwarded text.
**Reads:** recorded `_original.jsonl` dual-log payloads (re-runs `apply_modification_rules` on them
to regenerate `stripped_msg_removed`).
**Writes:** `groundtruth_message_spans_probe_reports/groundtruth_spans_<timestamp>.md`.
**Called by:** none — manual, one-off design-validation probe.
**Calls out:** `groundtruth_spans_cases.py`, `groundtruth_spans_report.py`.

### groundtruth_spans_algorithm.py (191 LOC)

**Purpose:** The GT algorithm under test (`build_message_spans`, split into
`_split_stripped_chunks`/`_walk_forward_spans`), the current-production `diff_text_word` baseline,
minimal src/ mirror helpers (`_strip_cache_control`/`_normalize_msg_shape`/`_get_text`/
`_get_inner_text`), and the two fidelity checks.
**Reads:** nothing — pure text/span functions.
**Writes:** nothing.
**Called by:** `groundtruth_spans_cases.py`, `groundtruth_spans_report.py`.
**Calls out:** none.

### groundtruth_spans_cases.py (179 LOC)

**Purpose:** `apply_modification_rules` re-run wrapper and the 4 real-log case builders (bug case,
text-block-replace case, bg-exit-replace case, multi-chunk/large-SR case).
**Reads:** recorded `_original.jsonl`/`_forwarded.jsonl` dual-log payloads (two hardcoded stems).
**Writes:** nothing — returns case dicts.
**Called by:** `groundtruth_message_spans_probe.py`.
**Calls out:** `src.proxy.rules` (`apply_modification_rules`, lazy import inside `run_rules`);
`groundtruth_spans_algorithm.py`.

### groundtruth_spans_report.py (253 LOC)

**Purpose:** Runs one case through both algorithms (`run_case`) and builds every report section
(summary table, per-case GT/diff/bug/replace detail, fidelity summary, zero-phantom summary,
recording-gaps summary, conclusion).
**Reads:** case dicts from `groundtruth_spans_cases.py`.
**Writes:** nothing — appends to the caller's `emit`-collected line list.
**Called by:** `groundtruth_message_spans_probe.py`.
**Calls out:** `groundtruth_spans_algorithm.py`.

---

### composition_probe.py (233 LOC)

**Purpose:** CLI entry point proving multi-pass span composition over the original content (C0) —
models each proxy pass as an `Op(offset, removed, injected)` and composes all passes into one span
list, validating two reconstruction invariants (`equal+stripped == C0`, `equal+injected == Cfwd`)
across every modified block in the corpus, including double-inject and multi-pass-per-block cases.
Also re-imports `_strip_cache_control`/`_block_text`/`compose_block`/`check_invariants`/
`run_passes_and_collect_ops` from its sibling modules so `import composition_probe as _probe`
(used by `test_composition_invariant.py`) keeps working unchanged.
**Reads:** the full dual-log corpus (`*_original.jsonl` and siblings) present at run time.
**Writes:** `01_reports/composition_probe_<date>.md`.
**Called by:** `test_composition_invariant.py` (imports it as a module for its own synthetic-fixture
check); otherwise run manually.
**Calls out:** `src.proxy.strip_bg_completed` (`_WAKEUP_TEXT`); `composition_probe_ops.py`,
`composition_probe_passes.py`, `composition_probe_corpus.py`.

### composition_probe_ops.py (164 LOC)

**Purpose:** The span algebra — cache_control strip, inner-text extraction, prefix/suffix op
extraction from a (before, after) pair, `apply_edit_to_spans` (the core span-list edit primitive),
block-pair diffing, `compose_block`, and `check_invariants`.
**Reads:** nothing — pure data transforms.
**Writes:** nothing.
**Called by:** `composition_probe.py`, `composition_probe_passes.py`, `composition_probe_corpus.py`,
`test_composition_invariant.py` (via `composition_probe`'s re-export).
**Calls out:** none.

### composition_probe_passes.py (69 LOC)

**Purpose:** Runs the 8 production proxy passes plus `_dedup_wakeup_blocks` in sequence, collecting
per-block ops from each pass's real op-recording return value (all passes now real, no stand-in).
**Reads:** message list passed in by the caller.
**Writes:** nothing — returns `(final_messages, ops_by_msg_blk)`.
**Called by:** `composition_probe.py`, `composition_probe_corpus.py`,
`test_composition_invariant.py` (via `composition_probe`'s re-export).
**Calls out:** `src.proxy.rules` (lazy import inside `run_passes_and_collect_ops`);
`composition_probe_ops.py`.

### composition_probe_corpus.py (139 LOC)

**Purpose:** Scans the 5 fixed corpus stems, running every modified block through
`run_passes_and_collect_ops` + `compose_block` + `check_invariants` and aggregating pass-level
pass/fail stats and failing cases; also the msg[100] TN+BG double-inject money-shot case lookup.
**Reads:** the 5 fixed `LOG_STEMS`' `_original.jsonl` files under `src/logs/dual_log`.
**Writes:** nothing — returns stats dicts.
**Called by:** `composition_probe.py`.
**Calls out:** `composition_probe_ops.py`, `composition_probe_passes.py`.

---

### attribution_coverage.py (53 LOC)

**Purpose:** CLI entry point for the read-only coverage analysis — can every entry in the
`_stripped`/`_injected` dual-logs be attributed to a responsible proxy function?
**Reads:** all `*_stripped.jsonl`/`*_injected.jsonl` pairs under src/logs/dual_log.
**Writes:** `attribution_coverage_reports/<YYYYMMDD>.md`.
**Called by:** none — manual CLI.
**Calls out:** `src.proxy.strip_vocab` (`attribute_chunk`, loaded via
`importlib.util.spec_from_file_location`); `attribution_coverage_analyse.py`,
`attribution_coverage_report.py`.

### attribution_coverage_classify.py (101 LOC)

**Purpose:** Owns the only `_FIELD_STRIP_FN`/`_FIELD_INJECT_FN` maps left for top-level-field
attribution (`model`/`max_tokens`/`thinking`/`output_config`/`context_management`) — this is the
live attribution mechanism for those fields; `src/proxy/strip_inject_delta.py` used to hold an
unread, already-drifted copy of the same two maps, removed as dead code (see that module's own
DOCS.md entry). Also the span-format detection, strip/inject message classification, and coverage
percentage calculation.
**Reads:** nothing — pure classification functions.
**Writes:** nothing.
**Called by:** `attribution_coverage_analyse.py`, `attribution_coverage_report.py`,
`attribution_coverage.py` (`_SYS_INJECT_FN` via `attribution_coverage_analyse.py`).
**Calls out:** none.

### attribution_coverage_analyse.py (147 LOC)

**Purpose:** Pair discovery, JSONL loading, and the per-section (sys/tools/messages/fields)
strip+inject analysers that build the aggregated coverage stats.
**Reads:** paired `*_stripped.jsonl`/`*_injected.jsonl` files.
**Writes:** nothing — returns `(strip_stats, inject_stats, residuals, false_positives)`.
**Called by:** `attribution_coverage.py`.
**Calls out:** `attribution_coverage_classify.py`.

### attribution_coverage_report.py (245 LOC)

**Purpose:** Builds the Markdown report — header, strip/inject attribution tables, residual
analysis, false-positive (json_reserialization bug) evidence, and gap-coverage status.
**Reads:** the aggregated stats from `attribution_coverage_analyse.py`.
**Writes:** returns the report as a string.
**Called by:** `attribution_coverage.py`.
**Calls out:** `attribution_coverage_classify.py`; `src.proxy.strip_vocab` (`RULES`, loaded via its
own `importlib.util.spec_from_file_location`, separate from `attribution_coverage.py`'s load).

---

### A_render_refactor_proof.py (125 LOC)

**Purpose:** CLI harness (capture/verify modes) for the byte-identical differential test of the
proxy_display render cluster — `--mode capture` runs the fixture cases through `format_proxy_block`
and writes `(ansi_string, total_lines)` per case to a baseline JSON; `--mode verify` re-runs the
same cases and asserts byte-identity against that baseline.
**Reads:** fixture entries from `A_render_refactor_proof_cases.py`; `--mode verify` also reads a
baseline JSON under `A_render_refactor_proof_reports/`.
**Writes:** `A_render_refactor_proof_reports/<name>.json` (capture mode).
**Called by:** none — manual, run as capture/implement/verify around a render-cluster refactor
(also reused by `dev/proxy_tool_stripping/` for its own regression checks — see that DOCS.md).
**Calls out:** `src.proxy_display.format` (`format_proxy_block`); `A_render_refactor_proof_cases.py`.

### A_render_refactor_proof_fixtures.py (35 LOC)

**Purpose:** The 3 low-level fixture builders (`_mk_entry`/`_mk_msg`/`_mk_blk`) shared by every case.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `A_render_refactor_proof_cases.py`.
**Calls out:** none.

### A_render_refactor_proof_cases.py (246 LOC)

**Purpose:** The 14 fixed test cases (`_build_cases` + one `_case_*` builder per case) covering
every render branch (new/stripped/tail-fallback messages, dual-span new/legacy format, tools
first-request/changed, system blocks, standalone haiku, copy-feedback, hover/scroll, label
collision, and the expand-all fixpoint).
**Reads:** nothing — synthetic in-script fixture data.
**Writes:** nothing.
**Called by:** `A_render_refactor_proof.py`.
**Calls out:** `A_render_refactor_proof_fixtures.py`.

---

### proxy_176_agent_types_tests.py (155 LOC)

**Purpose:** Unit tests for the CC 2.1.176 agent-types system-reminder strip — a standalone
`<system-reminder>`-wrapped "Available agent types" block in a user message must strip via
`_apply_cumulative_sr_strips` and attribute to code `AT` in `_MSG_CODE_TO_FN`.
**Reads:** nothing — synthetic in-script fixture text.
**Writes:** PASS/FAIL lines to stdout.
**Called by:** none — manual CLI; its own usage comment names a stale top-level `dev/` path that
predates this file's move into `dev/proxy_dual_log/`.
**Calls out:** `proxy.message_passes`, `proxy.strip_inject_delta`, `proxy.diff_engine`,
`proxy.logging`, `proxy.rule_ops` — imported after inserting `src/` directly onto `sys.path` (not a
`from src.` line).

---

### proxy_176_bg_launch_ack_tests.py (74 LOC)

**Purpose:** CLI runner for the CC 2.1.176 background-launch-ack strip
(`_apply_bg_launch_ack_strip`) unit tests — imports and sequences every `test_*` case.
**Reads:** nothing.
**Writes:** PASS/FAIL lines to stdout.
**Called by:** none — manual CLI.
**Calls out:** `proxy_176_bg_launch_ack_cases.py`, `proxy_176_bg_launch_ack_cases_w3.py` — both
import `proxy.message_passes_simple`/`proxy.strip_inject_delta`/`proxy.diff_engine`/`proxy.logging`/
`proxy.rule_ops`/`proxy.strip_vocab`/`proxy.strip_bg_launch_ack` after this file inserts `src/`
directly onto `sys.path`.

### proxy_176_bg_launch_ack_fixtures.py (123 LOC)

**Purpose:** Wording 1/2/3 launch-ack fixture texts, their expected 3-line hold-message
replacements, and the false-positive (marker-quoted-mid-content) fixtures for each wording.
**Reads:** nothing — pure constants.
**Writes:** nothing.
**Called by:** `proxy_176_bg_launch_ack_cases.py`, `proxy_176_bg_launch_ack_cases_w3.py`.
**Calls out:** none.

### proxy_176_bg_launch_ack_report.py (10 LOC)

**Purpose:** The shared `check()` PASS/FAIL-line printer and its ANSI color constants.
**Reads:** nothing.
**Writes:** PASS/FAIL lines to stdout (via `check`).
**Called by:** `proxy_176_bg_launch_ack_cases.py`, `proxy_176_bg_launch_ack_cases_w3.py`.
**Calls out:** none.

### proxy_176_bg_launch_ack_cases.py (256 LOC)

**Purpose:** Items 4a–4p — tool_result/text-block/string-content/list-content replacement tests,
non-matching and completion-notification negative tests, BL-code attribution, wording-1
false-positive preservation tests, and the wording-2 tests (replacement, FP, attribution, same
message-line-as-wording-1 check).
**Reads:** nothing — synthetic in-script fixture text via `proxy_176_bg_launch_ack_fixtures.py`.
**Writes:** PASS/FAIL lines to stdout (via `check`).
**Called by:** `proxy_176_bg_launch_ack_tests.py`.
**Calls out:** `proxy.message_passes_simple`, `proxy.strip_inject_delta`, `proxy.diff_engine`,
`proxy.logging`, `proxy.rule_ops`, `proxy.strip_vocab`.

### proxy_176_bg_launch_ack_cases_w3.py (193 LOC)

**Purpose:** Items 4q–4x — wording-3 (auto-backgrounded-on-timeout) tests (replacement, FP,
attribution, message-differs-and-names-timeout, main-vs-worker wording, ops-path visibility), the
full-replacement-is-one-contiguous-span-shape pin, and the wording-1 main-vs-worker wording test.
**Reads:** nothing — synthetic in-script fixture text via `proxy_176_bg_launch_ack_fixtures.py`.
**Writes:** PASS/FAIL lines to stdout (via `check`).
**Called by:** `proxy_176_bg_launch_ack_tests.py`.
**Calls out:** `proxy.message_passes_simple`, `proxy.strip_inject_delta`, `proxy.diff_engine`,
`proxy.logging`, `proxy.rule_ops`, `proxy.strip_vocab`, `proxy.strip_bg_launch_ack`.

---

### proxy_176_strip_tests.py (181 LOC)

**Purpose:** Unit tests for two CC 2.1.176 proxy drift fixes: `Workflow` added to `TOOL_BLOCKLIST`
(stripped by `_strip_unused_tools`), and `_apply_role_system_strip` stripping `role='system'`
messages unconditionally.
**Reads:** nothing — synthetic in-script fixture text.
**Writes:** PASS/FAIL lines to stdout.
**Called by:** none — manual CLI.
**Calls out:** `proxy.tools`, `proxy.message_passes`, `proxy.strip_inject_delta`, `proxy.diff_engine`,
`proxy.logging` — imported after inserting `src/` directly onto `sys.path`.

---

### test_composition_invariant.py (131 LOC)

**Purpose:** CI-style regression test asserting the two composition invariants (`equal+stripped ==
C0`, `equal+injected == Cfwd`) hold for every modified block across a synthetic 9-entry fixture
corpus covering all 8 proxy passes plus the wakeup-dedup pass.
**Reads:** `fixtures/invariant_corpus.jsonl`.
**Writes:** PASS/FAIL summary to stdout; exits 1 on any invariant violation.
**Called by:** none — manual CLI, exit code suitable for CI use.
**Calls out:** `composition_probe` (same-directory module, imported directly by adding this
directory and the project root to `sys.path` — `composition_probe.py` re-exports
`_strip_cache_control`/`run_passes_and_collect_ops`/`_block_text`/`compose_block`/
`check_invariants` from its own sibling modules for this import to keep working unchanged).

---

## Gotchas
- The dual-log corpus under src/logs/dual_log is live and growing from concurrent real sessions — a
  re-run of any corpus-scanning script here shifts absolute counts without changing the underlying
  correctness finding.
- Session-specific scripts (`span_inline_probe.py`, `green_overlay_probe.py`,
  `main_log_elimination_probe.py`) hardcode one recorded session's stem rather than taking it as an
  argument — they are one-off design-validation probes, not general-purpose regression tools.
- `tt_delta_skip_replay.py`'s inject check is an implication, not an equality — a green message span
  must light `inject`, but a system-section-only injection can legitimately light `inject` with an
  empty injected `messages_delta`.
- Every split-off sibling module (e.g. `composition_probe_ops.py`, `green_overlay_probe_diff.py`,
  `span_inline_probe_reconstruct.py`) duplicates small helpers (`_strip_cache_control`,
  `_infer_family`, delta-chain reconstruction) rather than importing them from another probe's
  sibling — this mirrors the pre-existing cross-script duplication convention in this directory and
  was deliberately not touched by the cohesion split (see process-docs/proxy_dual_log/ for the
  2026-09-15 entry).
