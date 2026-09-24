# dev/proxy_tool_stripping/

## Role
Regression coverage and measurement probes for the proxy's strip/inject display area: how a
whole-stripped tool shows up in the tools drill-down (`TOOL_BLOCKLIST` in `src/constants.py` +
`src/proxy/tools.py`), and the REQ-header `strip`/`inject` badge's noise filters
(`src/proxy_display/parser.py`). Shares its name with `process-docs/proxy_tool_stripping/`, which
covers the broader write-side strip mechanism and read-side display together.

## Public Interface
No `__init__.py` in this directory. Entry paths: `python3
dev/proxy_tool_stripping/probe_trailing_message_shapes.py` and `python3
dev/proxy_tool_stripping/tests/test_whole_stripped_tool_expand.py`.

## Flow
`tests/test_whole_stripped_tool_expand.py` drives real render/parser functions against synthetic
fixtures and prints PASS/FAIL. `probe_trailing_message_shapes.py` scans real `_stripped.jsonl` text
for a specific tag shape and writes a findings report.
Converted suites run as parallel strands through `dev/refactoring/strand_runner.py`: `python <file>` starts one subprocess per strand (`--strand <name>`), each strand aborts at its first failing `check`, sibling strands still finish, and the exit code is 1 if any strand aborted. The strand names are the module constant `_STRANDS`.

## Modules

### tests/test_whole_stripped_tool_expand.py (183 LOC)

**Purpose:** Verifies the whole-stripped tool row expand feature — a `TOOL_BLOCKLIST`-stripped tool's
drill-down row expands to show the original description/schema sourced from the session's `_original`
dual-log, instead of a static name-only row.
**Reads:** nothing from disk except a JSONL fixture it writes itself under a temp directory for the
incremental-read tests.
**Writes:** nothing persistent — PASS/FAIL to stdout.
**Called by:** none — manual CLI. Placed under `tests/` (pytest-shaped filename) so the
`block_dev_imports_src` hook's regression-suite exemption allows its literal `from src.` imports.
**Calls out:** `src.proxy_display.dual_log_accumulator`, `src.proxy_display.parser`,
`src.proxy_display.render_sections`.

---

### probe_trailing_message_shapes.py (99 LOC)

**Purpose:** Scans every `_stripped.jsonl` line's `messages_delta` in the current corpus, collects
individual stripped text ending with the `<total_tokens>N tokens left</total_tokens>` tag, normalizes
the digit run, and reports distinct shapes with per-session counts.
**Reads:** three fixed corpus stems' `_stripped.jsonl` files under src/logs/dual_log — currently
rotated off the live corpus, so a run raises `FileNotFoundError` (see process-docs).
**Writes:** `md/trailing_message_shapes_report.md`.
**Called by:** none — manual CLI. Pure text/regex measurement, no `src/` import, so it lives at the
top level of this directory rather than under `tests/`.
**Calls out:** none — pure stdlib text scanning.

---

## State
Neither module owns persistent state across runs — each reads its own input fresh per invocation
and writes at most one output file (or, for the probe, raises before writing when its fixed corpus
stems are absent).
