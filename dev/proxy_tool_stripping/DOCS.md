# dev/proxy_tool_stripping/

## Role
Regression coverage and measurement probes for the proxy's strip/inject display area: how a
whole-stripped tool shows up in the tools drill-down (`TOOL_BLOCKLIST` in `src/constants.py` +
`src/proxy/tools.py`), and the REQ-header `strip`/`inject` badge's noise filters
(`src/proxy_display/parser.py`). Shares its name with `process-docs/proxy_tool_stripping/`, which
covers the broader write-side strip mechanism and read-side display together, not limited to the
tool blocklist specifically.

## Flow
`tests/test_whole_stripped_tool_expand.py` drives real render/parser functions against synthetic
fixtures and prints PASS/FAIL. `probe_trailing_message_shapes.py` scans real `_stripped.jsonl` text
for a specific tag shape and writes a findings report.

## Modules

### tests/test_whole_stripped_tool_expand.py (217 LOC)

**Purpose:** Verifies the whole-stripped tool row expand feature — a `TOOL_BLOCKLIST`-stripped tool's
drill-down row expands to show the original description/schema sourced from the session's `_original`
dual-log, instead of a static name-only row. Covers `_render_whole_stripped_tool`'s collapsed/expanded
bytes and key shape, `render_tools`'s whole-stripped loop wiring, and
`parser._find_original_log_path`/`accumulate_original_tools`'s path derivation and per-family
overwrite behavior.
**Reads:** nothing from disk except a JSONL fixture it writes itself under a temp directory for the
incremental-read tests.
**Writes:** nothing persistent — PASS/FAIL to stdout.
**Called by:** none — manual CLI. Placed under `tests/` (pytest-shaped filename) so the
`block_dev_imports_src` hook's regression-suite exemption allows its literal `from src.` imports.
**Calls out:** `src.proxy_display.dual_log_accumulator`, `src.proxy_display.parser`,
`src.proxy_display.render_sections`.

---

### probe_trailing_message_shapes.py (121 LOC)

**Purpose:** Scans every `_stripped.jsonl` line's `messages_delta` in the current corpus, collects
individual stripped text ending with the `<total_tokens>N tokens left</total_tokens>` tag, normalizes
the digit run, and reports distinct shapes with per-session counts — re-runnable to check whether a
new, uncatalogued nudge shape has appeared in the live corpus.
**Reads:** three fixed corpus stems' `_stripped.jsonl` files under src/logs/dual_log.
**Writes:** `md/trailing_message_shapes_report.md`.
**Called by:** none — manual CLI. Pure text/regex measurement, no `src/` import, so it lives at the
top level of this directory rather than under `tests/`.
**Calls out:** none — pure stdlib text scanning.

---

## Gotchas
- The byte-identity regression for the whole-stripped-tool-expand milestone reuses
  `dev/proxy_dual_log/A_render_refactor_proof.py` rather than a harness in this directory — its
  refreshed baseline lives at `dev/proxy_dual_log/A_render_refactor_proof_reports/baseline_20260905.json`.
