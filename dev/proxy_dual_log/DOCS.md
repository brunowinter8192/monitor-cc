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
findings report to `md/`.

## Modules

### verify_delta.py (272 LOC)

**Purpose:** Reconstructs the full forwarded payload from a `_forwarded.jsonl` delta stream
(per-model-family chain) and verifies element counts match the delta entry's own declared counts
(hard check), plus a soft diagnostic comparing message counts against the original log.
**Reads:** an `_original.jsonl` + `_forwarded.jsonl` pair (positional or `--original`/`--forwarded`).
**Writes:** a per-request table and PASS/FAIL summary to stdout.
**Called by:** none — manual CLI, exits 1 on a hard-check failure.
**Calls out:** none at import time — parses JSONL directly.

---

### tt_delta_skip_replay.py (282 LOC)

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

### diff_strip_inject.py (239 LOC)

**Purpose:** Span-level strip/inject diff of an original vs. forwarded proxy log pair — reconstructs
the forwarded payload from the delta chain, aligns blocks (system by index, tools by name, messages
by index), and classifies spans as equal/stripped/injected via `difflib`. Word-level diff when
`SequenceMatcher.ratio() >= 0.1`, whole-block 2-span replacement below that threshold.
**Reads:** an `_original.jsonl` + `_forwarded.jsonl` pair (positional or `--original`/`--forwarded`).
**Writes:** per-request diff sections with IDENTICAL/REPLACED/STRIPPED/INJECTED tags to stdout.
**Called by:** none — manual CLI.
**Calls out:** `src.proxy.diff_engine`.

---

### span_inline_probe.py (625 LOC)

**Purpose:** Validates that a full ordered span list per log (Form B) is the minimal data model
letting the read side render strip/inject inline without content duplication, by showing Form A's
(offset+text anchor) empirical failure on real diff data across three probed blocks.
**Reads:** a fixed recorded session's dual-log files (hardcoded session reference).
**Writes:** `md/span_inline_probe_<date>.md`.
**Called by:** none — manual, one-off design-validation probe.
**Calls out:** `src.proxy.diff_engine` (`_diff_text`, loaded via `importlib`, standalone).

---

### main_log_elimination_probe.py (625 LOC)

**Purpose:** Feasibility probe for eliminating the single main proxy log in favor of the dual-log
quartet — reconstructs full payloads from the `_forwarded` delta chain and diffs against the main
log's `raw_payload`, classifying every top-level field as delta-covered / must-add / pane-only; also
cross-checks `is_error` tool_result extraction against `tool_errors.jsonl`.
**Reads:** a dual-log quartet plus the corresponding main proxy log for one session (session suffix
via positional arg, default hardcoded).
**Writes:** `md/main_log_elimination_<date>.md`.
**Called by:** none — manual, one-off feasibility probe.
**Calls out:** none at module scope — inlines the cache-control-strip and shape-normalization helpers
from `src/proxy/logging.py` verbatim.

---

### green_overlay_probe.py (538 LOC)

**Purpose:** Reproduces a green-overlay false-injection bug in the word-level diff path (JSON-escaped
`\n` sequences merged into single "words" by `.split()`, causing a shared prefix to be mis-tagged as
both stripped and injected) and validates a char-level `SequenceMatcher` fix against real log data
plus synthetic regression cases.
**Reads:** one recorded session's dual-log files (hardcoded session reference).
**Writes:** `md/green_overlay_probe.md`.
**Called by:** none — manual, one-off bug-repro probe.
**Calls out:** none — both diff variants (`diff_text_word`, `diff_text_char`) are implemented inline,
no `src/` imports at module level.

---

### groundtruth_message_spans_probe.py (669 LOC)

**Purpose:** Validates `build_message_spans(orig_text, fwd_text, stripped_chunks)`, the ground-truth
span-construction algorithm that replaces blind diffing for messages — builds spans directly from the
chunks `apply_modification_rules` recorded as stripped, rather than diffing original against
forwarded text.
**Reads:** recorded `_original.jsonl` dual-log payloads (re-runs `apply_modification_rules` on them to
regenerate `stripped_msg_removed`).
**Writes:** `md/groundtruth_spans_<timestamp>.md`.
**Called by:** none — manual, one-off design-validation probe.
**Calls out:** `src.proxy.rules` (`apply_modification_rules`).

---

### composition_probe.py (547 LOC)

**Purpose:** Proves multi-pass span composition over the original content (C0) — models each proxy
pass as an `Op(offset, removed, injected)` and composes all passes into one span list, validating two
reconstruction invariants (`equal+stripped == C0`, `equal+injected == Cfwd`) across every modified
block in the corpus, including double-inject and multi-pass-per-block cases.
**Reads:** the full dual-log corpus (`*_original.jsonl` and siblings) present at run time.
**Writes:** `md/composition_probe_<date>.md`.
**Called by:** `test_composition_invariant.py` (imports it as a module for its own synthetic-fixture
check); otherwise run manually.
**Calls out:** `src.proxy.rules`, `src.proxy.strip_bg_completed`.

---

### attribution_coverage.py (479 LOC)

**Purpose:** Read-only coverage analysis — can every entry in the `_stripped`/`_injected` dual-logs
be attributed to a responsible proxy function? Processes all available quartet pairs, produces
per-category attribution tables and RAW/ADJUSTED coverage percentages.
**Reads:** all `*_stripped.jsonl`/`*_injected.jsonl` pairs under src/logs/dual_log.
**Writes:** `md/attribution_coverage_<date>.md`.
**Called by:** none — manual CLI.
**Calls out:** `src.proxy.strip_vocab` (loaded via `importlib.util.spec_from_file_location`).

---

### A_render_refactor_proof.py (403 LOC)

**Purpose:** Byte-identical differential test harness for the proxy_display render cluster —
`--mode capture` runs 14 fixed cases through `format_proxy_block` and writes `(ansi_string,
total_lines)` per case to a baseline JSON; `--mode verify` re-runs the same cases and asserts
byte-identity against that baseline.
**Reads:** synthetic in-script fixture entries; `--mode verify` also reads a baseline JSON under
`A_render_refactor_proof_reports/`.
**Writes:** `A_render_refactor_proof_reports/<name>.json` (capture mode).
**Called by:** none — manual, run as capture/implement/verify around a render-cluster refactor
(also reused by `dev/proxy_tool_stripping/` for its own regression checks — see that DOCS.md).
**Calls out:** `src.proxy_display.format` (`format_proxy_block`).

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

### proxy_176_bg_launch_ack_tests.py (432 LOC)

**Purpose:** Unit tests for the CC 2.1.176 background-launch-ack strip (`_apply_bg_launch_ack_strip`)
across tool_result-string, tool_result-list, and standalone-text-block shapes, including two known
wordings and several false-positive-preservation cases.
**Reads:** nothing — synthetic in-script fixture text.
**Writes:** PASS/FAIL lines to stdout.
**Called by:** none — manual CLI.
**Calls out:** `proxy.message_passes_simple`, `proxy.strip_inject_delta`, `proxy.diff_engine`,
`proxy.logging`, `proxy.rule_ops`, `proxy.strip_vocab`, `proxy.strip_bg_launch_ack` — imported after
inserting `src/` directly onto `sys.path`.

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
directory and the project root to `sys.path`).

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
