# dev/session_analysis/

## Role
Standalone forensic analysis suite for Claude Code session JSONL and proxy log data —
investigates cache behavior, token attribution, and cache-rebuild root causes. Not part of the
production pipeline. Touch when adding a new forensic angle on cache/token behavior; scripts
assume CWD is the project root.

## Public Interface
No `__init__.py` in this directory. Each numbered `0N_*.py` script is its own entry point, run
directly, e.g. `python3 dev/session_analysis/01_extract.py --session <path>`.

## Flow
Each script reads session JSONL files (under the user's Claude Code projects directory) and/or a
proxy log under `src/logs`, computes one specific breakdown or timeline, and either prints a
Markdown table to stdout or writes a timestamped report to `md/`.

Every numbered script over budget splits into the numbered entry file (kept at its original
path/name) plus sibling modules named `<topic>_<concern>.py` — without the numeric prefix, since a
literal `NN_name` is not a valid Python identifier.

## Modules

### 01_extract.py (266 LOC)

**Purpose:** Multi-level tool-call extraction and summary from session JSONL files — all
projects, one project, one session, or one session filtered by tool name.
**Reads:** session JSONL files under the user's Claude Code projects directory.
**Writes:** a Markdown table of tool-call counts and token usage to stdout.
**Called by:** none — manual CLI.
**Calls out:** none — stdlib JSONL parsing only.

---

### 02_cache_timeline.py (66 LOC)

**Purpose:** Entry point — visualizes cache/token behavior turn-by-turn or minute-by-minute
across a session or project, flagging anomalies.
**Reads:** session JSONL files under the user's Claude Code projects directory.
**Writes:** a Markdown table with anomaly flags and a bar chart to stdout.
**Called by:** none — manual CLI.
**Calls out:** `cache_timeline_parse.py`, `cache_timeline_analysis.py`, `cache_timeline_render.py`.

---

### cache_timeline_parse.py (111 LOC)

**Purpose:** Session-JSONL discovery and per-turn parsing (project path encoding, timestamp
parsing/formatting, assistant-turn extraction and content classification).
**Reads:** nothing at import time; its functions read session JSONL files.
**Writes:** nothing.
**Called by:** `02_cache_timeline.py`, `cache_timeline_analysis.py`, `cache_timeline_render.py`.
**Calls out:** none.

---

### cache_timeline_analysis.py (155 LOC)

**Purpose:** Cache-status classification and anomaly detection (stuck cache, failed resume,
premature TTL, each its own detector) plus time-gap finding.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `02_cache_timeline.py`, `cache_timeline_render.py`.
**Calls out:** `cache_timeline_parse.py`.

---

### cache_timeline_render.py (167 LOC)

**Purpose:** Markdown/table rendering for the timeline, anomalies section, summary, per-minute
bar chart, and per-project session summary.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `02_cache_timeline.py`.
**Calls out:** `cache_timeline_parse.py`, `cache_timeline_analysis.py`.

---

### 03_cache_rebuild_context.py (75 LOC)

**Purpose:** Entry point — detects cache rebuilds (CR drops with disproportionate CC spikes) and
shows surrounding message context for root-cause analysis.
**Reads:** session JSONL files under the user's Claude Code projects directory.
**Writes:** per-rebuild context blocks plus a pattern summary to stdout.
**Called by:** none — manual CLI.
**Calls out:** `cache_rebuild_context_parse.py`, `cache_rebuild_context_detect.py`,
`cache_rebuild_context_render.py`.

---

### cache_rebuild_context_parse.py (143 LOC)

**Purpose:** Session-JSONL discovery and per-message parsing/classification (assistant tool_use,
user prompt tags, timestamp/gap formatting).
**Reads:** nothing at import time; its functions read session JSONL files.
**Writes:** nothing.
**Called by:** `03_cache_rebuild_context.py`, `cache_rebuild_context_detect.py`,
`cache_rebuild_context_render.py`.
**Calls out:** none.

---

### cache_rebuild_context_detect.py (90 LOC)

**Purpose:** Rebuild detection (CR/CC ratio rule) and preceding-event classification for each
detected rebuild.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `03_cache_rebuild_context.py`.
**Calls out:** `cache_rebuild_context_parse.py`.

---

### cache_rebuild_context_render.py (115 LOC)

**Purpose:** Per-rebuild context block rendering plus pattern/delta/session summary tables.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `03_cache_rebuild_context.py`.
**Calls out:** `cache_rebuild_context_parse.py`.

---

### 04_cache_validation.py (159 LOC)

**Purpose:** Validates proxy-side cache breakpoint placement and stability — per request, shows
breakpoint positions, modified messages, and stability between requests.
**Reads:** a proxy JSONL log (positional, `--limit`, `--rebuilds-only`).
**Writes:** a per-request breakpoint analysis table to stdout.
**Called by:** none — manual CLI.
**Calls out:** none — stdlib JSONL parsing only.

---

### 05_req_breakdown.py (55 LOC)

**Purpose:** Entry point — forensic per-segment token attribution for one API request, comparing
`tiktoken` estimates against session-JSONL ground truth.
**Reads:** a proxy JSONL log (`--proxy-log`) and a session JSONL (`--session-jsonl`); optionally
a previous session's proxy log (`--prev-proxy-log`).
**Writes:** `04_reports/<timestamp>_req<N>.md`, path printed to stdout.
**Called by:** none — manual CLI.
**Calls out:** `req_breakdown_load.py`, `req_breakdown_attribution.py`,
`req_breakdown_rule_edits.py`, `req_breakdown_report.py`.

---

### req_breakdown_load.py (144 LOC)

**Purpose:** Loads the target proxy-log entry and session ground truth, and tokenizes
system/tools/messages segments with `tiktoken`.
**Reads:** a proxy JSONL log and a session JSONL.
**Writes:** nothing.
**Called by:** `05_req_breakdown.py`.
**Calls out:** `tiktoken`.

---

### req_breakdown_attribution.py (202 LOC)

**Purpose:** Cross-session byte-level prefix-diff attribution — locates where the current
request's serialized prefix diverges from the previous session's last request.
**Reads:** a previous session's proxy JSONL log.
**Writes:** nothing.
**Called by:** `05_req_breakdown.py`.
**Calls out:** `req_breakdown_load.py`, `tiktoken`.

---

### req_breakdown_rule_edits.py (106 LOC)

**Purpose:** Correlates a prefix-drift finding with shared-rules edits — git log in the session
time window plus rule-file mtime scan.
**Reads:** `~/.claude/shared-rules` (git log + file mtimes), `~/.claude/rules`.
**Writes:** nothing.
**Called by:** `05_req_breakdown.py`.
**Calls out:** `git` (via `subprocess`).

---

### req_breakdown_report.py (242 LOC)

**Purpose:** Builds the full per-request Markdown report (ground truth, segment tables, totals,
attribution, rule-edit correlation, conclusion).
**Reads:** nothing external.
**Writes:** nothing — returns the report string; the caller writes the file.
**Called by:** `05_req_breakdown.py`.
**Calls out:** `req_breakdown_attribution.py`.

---

### 06_char_token_ratio.py (31 LOC)

**Purpose:** Entry point — single-session Opus char-to-token ratio analysis plus a tiktoken
drift comparison; auto-detects the newest proxy log and session JSONL.
**Reads:** the auto-detected proxy JSONL log and session JSONL.
**Writes:** a Markdown report to stdout; a persistent copy under `04_reports/`.
**Called by:** none — manual CLI.
**Calls out:** `char_token_ratio_load.py`, `char_token_ratio_compute.py`,
`char_token_ratio_report.py`.

---

### char_token_ratio_load.py (177 LOC)

**Purpose:** Latest-log/session auto-detection, proxy-row loading, and session-event loading,
paired by positional index.
**Reads:** proxy JSONL logs under `src/logs/`, session JSONLs under the Claude projects
directory.
**Writes:** nothing.
**Called by:** `06_char_token_ratio.py`.
**Calls out:** none.

---

### char_token_ratio_compute.py (76 LOC)

**Purpose:** Computes the msg-delta and prefix-backsolve chars/token ratios, and the tiktoken
drift estimate per request.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `06_char_token_ratio.py`.
**Calls out:** `tiktoken`.

---

### char_token_ratio_report.py (176 LOC)

**Purpose:** Builds the full ratio-analysis Markdown report and writes it under `04_reports/`.
**Reads:** nothing external.
**Writes:** `04_reports/<timestamp>_token_ratios_live.md`.
**Called by:** `06_char_token_ratio.py`.
**Calls out:** none.

---

### 07_quartet_prefix_diff.py (67 LOC)

**Purpose:** Entry point — forensic per-segment prefix diff for cache rebuilds: replays the
`_forwarded` dual-log delta chain and diffs consecutive requests.
**Reads:** a `_forwarded` dual-log JSONL, a session JSONL, optionally a matching `_original`
dual-log.
**Writes:** `md/<timestamp>_quartet_prefix_diff.md`, path printed to stdout.
**Called by:** none — manual CLI.
**Calls out:** `quartet_prefix_diff_load.py`, `quartet_prefix_diff_diff.py`,
`quartet_prefix_diff_report.py`.

---

### quartet_prefix_diff_load.py (185 LOC)

**Purpose:** Ground-truth grouping, forwarded-delta-chain replay, original-log flow_id lookup,
timestamp-based request mapping, and rebuild-pair detection.
**Reads:** nothing at import time; its functions read the forwarded/original dual-logs and
session JSONL.
**Writes:** nothing.
**Called by:** `07_quartet_prefix_diff.py`, `quartet_prefix_diff_report.py`.
**Calls out:** none.

---

### quartet_prefix_diff_diff.py (221 LOC)

**Purpose:** The segment diff engine — system-block diff, message-content classification,
per-message row diff, client/proxy attribution, CR/CC reconciliation.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `07_quartet_prefix_diff.py`.
**Calls out:** `tiktoken`.

---

### quartet_prefix_diff_report.py (216 LOC)

**Purpose:** Builds the report header/methodology, CR-collapse-points section, pairs-analyzed
section, and the full per-pair section.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `07_quartet_prefix_diff.py`.
**Calls out:** `quartet_prefix_diff_load.py`, `quartet_prefix_diff_findings.py`.

---

### quartet_prefix_diff_findings.py (147 LOC)

**Purpose:** Builds the closing proven-vs-hypothesis findings summary (image/system/tools
stability flags, attribution rollup, recovery identity, interpretation).
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `quartet_prefix_diff_report.py`.
**Calls out:** none.

---

## State
No persistent state lives in this directory. Every script reads its input fresh on every run and
either prints to stdout or writes a fresh timestamped report; `05_req_breakdown.py` and
`06_char_token_ratio.py` write into a `04_reports/` subdirectory that does not currently exist
(mismatched from the real, tracked `md/` directory — a pre-existing inconsistency, not introduced
or fixed by this pass).
