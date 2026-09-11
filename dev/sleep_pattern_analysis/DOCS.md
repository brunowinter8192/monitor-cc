# dev/sleep_pattern_analysis/

## Role
Empirical analysis of `block_chained_sleep` hook firing events — classifies the command token
immediately preceding `sleep N` in a blocked Bash chain as trivial-sync (safe to strip),
load-bearing (keep), or mixed/unclear. Produces the data needed to design a hook that rewrites
violations instead of blocking them. Touch when re-auditing hook events after rule or hook changes,
or expanding the trivial/load-bearing token classification sets.

## Flow
`analyze.py` walks session JSONL files, resolves each blocked hook event to its triggering Bash
command, and builds a report; `classify.py` supplies the token classification rules and appends the
classification section to that same report.

## Modules

### analyze.py (361 LOC)

**Purpose:** Orchestrates the full audit — walks session JSONL files, resolves each `BLOCKED`
`block_chained_sleep` event to its triggering command via a two-pass tool_use_id/uuid map, extracts
per-sleep context records, and produces the Markdown report.
**Reads:** session JSONL files under the user's Claude Code projects directory.
**Writes:** `--out` path (default `md/sleep_audit_<date>.md`).
**Called by:** none — manual CLI.
**Calls out:** `classify.add_classification()`.

---

### classify.py (92 LOC)

**Purpose:** Token classification constant sets (trivial, load-bearing, mixed-notes) plus
`add_classification()`, which appends the classification table to an in-progress report line list.
**Reads:** nothing — pure constants and logic.
**Writes:** mutates the `lines` list passed in by `analyze._build_report()`.
**Called by:** `analyze.py`.
**Calls out:** none.

---

## Gotchas
- Must be run from `dev/sleep_pattern_analysis/` (`cd` there first) so `import classify` resolves —
  `classify.py` is imported as a bare top-level module, not `dev.sleep_pattern_analysis.classify`.
- Heredoc body spans are detected and excluded from histograms — `block_chained_sleep.py`'s own regex
  scanner sees `sleep` tokens inside heredoc strings, which would otherwise inflate the counts.
- `cmd_before = (empty)` means sleep is the first command in the chain (sleep-first pattern, not
  strippable — the sleep itself is the timing intent).
