# dev/proxy_tool_stripping/tests/

## Role
Regression test for the whole-stripped tool drill-down: the tools row must expand to the original description and schema from the original dual log. Touch when changing the tools drill-down rendering or the dual-log accumulator.

## Public Interface
No `__init__.py`. Entry path: `python3 dev/proxy_tool_stripping/tests/test_whole_stripped_tool_expand.py`.

## Flow
The test drives real render and parser functions against a synthetic JSONL fixture as parallel fail-fast strands (strand runner in `dev/refactoring/`).

## Modules

### test_whole_stripped_tool_expand.py (183 LOC)

**Purpose:** Verifies that a whole-stripped tool's drill-down row expands to the original description and schema from the original dual log.
**Reads:** nothing on disk except a JSONL fixture it writes itself under a temp dir.
**Writes:** stdout only.
**Called by:** none; manual CLI. It lives under `tests/` so the dev-imports-src hook's suite exemption allows its `src` imports.
**Calls out:** `src.proxy_display.dual_log_accumulator`, `.parser`, `.render_sections`.

---

## State
No persistent state. The module writes its fixture into a temp dir per run.
