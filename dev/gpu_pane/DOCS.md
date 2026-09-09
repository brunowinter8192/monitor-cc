# dev/gpu_pane/

## Role

Byte-identity regression harnesses for `src/gpu_pane/` module splits. Add a script here when a
`src/gpu_pane/` refactor (module split, helper extraction) needs a before/after correctness proof
that isn't already covered by `dev/pane_search/`, `dev/click_ui/`, or `dev/pane_error_log/`'s own
behavior probes.

## Modules

### render_byte_identity.py (131 LOC, new 2026-09, gpu-pane-split milestone)

**Purpose:** Byte-identity harness for the gpu-pane-split milestone (`pane.py` concern split into
`gpu_actions.py` / `gpu_render.py`). Calls `_render_pane` with synthetic
presets/arbitrary/anomalies/today_errors/error_counts/collections — 3 preset scenarios (running+
healthy, running+unhealthy, stopped), one arbitrary server, a fresh `'starting'` toggle_state
overlay and an old/expired-looking one (both set directly on `_toggle_state`, not via
`_toggle_server`/`_fire_button`), 3 errors, 2 collections, 1 anomaly — at two pane widths (100,
40), with and without a search query (query matched against the baseline render's own lines,
mirroring `_gpu_search_on_commit`'s own approach), hashing the rendered output AND the resulting
`_button_regions` dict for every one of the 4 calls per width. `time.time()` is monkeypatched to a
constant — defensive determinism guard; no code path in `_render_pane`'s own call graph currently
reads it (toggle_state timestamps are constructed directly in the fixture, not via
`_toggle_server`/`_fire_button`), kept in case that ever changes.
**Reads:** Nothing external — synthetic fixtures built in-script.
**Writes:** Nothing — stdout only (one `HASH: <hex>` line).
**Run:** `./venv/bin/python dev/gpu_pane/render_byte_identity.py`
**Calls out:** `src.gpu_pane.pane` (`_render_pane`, `_toggle_state`, `_button_regions` — imported
via a function, `_import_gpu`, not a module-level `from src.` line, per `block_dev_imports_src`).

Status: hash `e33158d622d325e1ece673c5afbfc79217c7dd3842b4243225a338df58a14a52` — identical before
and after the gpu-pane-split milestone.
