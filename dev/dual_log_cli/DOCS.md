# dev/dual_log_cli/

## Role
Regression suite plus one measurement probe for `src/dual_log_cli/`, proving msgs, reqs, search, sessions and expand rendering rules against synthetic fixtures by calling the real functions. Touch when changing `src/dual_log_cli/` behavior. Do not add fixtures requiring a live monitor root or a real Claude projects tree.

## Public Interface
No `__init__.py`. The probe is run directly; the tests are entered from `tests/`.

## Flow
The tests in `tests/` run the real functions against synthetic fixtures. The probe globs the real dual-log directory for original and stripped pairs, runs four corpus-wide measurements and writes a dated report to `md/`.

## Modules

### probe_sys_tool_original_chars.py (230 LOC)

**Purpose:** Measures whether the last original request reliably recovers an earlier request's pre-strip system and tool sizes, backing the overlay design.
**Reads:** every original and stripped log pair of the resolved dual-log directory.
**Writes:** `dev/dual_log_cli/md/probe_sys_tool_original_chars_<date>.md`.
**Called by:** none; run manually.
**Calls out:** none.

---

## Sub-directories

- `tests/`: Regression tests for `src/dual_log_cli/`. See its own `DOCS.md`.

## State
No state. The probe writes one dated report per run to `md/`.
