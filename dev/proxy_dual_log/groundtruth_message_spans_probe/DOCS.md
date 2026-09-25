# dev/proxy_dual_log/groundtruth_message_spans_probe/

## Role
Validates the ground-truth span-construction algorithm that replaces blind diffing for messages.
One unit of `dev/proxy_dual_log/` (see the area's own DOCS.md); split out because its 4 files
import only each other.

## Public Interface
No `__init__.py` in this directory. Entry path: `./venv/bin/python
dev/proxy_dual_log/groundtruth_message_spans_probe/groundtruth_message_spans_probe.py`.

## Flow
Two hardcoded recorded `_original.jsonl` payloads (currently rotated off disk) are re-run through
the real `apply_modification_rules`; each of 4 fixed cases is scored by both the ground-truth
algorithm and the current-production diff baseline, and every section is written to one
timestamped Markdown report.

## Modules

### groundtruth_message_spans_probe.py (91 LOC)

**Purpose:** CLI entry point validating the ground-truth span-construction algorithm that replaces
blind diffing for messages.
**Reads:** recorded `_original.jsonl` dual-log payloads (re-runs `apply_modification_rules` on them).
**Writes:** `groundtruth_message_spans_probe_reports/groundtruth_spans_<timestamp>.md` (the reports
directory stays at the area root, `dev/proxy_dual_log/`, not in this subfolder).
**Called by:** none — manual, one-off design-validation probe.
**Calls out:** `groundtruth_spans_cases.py`, `_report.py`.

---

### groundtruth_spans_algorithm.py (165 LOC)

**Purpose:** The ground-truth algorithm under test, the current-production diff baseline, minimal
src/ mirror helpers, and fidelity checks.
**Reads:** nothing — pure text/span functions.
**Writes:** nothing.
**Called by:** `groundtruth_spans_cases.py`, `_report.py`.
**Calls out:** none.

---

### groundtruth_spans_cases.py (175 LOC)

**Purpose:** `apply_modification_rules` re-run wrapper and the 4 real-log case builders.
**Reads:** recorded `_original.jsonl`/`_forwarded.jsonl` dual-log payloads (two hardcoded stems).
**Writes:** nothing — returns case dicts.
**Called by:** `groundtruth_message_spans_probe.py`.
**Calls out:** `src.proxy.rules`; `groundtruth_spans_algorithm.py`.

---

### groundtruth_spans_report.py (244 LOC)

**Purpose:** Runs one case through both algorithms and builds every report section (summary,
per-case detail, fidelity, conclusion).
**Reads:** case dicts from `groundtruth_spans_cases.py`.
**Writes:** nothing — appends to the caller's line list.
**Called by:** `groundtruth_message_spans_probe.py`.
**Calls out:** `groundtruth_spans_algorithm.py`.

---

## State
No shared or mutating state. The entry and cases modules each resolve the area root independently; the corpus lookup falls back to the main checkout because the corpus is gitignored. Both hardcoded stems are rotated off disk; each case loader's failure is caught individually and reported as an error line (see process-docs).
