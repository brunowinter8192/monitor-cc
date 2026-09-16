# dev/sleep_pattern_analysis/

## Role
Empirical analysis of `block_chained_sleep` hook events — classifies the command token before `sleep N` in a blocked Bash chain as trivial-sync, load-bearing, or mixed/unclear, feeding a rewrite-instead-of-block hook design. Touch when re-auditing hook events or expanding the classification sets; not a regression suite.

## Public Interface
No `__init__.py` in this directory. Entry point is direct invocation: `./venv/bin/python dev/sleep_pattern_analysis/analyze.py [--since YYYY-MM-DD] [--out PATH]`.

## Flow
`analyze.py` parses CLI args and orchestrates; `sleep_events.py` walks session JSONL files and resolves each blocked hook event to its triggering Bash command; `sleep_parsing.py` extracts per-sleep context records from that command; `sleep_report.py` builds the report and calls `classify.py`, which supplies the token classification rules and appends the classification section to that same report.

## Modules

### analyze.py (43 LOC)

**Purpose:** Entry script — parses CLI args and orchestrates event collection, sleep parsing, and report generation.
**Reads:** nothing directly — delegates to `sleep_events._collect_events`.
**Writes:** `--out` path (default `dev/sleep_pattern_analysis/01_reports/sleep_audit_2026-05-24.md`, a stale hardcoded fallback — callers should always pass `--out` explicitly).
**Called by:** none — manual CLI.
**Calls out:** `sleep_events`, `sleep_parsing`, `sleep_report`.

---

### sleep_events.py (105 LOC)

**Purpose:** Walks session JSONL files, resolves each `BLOCKED` `block_chained_sleep` event to its triggering command via a two-pass tool_use_id/uuid map.
**Reads:** session JSONL files under the user's Claude Code projects directory (`PROJECTS_DIR`).
**Writes:** nothing — returns the event list.
**Called by:** `analyze.py`.
**Calls out:** none.

---

### sleep_parsing.py (108 LOC)

**Purpose:** Extracts per-sleep context records (cmd_before, cmd_after, chain_op, in_loop, is_canonical, in_heredoc) from a triggering command string.
**Reads:** nothing beyond function args.
**Writes:** nothing — returns the record list.
**Called by:** `analyze.py`.
**Calls out:** none.

---

### sleep_report.py (127 LOC)

**Purpose:** Builds the Markdown report section by section from the parsed records and calls `classify.add_classification()` for the final classification section.
**Reads:** nothing beyond function args.
**Writes:** nothing directly — returns the report string; mutates the caller-owned `lines` list in place while building it.
**Called by:** `analyze.py`.
**Calls out:** `classify.add_classification()`.

---

### classify.py (88 LOC)

**Purpose:** Token classification constant sets (trivial, load-bearing, mixed-notes) plus `add_classification()`, which appends the classification table to an in-progress report line list.
**Reads:** nothing — pure constants and logic.
**Writes:** mutates the caller-owned `lines` list passed in by `sleep_report._build_report()`.
**Called by:** `sleep_report.py`.
**Calls out:** none.

---

## State
No module owns persistent state. `sleep_report.py` and `classify.py` both mutate the same `lines` list — built and owned by `sleep_report._build_report()`, passed by reference into `classify.add_classification()` for the final section, never read back except to join into the returned report string.
