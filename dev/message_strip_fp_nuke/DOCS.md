# dev/message_strip_fp_nuke/

## Role
Measurement-only audit for the false-positive-nuke bug class inside tool-result content: which strip passes remove text from a tool-result block, split into the system-reminder family and unrelated passes. Strip behavior itself lives in `src/proxy/`.

## Public Interface
No `__init__.py`. Entry point: `python3 dev/message_strip_fp_nuke/audit_tool_result_sr_strips.py`.

## Flow
Streams every recorded request payload from the dual log, threads it through the real per-message passes in production order, records every removal from a tool-result block classified by template, and writes a findings report to `md/`.

## Modules

### audit_tool_result_sr_strips.py (19 LOC)

**Purpose:** Entry point wiring corpus scanning and report rendering into one run.
**Reads:** nothing directly; delegates to the scanner.
**Writes:** nothing directly; delegates to the report module.
**Called by:** none; manual CLI.
**Calls out:** `audit_scan.py`, `audit_report.py`.

---

### audit_scan.py (275 LOC)

**Purpose:** Loads the real proxy strip passes and registries, threads every request through them in order and records removals from tool-result blocks.
**Reads:** all `*_original.jsonl` files under the main checkout's dual log (gitignored runtime data).
**Writes:** nothing; returns data structures.
**Called by:** `audit_tool_result_sr_strips.py`, `audit_report.py`.
**Calls out:** several `src.proxy` pass and strip modules via `importlib`.

---

### audit_report.py (381 LOC)

**Purpose:** Renders the collected occurrence and ground-truth data into the Markdown findings report.
**Reads:** scanner output; the manual verdict table.
**Writes:** `md/audit_tool_result_sr_strips.md`.
**Called by:** `audit_tool_result_sr_strips.py`.
**Calls out:** `audit_scan.py`, `audit_verdicts.py`.

---

### audit_verdicts.py (42 LOC)

**Purpose:** Hand-written verdict table (quoted data, genuine CC injection, ambiguous) filled in after reviewing a first run.
**Reads:** nothing.
**Writes:** nothing; pure data.
**Called by:** `audit_report.py`.
**Calls out:** none.

---

## State
No persistent state. The verdict table is the one piece of hand-maintained data; it is read on every run and written by no script.
