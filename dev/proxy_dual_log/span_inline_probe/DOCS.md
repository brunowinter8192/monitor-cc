# dev/proxy_dual_log/span_inline_probe/

## Role
Compares the Form A vs Form B inline-render data model on one fixed recorded session's blocks. One
unit of `dev/proxy_dual_log/` (see the area's own DOCS.md); split out because its 4 files import
only each other.

## Public Interface
No `__init__.py` in this directory. Entry path: `./venv/bin/python
dev/proxy_dual_log/span_inline_probe/span_inline_probe.py`.

## Flow
One hardcoded recorded session's original/forwarded dual-log files (currently rotated off disk)
are matched and diffed via the real `src/proxy/diff_engine.py`; three representative blocks are
located and rendered both ways into one dated Markdown report.

## Modules

### span_inline_probe.py (73 LOC)

**Purpose:** CLI entry point for the Form A vs Form B inline-render data model probe, comparing
them on one fixed recorded session's blocks.
**Reads:** a fixed recorded session's dual-log files (hardcoded session reference).
**Writes:** `span_inline_probe_reports/<YYYYMMDD>.md` (the reports directory stays at the area
root, `dev/proxy_dual_log/`, not in this subfolder, via a literal path string unaffected by this
module's own location).
**Called by:** none — manual, one-off design-validation probe.
**Calls out:** `src.proxy.diff_engine` (loaded via `importlib`); `span_inline_probe_reconstruct.py`,
`_blocks.py`, `_report.py`.

---

### span_inline_probe_reconstruct.py (88 LOC)

**Purpose:** JSONL loading, per-model-family forwarded-delta chain reconstruction, and
original/forwarded request matching.
**Reads:** JSONL file objects passed in by the caller.
**Writes:** nothing — pure data transforms.
**Called by:** `span_inline_probe.py`.
**Calls out:** none.

---

### span_inline_probe_blocks.py (108 LOC)

**Purpose:** Locates the three representative probe blocks (sys full-replace, sys strip-to-dot,
message word-level-mixed) in a matched request list.
**Reads:** matched `(orig_entry, fwd_entry, fwd_state)` tuples; takes the diff function as a
parameter.
**Writes:** nothing — returns block-description dicts.
**Called by:** `span_inline_probe.py`.
**Calls out:** none.

---

### span_inline_probe_report.py (370 LOC)

**Purpose:** Builds the Markdown report — per-block span sequence, inline render mock, Form A/B
analysis, storage-cost table, design-tension and recommendation sections.
**Reads:** block-description dicts from `span_inline_probe_blocks.py`.
**Writes:** returns the report as a list of lines.
**Called by:** `span_inline_probe.py`.
**Calls out:** none.

---

## State
No shared or mutating state. The entry script resolves the area and project roots once at import time and always derives the main-checkout root for the corpus lookup. Its hardcoded session stem is rotated off disk, so the script raises on load (see process-docs).
