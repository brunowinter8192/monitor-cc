# dev/proxy_dual_log/A_render_refactor_proof/

## Role
Byte-identical differential test harness for the proxy_display render cluster, run around a
render-cluster refactor to prove output didn't change. One unit of `dev/proxy_dual_log/` (see the
area's own DOCS.md); split out because its 3 files import only each other.

## Public Interface
No `__init__.py` in this directory. Entry path: `./venv/bin/python
dev/proxy_dual_log/A_render_refactor_proof/A_render_refactor_proof.py --mode capture|verify`.

## Flow
14 fixed synthetic cases (from `_cases.py`, built from `_fixtures.py`'s low-level builders) are
rendered through the real `src.proxy_display.format.format_proxy_block`. `--mode capture` writes
the resulting `(ansi, total_lines)` per case to a baseline JSON; `--mode verify` re-renders and
diffs against a prior baseline.

## Modules

### A_render_refactor_proof.py (115 LOC)

**Purpose:** CLI harness (capture/verify modes) for the byte-identical differential test of the
proxy_display render cluster.
**Reads:** fixture entries from `A_render_refactor_proof_cases.py`; `--mode verify` also reads a
baseline JSON.
**Writes:** `A_render_refactor_proof_reports/<name>.json` (capture mode; the reports directory
stays at the area root, `dev/proxy_dual_log/`, not in this subfolder).
**Called by:** none — manual, run around a render-cluster refactor.
**Calls out:** `src.proxy_display.format`; `A_render_refactor_proof_cases.py`.

---

### A_render_refactor_proof_fixtures.py (35 LOC)

**Purpose:** The 3 low-level fixture builders shared by every case.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `A_render_refactor_proof_cases.py`.
**Calls out:** none.

---

### A_render_refactor_proof_cases.py (232 LOC)

**Purpose:** The 14 fixed test cases covering every render branch (new/stripped messages,
dual-span formats, tools, system blocks, expand-all fixpoint).
**Reads:** nothing — synthetic in-script fixture data.
**Writes:** nothing.
**Called by:** `A_render_refactor_proof.py`.
**Calls out:** `A_render_refactor_proof_fixtures.py`.

---

## State
No shared or mutating state across modules. `A_render_refactor_proof.py` resolves `_AREA_ROOT`
(by walking up from `__file__` until the directory named `proxy_dual_log` is found) and
`_PROJECT_ROOT` (`_AREA_ROOT.parent.parent`) once at import time; nothing else is mutable.
