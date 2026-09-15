# dev/tool_use_analysis/

## Role
Forensic extraction and analysis of tool_use blocks and system-reminder/task-notification content
from Claude Code sessions and proxy logs. Each script is standalone (no shared library across
scripts — small per-script helpers are inlined rather than factored out). Error/failure analysis and
rule-compliance scoring have moved to `dev/tool_use_errors/`.

## Flow
Each script reads one or more proxy-log or session JSONL files (positional args, or an auto-picked
newest/default set), computes one specific breakdown, and writes a Markdown report to `md/` or
stdout. Scripts over ~400 LOC or with a function at 50+ lines are split into same-directory sibling
modules by concern (data collection, classification, report rendering); each sibling is a plain
`INFRASTRUCTURE` + `FUNCTIONS` helper module (no `ORCHESTRATOR`, per the Utility-module exception)
imported back into the CLI entry point. No sibling module is shared across two different scripts'
splits — the "standalone script" convention above still holds at the split-group level.

## Modules

### extract_long_calls.py (85 LOC)

**Purpose:** CLI entry point — collects every `tool_use` block from proxy JSONL files, deduplicates
by id, measures serialized input size in characters, and ranks by size — identifies which tool calls
burn the most context budget. `--tool` filters by name (adds command-prefix clustering for Bash);
`--ratio` reports input/output ratio per matched tool_use/tool_result pair instead.
**Reads:** proxy JSONL paths under src/logs (positional, variadic).
**Writes:** Markdown report to stdout or `--output` file.
**Called by:** none — manual CLI.
**Calls out:** `extract_long_calls_lib.py`, `extract_long_calls_report.py`.

### extract_long_calls_lib.py (303 LOC)

**Purpose:** The former `src/proxy_forensics.py` library, inlined verbatim (removed 2026-04-19) —
`ToolUse`/`ToolResult`/`Pair`/`ToolStats`/`PrefixBucket` dataclasses, JSONL loading, tool_use/
tool_result collection and pairing, filtering, and the two aggregation functions (by tool, by Bash
command prefix).
**Reads:** nothing — pure data-model/collection functions over passed-in paths/events.
**Writes:** nothing.
**Called by:** `extract_long_calls.py`, `extract_long_calls_report.py`.
**Calls out:** none — stdlib JSONL parsing only.

### extract_long_calls_report.py (211 LOC)

**Purpose:** All Markdown report builders for both modes — per-tool summary tables, prefix-cluster
table, per-call detail sections (char-based and ratio-based), and the two top-level report
assemblers (`build_report`, `build_ratio_report`).
**Reads:** `ToolUse`/`Pair` objects from `extract_long_calls_lib.py`.
**Writes:** nothing — returns report strings.
**Called by:** `extract_long_calls.py`.
**Calls out:** `extract_long_calls_lib.py`.

---

### extract_zeros.py (365 LOC)

**Purpose:** Detects every Grep/Glob/Read call that returned a zero result across session JSONL
files, reporting each call's input, raw result, and the preceding assistant text (walking the
`parentUuid` chain) for search-intent context.
**Reads:** session JSONL paths (positional, variadic) under the user's Claude Code projects
directory.
**Writes:** Markdown report to stdout or `--output` file.
**Called by:** none — manual CLI.
**Calls out:** none — stdlib JSONL parsing only.

---

### rs_truncation_preserve_replay.py (113 LOC)

**Purpose:** Replay-verifies the `_apply_role_system_strip` preserve guard — every logged
`role='system'` message starting with a Read-truncation notice must pass through unchanged, while
other `role='system'` noise still reduces to `"."`.
**Reads:** one dual-log `_original.jsonl` path (positional, optional — default under src/logs/dual_log
in the worktree if present, else the main-checkout absolute path).
**Writes:** a console PASS/FAIL summary; a verbose per-failure table to
`dev/tool_use_analysis/md/rs_truncation_preserve_replay_detail.md`.
**Called by:** none — manual CLI.
**Calls out:** `src.proxy.message_passes` (`_apply_role_system_strip`).

---

### extract_transcript.py (181 LOC)

