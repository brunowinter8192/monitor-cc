# dev/session_analysis/

## Role
Standalone forensic analysis suite for Claude Code session JSONL and proxy log data — investigates
cache behavior, token attribution, and cache-rebuild root causes. Scripts are not part of the
production pipeline: they read raw data files directly and write Markdown reports or print to
stdout. Touch when adding a new forensic angle on cache/token behavior; all scripts assume CWD is the
project root.

## Flow
Each script reads session JSONL files (under the user's Claude Code projects directory) and/or a
proxy log under src/logs, computes one specific breakdown or timeline, and either prints a Markdown
table to stdout or writes a timestamped report to `md/`.

Every numbered script over the 400-LOC/50-line-function budget splits into the numbered entry file
(kept at its original path/name, so `./venv/bin/python dev/session_analysis/0N_*.py` still works
unchanged) plus sibling modules named `<topic>_<concern>.py` — WITHOUT the numeric prefix, since a
literal `NN_name` is not a valid Python identifier and can't be the target of a `from NN_name import
x` statement (digits can't lead a name). Entry scripts import their siblings with plain
`from <topic>_<concern> import name`, matching the import style already used across `dev/`.

## Modules

### 01_extract.py (281 LOC)

**Purpose:** Multi-level tool-call extraction and summary from session JSONL files — all projects,
one project, one session, or one session filtered by tool name (`--project`, `--session`, `--tool`).
**Reads:** session JSONL files under the user's Claude Code projects directory.
**Writes:** a Markdown table of tool-call counts and token usage to stdout.
**Called by:** none — manual CLI.
**Calls out:** none — stdlib JSONL parsing only.

---

### 02_cache_timeline.py (66 LOC)

**Purpose:** Entry point — visualizes cache/token behavior turn-by-turn or minute-by-minute across a
session or project, flagging anomalies via `--anomalies-only`, `--aggregate`, `--project`, or
`--workers`.
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

**Purpose:** Cache-status classification and anomaly detection (STUCK_CACHE, FAILED_RESUME,
PREMATURE_TTL, each its own detector) plus time-gap finding.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `02_cache_timeline.py`, `cache_timeline_render.py`.
**Calls out:** `cache_timeline_parse.py`.

---

### cache_timeline_render.py (167 LOC)

**Purpose:** Markdown/table rendering for the timeline, anomalies section, summary, per-minute bar
chart, and per-project session summary.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `02_cache_timeline.py`.
**Calls out:** `cache_timeline_parse.py`, `cache_timeline_analysis.py`.

---

### 03_cache_rebuild_context.py (75 LOC)

**Purpose:** Entry point — detects cache rebuilds (CR drops with disproportionate CC spikes) and
shows surrounding message context (`--context N`) for root-cause analysis, across one session or all
sessions (`--all`).
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

### 04_cache_validation.py (158 LOC)

**Purpose:** Validates proxy-side cache breakpoint placement and stability — per request, shows
breakpoint positions, which messages carry proxy-modified content, and breakpoint stability between
consecutive requests.
**Reads:** a proxy JSONL log (positional, `--limit`, `--rebuilds-only`).
**Writes:** a per-request breakpoint analysis table to stdout.
**Called by:** none — manual CLI.
**Calls out:** none — stdlib JSONL parsing only.

---

### 05_req_breakdown.py (55 LOC)

**Purpose:** Entry point — forensic per-segment token attribution for one API request, tokenizing
each system block/tool definition/message with `tiktoken` and comparing against session-JSONL ground
truth; with `--prev-proxy-log`, adds cross-session byte-diff prefix attribution.
**Reads:** a proxy JSONL log (`--proxy-log`) and a session JSONL (`--session-jsonl`) for the same
session; optionally a previous session's proxy log (`--prev-proxy-log`).
**Writes:** `04_reports/<timestamp>_req<N>.md`, path printed to stdout.
**Called by:** none — manual CLI.
**Calls out:** `req_breakdown_load.py`, `req_breakdown_attribution.py`, `req_breakdown_rule_edits.py`,
`req_breakdown_report.py`.

---

### req_breakdown_load.py (145 LOC)

**Purpose:** Loads the target proxy-log entry and session ground truth (CR/CC/D/Out), and tokenizes
system/tools/messages segments with `tiktoken`.
**Reads:** a proxy JSONL log and a session JSONL.
**Writes:** nothing.
**Called by:** `05_req_breakdown.py`.
**Calls out:** `tiktoken`.

---

### req_breakdown_attribution.py (210 LOC)

**Purpose:** Cross-session byte-level prefix-diff attribution — locates the first byte where the
current request's serialized prefix diverges from the previous session's last request, converts to a
token-estimate KPI, and locates the diverging segment/nearest heading.
**Reads:** a previous session's proxy JSONL log (`load_last_opus_entry`).
**Writes:** nothing.
**Called by:** `05_req_breakdown.py`.
**Calls out:** `req_breakdown_load.py` (`ENC`), `tiktoken`.

---

### req_breakdown_rule_edits.py (106 LOC)

**Purpose:** Correlates a prefix-drift finding with shared-rules edits — git log in the session time
window plus rule-file mtime scan, cross-checked against the drift context text.
**Reads:** `~/.claude/shared-rules` (git log + file mtimes), `~/.claude/rules`.
**Writes:** nothing.
**Called by:** `05_req_breakdown.py`.
**Calls out:** `git` (via `subprocess`).

---

### req_breakdown_report.py (242 LOC)

**Purpose:** Builds the full per-request Markdown report (ground truth, segment tables, totals,
prefix attribution, rule-edit correlation, conclusion), section by section.
**Reads:** nothing external.
**Writes:** nothing — returns the report string; the caller writes the file.
**Called by:** `05_req_breakdown.py`.
**Calls out:** `req_breakdown_attribution.py` (`KPI_THRESHOLD`).

---

### 06_char_token_ratio.py (41 LOC)

**Purpose:** Entry point — single-session Opus char-to-token ratio analysis (msg-delta ratio and
REQ#1 prefix-ratio backsolve), plus a tiktoken cl100k_base drift comparison against actual API token
counts. Auto-detects the newest opus proxy log under `src/logs/` and the newest non-agent session
JSONL under the current project's Claude directory — no CLI arguments.
**Reads:** the auto-detected proxy JSONL log and session JSONL.
**Writes:** a Markdown report to stdout; a persistent copy under `04_reports/`.
**Called by:** none — manual CLI.
**Calls out:** `char_token_ratio_load.py`, `char_token_ratio_compute.py`, `char_token_ratio_report.py`.

---

### char_token_ratio_load.py (177 LOC)

**Purpose:** Latest-log/session auto-detection, proxy-row loading (char counts per segment), and
session-event loading (deduplicated assistant usage tuples), paired by positional index.
**Reads:** proxy JSONL logs under `src/logs/`, session JSONLs under the Claude projects directory.
**Writes:** nothing.
**Called by:** `06_char_token_ratio.py`.
**Calls out:** none.

---

### char_token_ratio_compute.py (76 LOC)

**Purpose:** Computes the msg-delta and prefix-backsolve chars/token ratios, and the tiktoken
cl100k_base drift estimate per request.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `06_char_token_ratio.py`.
**Calls out:** `tiktoken`.

---

### char_token_ratio_report.py (176 LOC)

**Purpose:** Builds the full ratio-analysis Markdown report (sources/accounting, prefix/msg-ratio,
tiktoken drift, raw data table) and writes it under `04_reports/`.
**Reads:** nothing external.
**Writes:** `dev/session_analysis/04_reports/<timestamp>_token_ratios_live.md`.
**Called by:** `06_char_token_ratio.py`.
**Calls out:** none.

---

### 07_quartet_prefix_diff.py (86 LOC)

**Purpose:** Entry point — forensic per-segment prefix diff for cache rebuilds: reconstructs full
payload state by replaying the `_forwarded` dual-log delta chain, aligns to session-JSONL ground
truth by timestamp, and diffs consecutive requests segment-by-segment.
**Reads:** a `_forwarded` dual-log JSONL (`--forwarded-log`), a session JSONL (`--session-jsonl`),
optionally a matching `_original` dual-log (`--original-log`).
**Writes:** `md/<timestamp>_quartet_prefix_diff.md`, path printed to stdout.
**Called by:** none — manual CLI.
**Calls out:** `quartet_prefix_diff_load.py`, `quartet_prefix_diff_diff.py`,
`quartet_prefix_diff_report.py`.

---

### quartet_prefix_diff_load.py (185 LOC)

**Purpose:** Ground-truth grouping from session JSONL, forwarded-delta-chain replay (state
reconstruction), original-log flow_id lookup, timestamp-based request/state mapping, and
rebuild-pair detection/selection.
**Reads:** nothing at import time; its functions read the forwarded/original dual-logs and session
JSONL.
**Writes:** nothing.
**Called by:** `07_quartet_prefix_diff.py`, `quartet_prefix_diff_report.py` (`REBUILD_CR_RATIO_THRESHOLD`).
**Calls out:** none.

---

### quartet_prefix_diff_diff.py (221 LOC)

**Purpose:** The segment diff engine — system-block diff, message-content classification (image
eviction, format normalization), per-message row diff (modified/added/removed), client-side-vs-
proxy-side original attribution, CR/CC reconciliation, and the full per-pair analysis assembly.
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `07_quartet_prefix_diff.py`.
**Calls out:** `tiktoken`.

---

### quartet_prefix_diff_report.py (216 LOC)

**Purpose:** Builds the report header/methodology, CR-collapse-points section, pairs-analyzed
section, and the full per-pair section (system/tools/messages tables, original attribution,
segment/reconciliation).
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `07_quartet_prefix_diff.py`.
**Calls out:** `quartet_prefix_diff_load.py` (`REBUILD_CR_RATIO_THRESHOLD`),
`quartet_prefix_diff_findings.py`.

---

### quartet_prefix_diff_findings.py (147 LOC)

**Purpose:** Builds the closing proven-vs-hypothesis findings summary (image/system/tools stability
flags, original-attribution client-vs-proxy rollup, recovery-identity per pair, interpretation
section).
**Reads:** nothing external.
**Writes:** nothing.
**Called by:** `quartet_prefix_diff_report.py`.
**Calls out:** none.

---

## Gotchas
- `07_quartet_prefix_diff.py` never reports cache-control breakpoint marker changes: the forwarded
  delta chain hashes elements with `cache_control` stripped, so a marker-only change never enters the
  delta and true sent breakpoint positions are not derivable from this reconstruction.
- `07_quartet_prefix_diff.py` aligns forwarded-log entries to ground-truth request groups by
  timestamp (two-pointer, monotonic), not by fixed line position — retried/aborted forwarded sends
  are silently absorbed into the next group's match.
- `04_cache_validation.py`, `05_req_breakdown.py`, and `06_char_token_ratio.py` all read the OLD
  single-file `raw_payload` proxy-log format, which no longer exists on a live proxy (superseded by
  the `_original`/`_forwarded`/`_stripped`/`_injected` dual-log quartet under `src/logs/dual_log/`,
  the format `07_quartet_prefix_diff.py` reads instead) — a fixed/replayed single-file log is still
  needed to exercise these three scripts.
