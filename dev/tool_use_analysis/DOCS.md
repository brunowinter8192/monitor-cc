# dev/tool_use_analysis/

## Role

Forensic extraction and analysis of tool_use blocks and system-reminder/task-notification content
from Claude Code sessions and proxy logs. Each script is standalone — no shared library across
scripts. Touch when adding a new audit; error/failure analysis and rule-compliance scoring live in
`dev/tool_use_errors/` instead.

## Public Interface

No `__init__.py` in this directory. Entry path: run each script directly, e.g.
`./venv/bin/python dev/tool_use_analysis/extract_long_calls.py`.

## Flow

Each script reads proxy-log or session JSONL files (positional args, or an auto-picked newest or default set), computes one breakdown (tool-call cost, waste ratio, zero-result search, leftover tag presence, strip effectiveness) and writes a Markdown report to stdout or an auto-dated file under this directory or `md/`.
Scripts over about 400 LOC split into same-directory sibling modules by concern (collection, classification, rendering), imported back into the CLI entry point.

## Modules

### extract_long_calls.py (81 LOC)

**Purpose:** CLI entry point — collects every tool_use block, dedups by id, measures serialized
input size, and ranks by size or by input/output ratio.
**Reads:** proxy JSONL paths under src/logs (positional, variadic).
**Writes:** Markdown report to stdout or `--output` file.
**Called by:** none — manual CLI.
**Calls out:** `extract_long_calls_lib.py`, `extract_long_calls_report.py`.

### extract_long_calls_lib.py (301 LOC)

**Purpose:** Formerly a separate proxy-forensics library, now inlined — dataclasses, JSONL
loading, tool_use/tool_result collection and pairing, filtering, aggregation.
**Reads:** nothing — pure data-model/collection functions over passed-in paths/events.
**Writes:** nothing.
**Called by:** `extract_long_calls.py`, `extract_long_calls_report.py`.
**Calls out:** none — stdlib JSONL parsing only.

### extract_long_calls_report.py (204 LOC)

**Purpose:** All Markdown report builders for both modes — summary tables, prefix-cluster table,
per-call detail sections, and the two top-level assemblers.
**Reads:** tool-use and pair objects from `extract_long_calls_lib.py`.
**Writes:** nothing — returns report strings.
**Called by:** `extract_long_calls.py`.
**Calls out:** `extract_long_calls_lib.py`.

---

### extract_zeros.py (346 LOC)

**Purpose:** Detects every Grep/Glob/Read call that returned a zero result, reporting each call's
input, result, and preceding assistant text.
**Reads:** session JSONL paths (positional, variadic) under the user's Claude Code projects
directory.
**Writes:** Markdown report to stdout or `--output` file.
**Called by:** none — manual CLI.
**Calls out:** none — stdlib JSONL parsing only.

---

### rs_truncation_preserve_replay.py (109 LOC)

**Purpose:** Replay-verifies the role=system strip preserve guard — Read-truncation notices pass
through unchanged, other system noise still reduces to `"."`.
**Reads:** one dual-log `_original.jsonl` path (positional, optional, else a hardcoded default).
**Writes:** console PASS/FAIL summary; a detail table to
`dev/tool_use_analysis/md/rs_truncation_preserve_replay_detail.md`.
**Called by:** none — manual CLI.
**Calls out:** `src.proxy.message_passes`.

---

### extract_transcript.py (164 LOC)

**Purpose:** Chronological tool_use/tool_result transcript from a proxy-log snapshot, marking
`(ERROR)` on failed results, no waste/ratio scoring.
**Reads:** proxy JSONL paths under src/logs (positional, variadic) — highest `message_count` entry
per file.
**Writes:** Markdown report to stdout or `--output` file.
**Called by:** none — manual CLI.
**Calls out:** none — stdlib JSONL parsing only.

---

### extract_patterns.py (71 LOC)

**Purpose:** CLI entry point — pairs tool_use/tool_result, filters to waste calls, normalizes
inputs to grouping signatures, and aggregates into a 6-section report.
**Reads:** proxy JSONL paths under src/logs (positional, variadic).
**Writes:** Markdown report to stdout or `--output` file.
**Called by:** none — manual CLI.
**Calls out:** `extract_patterns_collect.py`, `extract_patterns_report.py`.

