# dev/proxy_tool_stripping/

## Role
Regression coverage and measurement probes for the proxy's strip/inject display area: how a whole-stripped tool appears in the tools drill-down and how the REQ-header strip/inject badge filters noise. Broader write-side and read-side background is in the process-docs of this area.

## Public Interface
No `__init__.py`. Entry paths: `python3 dev/proxy_tool_stripping/probe_trailing_message_shapes.py` and `python3 dev/proxy_tool_stripping/tests/test_whole_stripped_tool_expand.py`.

## Flow
The test drives real render and parser functions against synthetic fixtures as parallel fail-fast strands (strand runner in `dev/refactoring/`). The probe scans real stripped-log text for one tag shape and writes a findings report.

## Modules

### probe_trailing_message_shapes.py (101 LOC)

**Purpose:** Scans stripped-log message deltas for text ending in the token-count tag, normalizes digits and reports distinct shapes per session.
**Reads:** three fixed corpus stems' stripped logs, currently rotated out, so a run raises.
**Writes:** `md/trailing_message_shapes_report.md`.
**Called by:** none; manual CLI. Pure text measurement with no `src/` import.
**Calls out:** none; stdlib only.

---

## Sub-directories

- `tests/`: Regression test for the whole-stripped tool drill-down. See its own `DOCS.md`.

## State
No persistent state. Each module reads its input fresh per run and writes at most one output file.