**Purpose:** Chronological tool_use/tool_result transcript from a proxy-log snapshot — a plain
timeline dump (no waste/ratio scoring) marking `(ERROR)` on failed tool_results, for tracing a
session's workflow and spotting redundant call sequences.
**Reads:** proxy JSONL paths under src/logs (positional, variadic) — uses the entry with the highest
`message_count` per file.
**Writes:** Markdown report to stdout or `--output` file.
**Called by:** none — manual CLI.
**Calls out:** none — stdlib JSONL parsing only.

---

### extract_patterns.py (74 LOC)

**Purpose:** CLI entry point — pairs every `tool_use` with its `tool_result`, filters to waste calls
(ratio ≥ 3, input ≥ 50 chars), normalizes inputs to grouping signatures (paths, log filenames, bead
IDs, hex IDs, timestamps, long strings), and aggregates by `(tool_name, signature)` into a 6-section
report including wrapper-script candidates.
**Reads:** proxy JSONL paths under src/logs (positional, variadic).
**Writes:** Markdown report to stdout or `--output` file.
**Called by:** none — manual CLI.
**Calls out:** `extract_patterns_collect.py`, `extract_patterns_report.py`.

### extract_patterns_collect.py (258 LOC)

**Purpose:** Load/dedup/signature-normalize tool_use and tool_result blocks, classify content-
transfer vs. waste vs. failed pairs, and aggregate them by tool/signature/error-type and by source
file.
**Reads:** nothing — pure data transforms over passed-in events.
**Writes:** nothing.
**Called by:** `extract_patterns.py`, `extract_patterns_report.py`.
**Calls out:** none — stdlib JSONL/regex parsing only.

### extract_patterns_wrappers.py (103 LOC)

**Purpose:** Wrapper-candidate naming and complexity classification — command-prefix extraction,
complexity tier (trivial/medium/structural), proposed wrapper name derivation, and the ranked/
deduped candidate list builder.
**Reads:** nothing — pure functions over signature strings and aggregated group dicts.
**Writes:** nothing.
**Called by:** `extract_patterns_report.py`.
**Calls out:** none.

### extract_patterns_report.py (210 LOC)

**Purpose:** All 6 report section renderers (per-source summary, tool breakdown, content-transfer
breakdown, Bash patterns, other-tool patterns, failed calls, wrapper candidates) plus the top-level
`_build_report` assembler.
**Reads:** aggregated stats/pair lists from `extract_patterns_collect.py`.
**Writes:** nothing — returns the report string.
**Called by:** `extract_patterns.py`.
**Calls out:** `extract_patterns_collect.py` (`_source_label`), `extract_patterns_wrappers.py`
(`_build_wrapper_candidates`).

---

### waste_repetition.py (311 LOC)

**Purpose:** Extracts deduplicated Bash `tool_use` blocks from a single JSONL file's cumulative
snapshot and analyzes waste two ways: repetition-signature groups (normalized command signature,
ranked by count × avg_chars) and known-shortcut path fragments (absolute paths replaceable with `~`
or a project alias).
**Reads:** one proxy JSONL path (positional).
**Writes:** Markdown report to stdout.
**Called by:** none — manual CLI.
**Calls out:** none — stdlib JSONL parsing only.

---

### cc_injection_audit.py (322 LOC)

**Purpose:** For each user-role message in an opus request's delta range, checks whether it appears
as a real user event in the matching CC session JSONL — unmatched messages are CC-injected,
classified by prefix pattern into a catalog of injection types.
**Reads:** proxy log paths (positional, optional — default: newest 5 opus proxy logs under src/logs);
CC session JSONL auto-discovered by mtime proximity, or `--cc-session`.
**Writes:** `dev/tool_use_analysis/md/<timestamp>_cc_injection_catalog.md`.
**Called by:** none — manual CLI.
**Calls out:** none — stdlib JSONL parsing only.

---

### rag_query_audit.py (364 LOC)

