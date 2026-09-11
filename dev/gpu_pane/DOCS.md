# dev/gpu_pane/

## Role

Byte-identity regression harness for `src/gpu_pane/`. Add a script here when a `src/gpu_pane/`
refactor (module split, helper extraction) needs a before/after correctness proof that isn't
already covered by `dev/click_ui/` or `dev/pane_error_log/`'s own behavior probes.

## Modules

### render_byte_identity.py (131 LOC)

**Purpose:** Byte-identity harness for `src.gpu_pane.pane`'s `_render_pane` — calls it across
preset scenarios (running+healthy, running+unhealthy, stopped), an arbitrary server, fresh and
expired `toggle_state` overlays, errors, collections, and an anomaly, at two pane widths, with and
without a search query, hashing both the rendered output and the resulting `_button_regions` for
every call.
**Reads:** nothing external — synthetic fixtures built in-script.
**Writes:** nothing — stdout only (`HASH: <hex>`).
**Called by:** none — run manually; re-run after any `src/gpu_pane/` refactor.
**Calls out:** `src.gpu_pane.pane` (`_render_pane`, `_toggle_state`, `_button_regions`) —
imported via a function (`_import_gpu`), not a module-level `from src.` line, per
`block_dev_imports_src`.

---

## Gotchas

**`time.time()` is monkeypatched to a constant** as a defensive determinism guard — no code path
in `_render_pane`'s current call graph reads it (toggle_state timestamps are constructed directly
in the fixture, not via `_toggle_server`/`_fire_button`), but the patch stays in case that changes.