### extract_patterns_collect.py (239 LOC)

**Purpose:** Load/dedup/signature-normalize tool_use and tool_result blocks, classify
content-transfer vs. waste vs. failed pairs, and aggregate them.
**Reads:** nothing — pure data transforms over passed-in events.
**Writes:** nothing.
**Called by:** `extract_patterns.py`, `extract_patterns_report.py`.
**Calls out:** none — stdlib JSONL/regex parsing only.

### extract_patterns_wrappers.py (91 LOC)

**Purpose:** Wrapper-candidate naming and complexity classification — prefix extraction, complexity
tier, proposed name derivation, ranked/deduped candidate list.
**Reads:** nothing — pure functions over signature strings and aggregated group dicts.
**Writes:** nothing.
**Called by:** `extract_patterns_report.py`.
**Calls out:** none.

### extract_patterns_report.py (200 LOC)

**Purpose:** All 6 report section renderers (source summary, tool/content-transfer breakdowns,
Bash/other-tool patterns, failed calls, wrapper candidates) plus the assembler.
**Reads:** aggregated stats/pair lists from `extract_patterns_collect.py`.
**Writes:** nothing — returns the report string.
**Called by:** `extract_patterns.py`.
**Calls out:** `extract_patterns_collect.py`, `extract_patterns_wrappers.py`.

---

### waste_repetition.py (290 LOC)

**Purpose:** Extracts deduplicated Bash tool_use blocks from one JSONL snapshot and analyzes waste
by repetition signature and known-shortcut path fragments.
**Reads:** one proxy JSONL path (positional).
**Writes:** Markdown report to stdout.
**Called by:** none — manual CLI.
**Calls out:** none — stdlib JSONL parsing only.

---

### cc_injection_audit.py (282 LOC)

**Purpose:** For each user-role delta message in an opus REQ, checks whether it appears as a real
event in the matching CC session, classifying unmatched ones.
**Reads:** proxy log paths (positional, optional default); CC session JSONL auto-discovered by
mtime or `--cc-session`.
**Writes:** `dev/tool_use_analysis/<timestamp>_cc_injection_catalog.md`.
**Called by:** none — manual CLI.
**Calls out:** none — stdlib JSONL parsing only.

---

### rag_query_audit.py (354 LOC)

**Purpose:** Extracts and Jaccard-clusters rag-cli search calls from opus proxy logs for a
helpfulness evaluation.
**Reads:** proxy JSONL paths under src/logs (positional or default glob).
**Writes:** `dev/tool_use_analysis/<date>_rag_query_audit.md` (`--output` or auto-dated).
**Called by:** none — manual CLI.
**Calls out:** none — stdlib JSONL/regex parsing only.

---

### rag_truncation_audit.py (90 LOC)

**Purpose:** CLI entry point — classifies every truncation-marker occurrence in opus proxy logs by
hypothesis A/B/C using split-position and rag-cli detection.
**Reads:** proxy JSONL paths under src/logs (positional or default glob).
**Writes:** `dev/tool_use_analysis/<date>_rag_truncation_audit.md` (`--output` or auto-dated).
**Called by:** none — manual CLI.
**Calls out:** `rag_truncation_audit_data.py`, `rag_truncation_audit_report.py`.

### rag_truncation_audit_data.py (186 LOC)

**Purpose:** Load proxy JSONL, collect tool_use/truncated-result/echo-hit blocks, and classify each
truncated result into Hypothesis A/B/C.
**Reads:** nothing — pure data transforms over passed-in paths/events.
**Writes:** nothing.
**Called by:** `rag_truncation_audit.py`.
**Calls out:** none — stdlib JSONL/regex parsing only.

### rag_truncation_audit_report.py (154 LOC)

**Purpose:** All report section builders (source, summary, hit table, echo-hits, fingerprint, fixed
conclusion) plus the assembler.
**Reads:** classified results / echo hits from `rag_truncation_audit_data.py`.
**Writes:** nothing — returns the report string.
**Called by:** `rag_truncation_audit.py`.
**Calls out:** `rag_truncation_audit_data.py`.

