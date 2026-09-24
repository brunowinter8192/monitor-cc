# dev/proxy_dual_log/green_overlay_probe/

## Role
Reproduces a green-overlay false-injection bug and validates a char-level diff fix against real
and synthetic cases. One unit of `dev/proxy_dual_log/` (see the area's own DOCS.md); split out
because its 3 files import only each other.

## Public Interface
No `__init__.py` in this directory. Entry path: `./venv/bin/python
dev/proxy_dual_log/green_overlay_probe/green_overlay_probe.py`.

## Flow
One recorded session's dual-log files (hardcoded reference, currently rotated off disk) plus all
`*_injected.jsonl` under `src/logs/dual_log` feed the gating-soundness scan and bug/regression
cases; each is diffed with three variants (`word`/`char`/`char_gated`) and written to one fixed
Markdown report.

## Modules

### green_overlay_probe.py (214 LOC)

**Purpose:** CLI entry point reproducing a green-overlay false-injection bug and validating a
char-level diff fix against real and synthetic cases.
**Reads:** one recorded session's dual-log files (hardcoded session reference).
**Writes:** `green_overlay_probe_reports/green_overlay_probe.md` (the reports directory stays at
the area root, `dev/proxy_dual_log/`, not in this subfolder).
**Called by:** none — manual, one-off bug-repro probe.
**Calls out:** `green_overlay_probe_diff.py`, `_cases.py`.

---

### green_overlay_probe_diff.py (194 LOC)

**Purpose:** The three diff variants under comparison, marker-based attribution copies, fidelity
checking, and span formatting helpers.
**Reads:** nothing — pure text-diff functions.
**Writes:** nothing.
**Called by:** `green_overlay_probe.py`, `_cases.py`.
**Calls out:** none — self-contained.

---

### green_overlay_probe_cases.py (136 LOC)

**Purpose:** Live `_injected.jsonl` gating-soundness scan, plus the primary bug case and regression
cases used by the report.
**Reads:** one recorded session's dual-log files; all `*_injected.jsonl` under `src/logs/dual_log`.
**Writes:** nothing — returns case tuples/dicts.
**Called by:** `green_overlay_probe.py`.
**Calls out:** `green_overlay_probe_diff.py`.

---

## State
No shared or mutating state. The entry and cases modules each resolve the area root independently; the corpus lookup falls back to the main checkout because the corpus is gitignored. The hardcoded session stem is rotated off disk, so case loading fails per section and the failure is embedded as an error block in the report (see process-docs).
