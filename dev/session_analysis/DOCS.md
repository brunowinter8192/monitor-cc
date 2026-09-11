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

## Modules

### 01_extract.py (281 LOC)

**Purpose:** Multi-level tool-call extraction and summary from session JSONL files — all projects,
one project, one session, or one session filtered by tool name (`--project`, `--session`, `--tool`).
**Reads:** session JSONL files under the user's Claude Code projects directory.
**Writes:** a Markdown table of tool-call counts and token usage to stdout.
**Called by:** none — manual CLI.
**Calls out:** none — stdlib JSONL parsing only.

---

### 02_cache_timeline.py (478 LOC)

**Purpose:** Visualizes cache/token behavior turn-by-turn or minute-by-minute across a session or
project, flagging anomalies (large CC spikes, TTL time gaps, CR drops) via `--anomalies-only`,
`--aggregate`, `--project`, or `--workers`.
**Reads:** session JSONL files under the user's Claude Code projects directory.
**Writes:** a Markdown table with anomaly flags and a bar chart to stdout.
**Called by:** none — manual CLI.
**Calls out:** none — stdlib JSONL parsing only.

---

### 03_cache_rebuild_context.py (415 LOC)

**Purpose:** Detects cache rebuilds (CR drops with disproportionate CC spikes) and shows surrounding
message context (`--context N`) for root-cause analysis, across one session or all sessions
(`--all`).
**Reads:** session JSONL files under the user's Claude Code projects directory.
**Writes:** per-rebuild context blocks plus a pattern summary to stdout.
**Called by:** none — manual CLI.
**Calls out:** none — stdlib JSONL parsing only.

---

### 04_cache_validation.py (144 LOC)

**Purpose:** Validates proxy-side cache breakpoint placement and stability — per request, shows
breakpoint positions, which messages carry proxy-modified content, and breakpoint stability between
consecutive requests.
**Reads:** a proxy JSONL log (positional, `--limit`, `--rebuilds-only`).
**Writes:** a per-request breakpoint analysis table to stdout.
**Called by:** none — manual CLI.
**Calls out:** none — stdlib JSONL parsing only.

---

### 05_req_breakdown.py (687 LOC)

**Purpose:** Forensic per-segment token attribution for one API request — tokenizes each system
block, tool definition, and message with `tiktoken` (cl100k_base) and compares against session-JSONL
ground truth (CR/CC/D/Out). With `--prev-proxy-log`, adds cross-session byte-diff attribution of
which prefix segments were cache-read vs. newly created.
**Reads:** a proxy JSONL log (`--proxy-log`) and a session JSONL (`--session-jsonl`) for the same
session; optionally a previous session's proxy log (`--prev-proxy-log`).
**Writes:** `md/<timestamp>_req<N>.md`, path printed to stdout.
**Called by:** none — manual CLI.
**Calls out:** `tiktoken`.

---

### 06_char_token_ratio.py (455 LOC)

**Purpose:** Correlates message char counts with actual API token counts (CR/CC/D) to derive
chars-per-token ratios, single-file or batch mode (`--batch <dir>`) with auto-pairing to session
JSONLs.
**Reads:** one proxy JSONL log (positional) or all logs in a directory (`--batch`); optionally a
session JSONL (`--session-jsonl`) for token-data pairing.
**Writes:** a Markdown table to stdout; a persistent report under `md/` in batch mode.
**Called by:** none — manual CLI.
**Calls out:** none — stdlib JSONL parsing only.

---

### 07_quartet_prefix_diff.py (811 LOC)

**Purpose:** Forensic per-segment prefix diff for cache rebuilds — reconstructs full payload state by
replaying the `_forwarded` dual-log delta chain, aligns to session-JSONL ground truth by timestamp,
and diffs consecutive requests segment-by-segment to find where a rebuild's byte divergence sits.
With `--original-log`, cross-checks each modified message against the `_original` dual-log to
attribute a diff as client-side (already in the incoming request) vs. proxy-side (introduced by a
proxy pass).
**Reads:** a `_forwarded` dual-log JSONL (`--forwarded-log`), a session JSONL (`--session-jsonl`),
optionally a matching `_original` dual-log (`--original-log`).
**Writes:** `md/<timestamp>_quartet_prefix_diff.md`, path printed to stdout.
**Called by:** none — manual CLI.
**Calls out:** none — stdlib JSONL parsing only.

---

## Gotchas
- `07_quartet_prefix_diff.py` never reports cache-control breakpoint marker changes: the forwarded
  delta chain hashes elements with `cache_control` stripped, so a marker-only change never enters the
  delta and true sent breakpoint positions are not derivable from this reconstruction.
- `07_quartet_prefix_diff.py` aligns forwarded-log entries to ground-truth request groups by
  timestamp (two-pointer, monotonic), not by fixed line position — retried/aborted forwarded sends
  are silently absorbed into the next group's match.
