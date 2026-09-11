# dev/tool_use_analysis/

## Role
Forensic extraction and analysis of tool_use blocks and system-reminder/task-notification content
from Claude Code sessions and proxy logs. Each script is standalone (no shared library — small
per-script helpers are inlined rather than factored out). Error/failure analysis and rule-compliance
scoring have moved to `dev/tool_use_errors/`.

## Flow
Each script reads one or more proxy-log or session JSONL files (positional args, or an auto-picked
newest/default set), computes one specific breakdown, and writes a Markdown report to `md/` or
stdout.

## Modules

### extract_long_calls.py (587 LOC)

**Purpose:** Collects every `tool_use` block from proxy JSONL files, deduplicates by id, measures
serialized input size in characters, and ranks by size — identifies which tool calls burn the most
context budget. `--tool` filters by name (adds command-prefix clustering for Bash); `--ratio` reports
input/output ratio per matched tool_use/tool_result pair instead.
**Reads:** proxy JSONL paths under src/logs (positional, variadic).
**Writes:** Markdown report to stdout or `--output` file.
**Called by:** none — manual CLI.
**Calls out:** none — stdlib JSONL parsing only.

---

### extract_zeros.py (351 LOC)

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

### extract_patterns.py (621 LOC)

**Purpose:** Pairs every `tool_use` with its `tool_result`, filters to waste calls (ratio ≥ 3, input
≥ 50 chars), normalizes inputs to grouping signatures (paths, log filenames, bead IDs, hex IDs,
timestamps, long strings), and aggregates by `(tool_name, signature)` into a 6-section report
including wrapper-script candidates.
**Reads:** proxy JSONL paths under src/logs (positional, variadic).
**Writes:** Markdown report to stdout or `--output` file.
**Called by:** none — manual CLI.
**Calls out:** none — stdlib JSONL parsing only.

---

### waste_repetition.py (294 LOC)

**Purpose:** Extracts deduplicated Bash `tool_use` blocks from a single JSONL file's cumulative
snapshot and analyzes waste two ways: repetition-signature groups (normalized command signature,
ranked by count × avg_chars) and known-shortcut path fragments (absolute paths replaceable with `~`
or a project alias).
**Reads:** one proxy JSONL path (positional).
**Writes:** Markdown report to stdout.
**Called by:** none — manual CLI.
**Calls out:** none — stdlib JSONL parsing only.

---

### cc_injection_audit.py (306 LOC)

**Purpose:** For each user-role message in an opus request's delta range, checks whether it appears
as a real user event in the matching CC session JSONL — unmatched messages are CC-injected,
classified by prefix pattern into a catalog of injection types.
**Reads:** proxy log paths (positional, optional — default: newest 5 opus proxy logs under src/logs);
CC session JSONL auto-discovered by mtime proximity, or `--cc-session`.
**Writes:** `dev/tool_use_analysis/md/<timestamp>_cc_injection_catalog.md`.
**Called by:** none — manual CLI.
**Calls out:** none — stdlib JSONL parsing only.

---

### rag_query_audit.py (350 LOC)

**Purpose:** Extracts and clusters rag-cli search calls from opus proxy logs for a helpfulness
evaluation — parses `rag-cli <verb> "<query>" <collection>` invocations (including compound bash
chains) and Jaccard-clusters queries above a threshold.
**Reads:** proxy JSONL paths under src/logs (positional or default glob
`api_requests_opus_monitor_cc_*.jsonl`).
**Writes:** `dev/tool_use_analysis/<date>_rag_query_audit.md` (`--output` or auto-dated).
**Called by:** none — manual CLI.
**Calls out:** none — stdlib JSONL/regex parsing only.

---

### rag_truncation_audit.py (413 LOC)

**Purpose:** Classifies every `[N characters truncated]` occurrence in opus proxy logs by hypothesis
(A/B/C) — checks where the truncation marker sits as a fraction of total content length to
distinguish CC's inline 5k/5k split from other truncation mechanisms, and whether the truncated call
was a rag-cli search.
**Reads:** proxy JSONL paths under src/logs (positional or default glob, 15 files).
**Writes:** `dev/tool_use_analysis/<date>_rag_truncation_audit.md` (`--output` or auto-dated).
**Called by:** none — manual CLI.
**Calls out:** none — stdlib JSONL/regex parsing only.

---

### tag_presence_audit.py (510 LOC)

**Purpose:** Per-REQ, delta-scoped audit for leftover tag occurrences (system-reminder, task-
notification, and two other short tag forms) in `raw_payload.messages` — emits only REQs with
occurrences, pairs each with its `stripped_msg_removed` delta entries to show whether a tag was
stripped or bypassed.
**Reads:** one proxy JSONL path (positional, optional — auto-picks newest opus proxy log under
src/logs).
**Writes:** `dev/tool_use_analysis/md/<timestamp>_tag_presence_audit.md` (`--output` overridable).
**Called by:** none — manual CLI.
**Calls out:** none — stdlib JSONL parsing only.

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

### strip_audit.py (502 LOC)

**Purpose:** Per-REQ strip-delta audit for one opus proxy log — classifies each request into five
buckets (effective strip, inert firing, index-tracking gap, leak, suspect) using rule-counter deltas
and marker-based chunk attribution.
**Reads:** one proxy JSONL path (positional, optional — auto-picks newest opus proxy log).
**Writes:** `dev/tool_use_analysis/md/<timestamp>_strip_audit.md`.
**Called by:** none — manual CLI.
**Calls out:** `src.proxy.strip_vocab` (rule/tag catalog and chunk-attribution logic).

---

### sr_session_audit.py (336 LOC)

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
