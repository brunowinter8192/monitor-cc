# dev/sleep_pattern_analysis/

## Role
Empirical analysis of chained-sleep hook block events: classifies the command before the sleep in a blocked Bash chain as trivial-sync, load-bearing or mixed, feeding a rewrite-instead-of-block hook design. Touch when re-auditing hook events; not a regression suite.

## Public Interface
No `__init__.py`. Entry point: `./venv/bin/python dev/sleep_pattern_analysis/analyze.py [--since YYYY-MM-DD] [--out PATH]`.

## Flow
The entry script collects block events from session JSONLs, resolves each to its triggering Bash command, extracts per-sleep context records, builds the Markdown report and appends the classification section.

## Modules

### analyze.py (43 LOC)

**Purpose:** Entry script: parses CLI args and orchestrates event collection, sleep parsing and report generation.
**Reads:** nothing directly; delegates to the event collector.
**Writes:** the report at the `--out` path. Its default path points to a report that no longer exists, so always pass `--out`.
**Called by:** none; manual CLI.
**Calls out:** `sleep_events.py`, `sleep_parsing.py`, `sleep_report.py`.

---

### sleep_events.py (105 LOC)

**Purpose:** Walks session JSONLs and resolves each blocked event to its triggering command through a two-pass id map.
**Reads:** session JSONLs under the user's Claude projects directory.
**Writes:** nothing; returns the event list.
**Called by:** `analyze.py`.
**Calls out:** none.

---

### sleep_parsing.py (108 LOC)

**Purpose:** Extracts per-sleep context records from a triggering command string.
**Reads:** nothing beyond arguments.
**Writes:** nothing; returns records.
**Called by:** `analyze.py`.
**Calls out:** none.

---

### sleep_report.py (127 LOC)

**Purpose:** Builds the Markdown report section by section and delegates the classification section.
**Reads:** nothing beyond arguments.
**Writes:** nothing; returns the report string.
**Called by:** `analyze.py`.
**Calls out:** `classify.py`.

---

### classify.py (88 LOC)

**Purpose:** Holds the token classification sets and appends the classification table to the in-progress report.
**Reads:** nothing.
**Writes:** mutates the caller-owned line list.
**Called by:** `sleep_report.py`.
**Calls out:** none.

---

## State
No persistent state. The report builder and classifier share one caller-owned line list, passed by reference.
