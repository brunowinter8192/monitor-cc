# process-docs/session_analysis/2026-09-16_comment_salvage.md

Session: dev/session_analysis/ module-standards conformance (comment/docstring removal + DOCS.md rewrite).
Date: 2026-09-16.

## Purpose of this file

Every comment and docstring deleted from `dev/session_analysis/*.py` during this milestone,
copied verbatim before deletion, plus the full pre-rewrite content of
`dev/session_analysis/DOCS.md`. Nothing judged and dropped — see the milestone rules in the
calling agent's prompt (module-standards conformance: relocate then delete, decide nothing).

File-count note: the milestone prompt stated "8 .py files"; the actual count in
`dev/session_analysis/` is 24 `.py` files. 16 of the 24 already had zero comments and zero
docstrings before this milestone touched them — 24 minus those 16 is exactly 8, so the prompt's
figure is read as "files with at least one comment/docstring," not the true file count. The
stated comment/docstring totals (33 comments, 3 docstrings) matched exactly what AST+tokenize
measured across all 24 files.

## Load-bearing docstring — the second one found this phase

`04_cache_validation.py` passed its own module docstring to
`argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)`.
The docstring text was moved verbatim into a module-level string constant
(`_MODULE_DOCSTRING` — see the file's INFRASTRUCTURE section) in the exact same position, and the
`description=__doc__` reference was rewired to `description=_MODULE_DOCSTRING`. `--help` output
was diffed before/after the edit and is byte-identical; see the verification note below.

The other two docstrings in this directory (`06_char_token_ratio.py`, `07_quartet_prefix_diff.py`)
are plain narrative — neither script uses `argparse(description=__doc__)` or any other runtime
`__doc__` consumption — confirmed by grep before deletion. Both deleted outright.

## Execution-safety note for this session

`04_cache_validation.py`, `05_req_breakdown.py`, and `06_char_token_ratio.py` all expect the OLD
single-file `raw_payload` proxy-log format, which does not exist on this machine's live proxy
(superseded by the `_original`/`_forwarded`/`_stripped`/`_injected` dual-log quartet under
`src/logs/dual_log/` — confirmed already in this directory's own pre-existing DOCS.md Gotchas).
`06`'s auto-detection (`find_latest_proxy_log`) and `05`'s explicit `--proxy-log` path both hit
this directly. `04`'s `--help` and error-path behavior were verified for real; its main analysis
path was verified against one small synthetic `raw_payload`-shaped fixture built for this session
only (not committed, built and discarded in `/tmp`), per the milestone's own "compare pre/post on
identical synthetic input" allowance — no real file of that vintage exists to test against.

`05_req_breakdown.py` and `06_char_token_ratio.py` both write into a `04_reports/` subdirectory
that does not currently exist on disk — this is a naming mismatch against the real, currently
tracked `dev/session_analysis/md/` directory (which holds this directory's actual historical
reports, including two files matching `05`'s and `06`'s own filename patterns:
`md/20260413_005151_req1.md`, `md/20260417_002739_token_ratios_live.md`). This mismatch predates
this session, was not introduced by it, and was left untouched — out of this milestone's negative
scope (do not change output paths). `07_quartet_prefix_diff.py` is the one script whose
`REPORTS_DIR` genuinely matches the real, tracked `md/` directory; it writes a new timestamped
file there on every run and was run for real against the live `dual_log` corpus and a real
session JSONL — the fresh report it wrote during this session's verification was deleted
afterward, never staged.

Comment/docstring counts confirmed via AST + tokenize before deletion: 33 comments, 3
docstrings, matching the task's stated measured state exactly.

## Salvage from dev/session_analysis/DOCS.md

Full content of dev/session_analysis/DOCS.md as it stood before this rewrite (318 lines),
preserved verbatim since the whole file is being replaced with the mandated leaner format
(Role capped at 50 words, Purpose capped at 25 words per module, no Gotchas section in the
new format, Public Interface / State sections added).

```markdown
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
```

## Salvage from dev/proxy/01_extract.py

COMMENT L60:
```
# Parse CLI arguments
```

COMMENT L68:
```
# Encode project path to match Claude directory naming
```

COMMENT L72:
```
# Find all main session JSONL files across all projects
```

COMMENT L82:
```
# Find main session JSONL files for a specific project path
```

COMMENT L92:
```
# Parse all sessions and return aggregated calls plus per-session summaries
```

COMMENT L102:
```
# Parse one JSONL session file into list of completed tool call dicts
```

COMMENT L121:
```
# Extract tool_use and tool_result blocks from one JSONL message
```

COMMENT L166:
```
# Extract plain text from a tool_result content block
```

COMMENT L176:
```
# Char count of serialized input dict
```

COMMENT L180:
```
# Char count of output string
```

COMMENT L184:
```
# Format aggregate table of tool usage sorted by total chars descending
```

COMMENT L229:
```
# Format per-session breakdown table sorted by total chars descending
```

COMMENT L245:
```
# Extract the key identifying parameter for a tool call
```

COMMENT L259:
```
# Extract HH:MM:SS from ISO timestamp string
```

COMMENT L266:
```
# Format one tool call as a chronological detail line
```

## Salvage from dev/proxy/02_cache_timeline.py

## Salvage from dev/proxy/03_cache_rebuild_context.py

## Salvage from dev/proxy/04_cache_validation.py

DOCSTRING L2-12:
```
Validate proxy cache breakpoint placement and stability.

Reads a proxy JSONL log and shows per-request:
- Our breakpoint positions (system, tools, messages)
- Which messages were modified by proxy rules
- Whether breakpoints are stable between consecutive requests
- Comparison with original CC breakpoints

Usage:
    python3 dev/session_analysis/04_cache_validation.py <proxy_log.jsonl> [--limit N]

```

## Salvage from dev/proxy/05_req_breakdown.py

## Salvage from dev/proxy/06_char_token_ratio.py

DOCSTRING L2-11:
```
Single-session Opus 4.7 char-to-token ratio analysis.

Ratios computed (chars/token, consistent with anchor 3.68 chars/token):
  A) msg-ratio: Δmsg_chars / CC for clean requests (REQ#>=2, no-thinking, Δmsg>0)
  B) prefix-ratio: (sys+tools+msgs chars) / (CC+CR) backsolve from REQ#1 if clean

Filters: Opus only, no-thinking response, streaming dedup.
Auto-detects latest proxy log + session JSONL.
All scripts assume CWD = Monitor_CC/ (project root).

```

## Salvage from dev/proxy/07_quartet_prefix_diff.py

DOCSTRING L2-20:
```
Forensic prefix-diff probe for repeated cache rebuilds.

Reconstructs full payload state (system/tools/messages) at each opus-family
request from a _forwarded dual-log delta chain, aligns it to session-JSONL
ground-truth usage (CR/CC/D) by timestamp, and diffs consecutive requests
segment-by-segment (system[0..3] individually / tools / messages) to find
WHERE a cache-rebuild's byte divergence sits and WHAT changed there.

Input handling note: the forwarded dual-log is delta-encoded (only changed
system/tools/message indices per request) — this is NOT the eliminated
single main-log raw_payload format read by 04/05/06; state must be replayed
by applying deltas cumulatively (mirrors src/proxy_display/forwarded_parser.py).

Usage (from project root):
    ./venv/bin/python dev/session_analysis/07_quartet_prefix_diff.py \
        --forwarded-log src/logs/dual_log/api_requests_opus_<id>_forwarded.jsonl \
        --session-jsonl ~/.claude/projects/<encoded>/session.jsonl \
        --req-range 133-137 --auto-detect

```

## Salvage from dev/proxy/cache_rebuild_context_detect.py

## Salvage from dev/proxy/cache_rebuild_context_parse.py

## Salvage from dev/proxy/cache_rebuild_context_render.py

## Salvage from dev/proxy/cache_timeline_analysis.py

## Salvage from dev/proxy/cache_timeline_parse.py

## Salvage from dev/proxy/cache_timeline_render.py

## Salvage from dev/proxy/char_token_ratio_compute.py

## Salvage from dev/proxy/char_token_ratio_load.py

## Salvage from dev/proxy/char_token_ratio_report.py

COMMENT L9:
```
# 3.68 chars/token
```

## Salvage from dev/proxy/quartet_prefix_diff_diff.py

## Salvage from dev/proxy/quartet_prefix_diff_findings.py

## Salvage from dev/proxy/quartet_prefix_diff_load.py

COMMENT L7:
```
# matches 03_cache_rebuild_context.py REBUILD_THRESHOLD
```

## Salvage from dev/proxy/quartet_prefix_diff_report.py

## Salvage from dev/proxy/req_breakdown_attribution.py

COMMENT L62:
```
# +1 for each \n separator
```

COMMENT L65:
```
# No BP in messages → use full prefix length
```

COMMENT L67:
```
# partial_msgs_json = json.dumps(messages[:M+1]) = "[m0, ..., mM]"
```

COMMENT L68:
```
# Removing the closing ] gives "[m0, ..., mM" which is a prefix of json.dumps(messages)
```

COMMENT L70:
```
# char position after last BP msg content
```

COMMENT L89:
```
# opening `[`
```

COMMENT L95:
```
# `, ` separator
```

COMMENT L129:
```
# default: one is prefix of the other
```

COMMENT L171:
```
# Byte-level comparison
```

COMMENT L176:
```
# Convert byte offset to character offset in new_prefix string
```

COMMENT L179:
```
# Tokenize before drift and from drift to last BP end (all char-based)
```

COMMENT L184:
```
# Context ±CONTEXT_CHARS characters around drift
```

COMMENT L187:
```
# Identify segment (system/tools/messages) the drift falls in, nearest heading if sys[2]
```

COMMENT L190:
```
# KPI
```

## Salvage from dev/proxy/req_breakdown_load.py

COMMENT L22:
```
# skip sent_meta entries
```

COMMENT L44:
```
# Non-assistant events break streaming group (user turn between calls)
```

## Salvage from dev/proxy/req_breakdown_report.py

## Salvage from dev/proxy/req_breakdown_rule_edits.py