**Purpose:** Extracts and clusters rag-cli search calls from opus proxy logs for a helpfulness
evaluation — parses `rag-cli <verb> "<query>" <collection>` invocations (including compound bash
chains) and Jaccard-clusters queries above a threshold.
**Reads:** proxy JSONL paths under src/logs (positional or default glob
`api_requests_opus_monitor_cc_*.jsonl`).
**Writes:** `dev/tool_use_analysis/<date>_rag_query_audit.md` (`--output` or auto-dated).
**Called by:** none — manual CLI.
**Calls out:** none — stdlib JSONL/regex parsing only.

---

### rag_truncation_audit.py (83 LOC)

**Purpose:** CLI entry point — classifies every `[N characters truncated]` occurrence in opus proxy
logs by hypothesis (A/B/C) — checks where the truncation marker sits as a fraction of total content
length to distinguish CC's inline 5k/5k split from other truncation mechanisms, and whether the
truncated call was a rag-cli search.
**Reads:** proxy JSONL paths under src/logs (positional or default glob, 15 files).
**Writes:** `dev/tool_use_analysis/<date>_rag_truncation_audit.md` (`--output` or auto-dated).
**Called by:** none — manual CLI.
**Calls out:** `rag_truncation_audit_data.py`, `rag_truncation_audit_report.py`.

### rag_truncation_audit_data.py (204 LOC)

**Purpose:** Load proxy JSONL, collect tool_use/truncated-tool_result/echo-hit blocks, and classify
each truncated result into Hypothesis A (rag-cli-only) / B (CC inline split) / C (echo artifact,
handled separately as `echo_hits`).
**Reads:** nothing — pure data transforms over passed-in paths/events.
**Writes:** nothing.
**Called by:** `rag_truncation_audit.py`.
**Calls out:** none — stdlib JSONL/regex parsing only.

### rag_truncation_audit_report.py (161 LOC)

**Purpose:** All report section builders (source block, summary, hit table, echo-hits, structural
fingerprint, fixed conclusion) plus the top-level `_build_report` assembler.
**Reads:** classified results / echo hits from `rag_truncation_audit_data.py`.
**Writes:** nothing — returns the report string.
**Called by:** `rag_truncation_audit.py`.
**Calls out:** `rag_truncation_audit_data.py` (`_source_label`).

---

### tag_presence_audit.py (93 LOC)

**Purpose:** CLI entry point — per-REQ, delta-scoped audit for leftover tag occurrences (system-
reminder, task-notification, and two other short tag forms) in `raw_payload.messages` — emits only
REQs with occurrences, pairs each with its `stripped_msg_removed` delta entries to show whether a
tag was stripped or bypassed.
**Reads:** one proxy JSONL path (positional, optional — auto-picks newest opus proxy log under
src/logs).
**Writes:** `dev/tool_use_analysis/md/<timestamp>_tag_presence_audit.md` (`--output` overridable).
**Called by:** none — manual CLI.
**Calls out:** `tag_presence_audit_scan.py`, `tag_presence_audit_report.py`.

### tag_presence_audit_scan.py (389 LOC)

**Purpose:** The SR/TN/ND/PO template catalog + tag regexes (mirrored from `src/proxy/strip_sr.py`),
the streaming per-REQ scanner (`_stream_and_audit`/`_scan_entry`, split into tag-occurrence scanning,
`stripped_msg_removed` captured-chunk scanning, and REQ-block building), and the small lookup helpers
(message-text iteration, SR-inner extraction, template matching, tool-result labeling, indentation).
**Reads:** nothing at module scope — streams the JSONL path passed to `_stream_and_audit`.
**Writes:** nothing.
**Called by:** `tag_presence_audit.py`.
**Calls out:** none — stdlib JSONL/regex parsing only.

### tag_presence_audit_report.py (93 LOC)

**Purpose:** Report builders — header, aggregate tag/SR-template tables, non-SR tag verification
table, and the top-level `_build_report` assembler.
**Reads:** aggregate counters from `tag_presence_audit_scan.py`.
**Writes:** nothing — returns report lines.
**Called by:** `tag_presence_audit.py`.
**Calls out:** `tag_presence_audit_scan.py` (`_SR_TEMPLATES`).

---

### sr_bypass_audit.py (257 LOC)

