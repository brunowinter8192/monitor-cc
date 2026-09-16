# dev/sleep_pattern_analysis/

## Role
Empirical analysis of `block_chained_sleep` hook firing events — classifies the command token
immediately preceding `sleep N` in a blocked Bash chain as trivial-sync (safe to strip),
load-bearing (keep), or mixed/unclear. Produces the data needed to design a hook that rewrites
violations instead of blocking them. Touch when re-auditing hook events after rule or hook changes,
or expanding the trivial/load-bearing token classification sets.

## Flow
`analyze.py` parses CLI args and orchestrates; `sleep_events.py` walks session JSONL files and
resolves each blocked hook event to its triggering Bash command; `sleep_parsing.py` extracts
per-sleep context records from that command; `sleep_report.py` builds the report and calls
`classify.py`, which supplies the token classification rules and appends the classification
section to that same report.

## Modules

### analyze.py (54 LOC)

**Purpose:** Entry script — parses CLI args and orchestrates event collection, sleep parsing, and
report generation.
**Reads:** nothing directly — delegates to `sleep_events._collect_events`.
**Writes:** `--out` path (default `dev/sleep_pattern_analysis/01_reports/sleep_audit_2026-05-24.md`,
a stale hardcoded fallback — callers should always pass `--out` explicitly).
**Called by:** none — manual CLI.
**Calls out:** `sleep_events`, `sleep_parsing`, `sleep_report`.

---

### sleep_events.py (108 LOC)

**Purpose:** Walks session JSONL files, resolves each `BLOCKED` `block_chained_sleep` event to its
triggering command via a two-pass tool_use_id/uuid map.
**Reads:** session JSONL files under the user's Claude Code projects directory (`PROJECTS_DIR`).
**Writes:** nothing — returns the event list.
**Called by:** `analyze.py`.
**Calls out:** none.

---

### sleep_parsing.py (116 LOC)

**Purpose:** Extracts per-sleep context records (cmd_before, cmd_after, chain_op, in_loop,
is_canonical, in_heredoc) from a triggering command string.
**Reads:** nothing beyond function args.
**Writes:** nothing — returns the record list.
**Called by:** `analyze.py`.
**Calls out:** none.

---

### sleep_report.py (134 LOC)

**Purpose:** Builds the Markdown report section by section from the parsed records and calls
`classify.add_classification()` for the final classification section.
**Reads:** nothing beyond function args.
**Writes:** nothing directly — returns the report string; mutates the `lines` list in place while
building it (same pattern `classify.add_classification()` already used).
**Called by:** `analyze.py`.
**Calls out:** `classify.add_classification()`.

---

### classify.py (92 LOC)

**Purpose:** Token classification constant sets (trivial, load-bearing, mixed-notes) plus
`add_classification()`, which appends the classification table to an in-progress report line list.
**Reads:** nothing — pure constants and logic.
**Writes:** mutates the `lines` list passed in by `sleep_report._build_report()`.
**Called by:** `sleep_report.py`.
**Calls out:** none.

---

## Gotchas
- All cross-file imports here are bare top-level module imports (`from sleep_events import ...`,
  `from classify import ...`), not `dev.sleep_pattern_analysis.x` — this works when invoked as
  `./venv/bin/python dev/sleep_pattern_analysis/analyze.py` from anywhere, since Python adds the
  executed script's own directory to `sys.path[0]`; no `cd` into this directory is required.
- Heredoc body spans are detected and excluded from histograms — `block_chained_sleep.py`'s own regex
  scanner sees `sleep` tokens inside heredoc strings, which would otherwise inflate the counts.
- `cmd_before = (empty)` means sleep is the first command in the chain (sleep-first pattern, not
  strippable — the sleep itself is the timing intent).