---

### tag_presence_audit.py (76 LOC)

**Purpose:** CLI entry point — per-REQ delta-scoped audit for leftover SR/TN/ND/PO tags, pairing
each with its `stripped_msg_removed` entries.
**Reads:** one proxy JSONL path (positional, optional — auto-picks newest opus log).
**Writes:** `dev/tool_use_analysis/<timestamp>_tag_presence_audit.md` (`--output` overridable).
**Called by:** none — manual CLI.
**Calls out:** `tag_presence_audit_scan.py`, `tag_presence_audit_report.py`.

### tag_presence_audit_scan.py (360 LOC)

**Purpose:** The SR/TN/ND/PO template catalog and tag regexes, the streaming per-REQ scanner, and
small message/tool-label lookup helpers.
**Reads:** nothing at module scope — streams the JSONL path passed in by the entry script.
**Writes:** nothing.
**Called by:** `tag_presence_audit.py`.
**Calls out:** none — stdlib JSONL/regex parsing only.

### tag_presence_audit_report.py (89 LOC)

**Purpose:** Report builders — header, aggregate tag/SR-template tables, non-SR tag verification
table, and the top-level assembler.
**Reads:** aggregate counters from `tag_presence_audit_scan.py`.
**Writes:** nothing — returns report lines.
**Called by:** `tag_presence_audit.py`.
**Calls out:** `tag_presence_audit_scan.py`.

---

### sr_bypass_audit.py (222 LOC)

**Purpose:** Per-template count of bypassed vs. captured system-reminder blocks, reporting bypass
rate per template per log plus an aggregate.
**Reads:** proxy JSONL paths (positional, optional — default newest 3 opus logs).
**Writes:** `dev/tool_use_analysis/<timestamp>_sr_bypass_audit.md`.
**Called by:** none — manual CLI.
**Calls out:** none — stdlib JSONL parsing only.

---

### strip_audit.py (73 LOC)

**Purpose:** CLI entry point — per-REQ strip-delta audit classifying each request into five buckets
using rule-counter deltas and marker-based attribution.
**Reads:** one proxy JSONL path (positional, optional — auto-picks newest opus log).
**Writes:** `dev/tool_use_analysis/<timestamp>_strip_audit.md`.
**Called by:** none — manual CLI.
**Calls out:** `src.proxy.strip_vocab`, `strip_audit_classify.py`, `strip_audit_report.py`.

### strip_audit_classify.py (198 LOC)

**Purpose:** Loads/filters opus entries, delegates per-REQ EFF/INERT/IDX classification, and builds
LEAK/SUSPECT tag lines via raw-payload SR-block scanning.
**Reads:** nothing at module scope — streams the JSONL path passed in by the entry script.
**Writes:** nothing.
**Called by:** `strip_audit.py`, `strip_audit_report.py`.
**Calls out:** `src.proxy.strip_vocab`, `src.proxy.strip_sr`.

### strip_audit_report.py (211 LOC)

**Purpose:** Report builders — header, rule catalog, per-REQ delta-log rendering, and the aggregate
summary.
**Reads:** classified REQ dicts from `strip_audit_classify.py`.
**Writes:** nothing — returns report lines.
**Called by:** `strip_audit.py`.
**Calls out:** `strip_audit_classify.py`.

---

### sr_session_audit.py (337 LOC)

**Purpose:** Longitudinal system-reminder audit across all Claude Code sessions, classifying blocks
against the live strip catalog into known/preserved/unknown buckets.
**Reads:** session JSONL files under the user's Claude Code projects directory (optional
project-name filter).
**Writes:** `dev/tool_use_analysis/<timestamp>_sr_session_audit.md`.
**Called by:** none — manual CLI.
**Calls out:** `src.proxy.strip_sr`.

---

## State

No shared state across modules — each script resolves its own log directory and output path at
module scope, and no module retains state between runs. Sibling modules pass results as plain
dicts/dataclasses back to their CLI entry point.