**Purpose:** Per-template count of bypassed vs. captured system-reminder blocks — scans
`raw_payload.messages` for SR blocks still present after proxy processing (bypassed) and
`stripped_msg_removed` for SR blocks successfully removed (captured), reporting bypass rate per
template.
**Reads:** proxy JSONL paths (positional, optional — default: newest 3 opus proxy logs).
**Writes:** `dev/tool_use_analysis/md/<timestamp>_sr_bypass_audit.md`.
**Called by:** none — manual CLI.
**Calls out:** none — stdlib JSONL parsing only.

---

### strip_audit.py (86 LOC)

**Purpose:** CLI entry point — per-REQ strip-delta audit for one opus proxy log — classifies each
request into five buckets (effective strip, inert firing, index-tracking gap, leak, suspect) using
rule-counter deltas and marker-based chunk attribution.
**Reads:** one proxy JSONL path (positional, optional — auto-picks newest opus proxy log).
**Writes:** `dev/tool_use_analysis/md/<timestamp>_strip_audit.md`.
**Called by:** none — manual CLI.
**Calls out:** `src.proxy.strip_vocab` (`legend_markdown`), `strip_audit_classify.py`,
`strip_audit_report.py`.

### strip_audit_classify.py (222 LOC)

**Purpose:** Loads/filters opus entries, delegates per-REQ EFF/INERT/IDX classification to
`src.proxy.strip_vocab.classify_req`, and builds the verbose LEAK/SUSPECT tag lines (`_check_tags`,
split into an SR-block scan and a simple-tag scan) via `raw_payload` SR-block scanning.
**Reads:** nothing at module scope — `_load_entries` streams the JSONL path passed to it.
**Writes:** nothing.
**Called by:** `strip_audit.py` (indirectly, via `strip_audit_report.py`), `strip_audit_report.py`.
**Calls out:** `src.proxy.strip_vocab` (`RULES`, `classify_req`), `src.proxy.strip_sr`
(`_SR_TEMPLATES`, `_PRESERVE_PREAMBLE`).

### strip_audit_report.py (221 LOC)

**Purpose:** Report builders — header, rule catalog, per-REQ delta-log rendering (split into a REQ
header line and an EFF-section renderer), and the aggregate summary.
**Reads:** classified REQ dicts from `strip_audit_classify.py`.
**Writes:** nothing — returns report lines.
**Called by:** `strip_audit.py`.
**Calls out:** `strip_audit_classify.py` (`_classify_req`, `_TEMPLATE_TO_RULE`, `_SR_TEMPLATES`).

---

### sr_session_audit.py (361 LOC)

**Purpose:** Longitudinal system-reminder audit across all Claude Code session JSONLs — extracts
`<system-reminder>` blocks, classifies against the live strip catalog, and reports known/preserved/
unknown buckets with a date timeline and CC-version attribution to surface which templates have
empirical hits and which are leaking through as gap candidates.
**Reads:** session JSONL files under the user's Claude Code projects directory (optional positional
project-name substring filter).
**Writes:** `dev/tool_use_analysis/md/<timestamp>_sr_session_audit.md`.
**Called by:** none — manual CLI.
**Calls out:** `src.proxy.strip_sr` (`_SR_TEMPLATES`, `_PRESERVE_PREAMBLE`).

---

## Gotchas
- Every generated report opens with a `## Source JSONLs` block (one line per input file, event count,
  deduplicated tool_use-block count) — a project-wide report convention across this directory's
  scripts, not enforced by shared code.
- `strip_audit.py`'s bucket classification depends on `src/proxy/strip_vocab.py`'s marker table
  staying in sync with the real strip rules — a new strip rule without a corresponding marker entry
  shows up as `INERT` or `IDX` rather than `EFF`.
- `strip_audit_report.py`'s `_build_rule_catalog` iterates the live `src.proxy.strip_sr._SR_TEMPLATES`
  against the local `_TEMPLATE_TO_RULE` map in `strip_audit_classify.py` — a template added to
  `_SR_TEMPLATES` without a matching `_TEMPLATE_TO_RULE` entry raises `KeyError` (observed: the
  `agent-types` template, added to `_SR_TEMPLATES` after this map was last updated).
