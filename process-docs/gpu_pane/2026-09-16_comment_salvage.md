## Salvage from dev/gpu_pane/render_byte_identity.py

```
"""
Byte-identity regression harness for src/gpu_pane/ (gpu-pane-split milestone — pane.py concern
split into gpu_actions.py / gpu_render.py).

Calls _render_pane with synthetic presets/arbitrary/anomalies/today_errors/error_counts/
collections (3 preset scenarios: running+healthy, running+unhealthy, stopped; one arbitrary
server; a fresh 'starting' toggle_state overlay and an old/expired-looking one; 3 errors; 2
collections; 1 anomaly) at two pane widths, with and without a search query, hashing the rendered
output AND the resulting _button_regions dict for every call. time.time() is monkeypatched to a
constant — defensive determinism guard per spec; no code path in _render_pane's own call graph
currently reads it (toggle_state timestamps are constructed directly here, not via _toggle_server/
_fire_button), but this keeps the harness robust if that ever changes.

Usage (from project root):
    ./venv/bin/python dev/gpu_pane/render_byte_identity.py

Prints one HASH line. Run before and after the src/gpu_pane/ split; the hash must match.
"""
```

```
# fresh
```
(trailing comment on `toggle_state['preset_healthy'] = ('starting', _FIXED_TS)          # fresh`)

```
# old/expired-looking
```
(trailing comment on `toggle_state['preset_stopped'] = ('starting', _FIXED_TS - 99999)  # old/expired-looking`)

```
# Imported via a function (not a module-level `from src....` line) — dev/ scripts may not use a
# literal top-level `from src.` import (block_dev_imports_src).
```

```
# Renders one pane_width twice (baseline, then with a search query matched against the baseline's
# own rendered lines — mirrors _gpu_search_on_commit's own matching approach), hashing
# (output, _button_regions) for each of the 2 calls.
```

## Salvage from dev/gpu_pane/DOCS.md

Nothing cut — the pre-existing `## Role` and `## Modules` sections already fit the required format. The pre-existing `## Gotchas` section has no home in the new fixed format and moved here in full:

```
## Gotchas

**`time.time()` is monkeypatched to a constant** as a defensive determinism guard — no code path
in `_render_pane`'s current call graph reads it (toggle_state timestamps are constructed directly
in the fixture, not via `_toggle_server`/`_fire_button`), but the patch stays in case that changes.
```

## Notes for successor

- 1 file, 7 comments + 1 docstring — matches the measured state exactly. Two are trailing inline comments (`# fresh`, `# old/expired-looking`); the other two are standalone blocks (one 2-line, one 3-line).
- No load-bearing docstring: grepped `__doc__` — zero hits. Docstring deleted outright.
- **Run directly** (safe): pure synthetic-fixture harness — `time.time()` monkeypatched to a fixed constant, all input data built in-script, no file I/O, stdout-only.
- Verification: ran before and after the comment/docstring strip — `HASH:` line identical (deterministic: `_regions_for_hash` sorts the button-regions list and `json.dumps(..., sort_keys=True)` is used for that part; the rendered-output string itself has no unordered-container dependency).
