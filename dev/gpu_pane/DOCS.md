# dev/gpu_pane/

## Role
Byte-identity regression harness for `src/gpu_pane/`. Add a script here when a `src/gpu_pane/`
refactor (module split, helper extraction) needs a before/after correctness proof that isn't
already covered by `dev/click_ui/` or `dev/pane_error_log/`'s own behavior probes.

## Public Interface
No `__init__.py` in this directory. Entry point is direct invocation: `./venv/bin/python dev/gpu_pane/render_byte_identity.py`.

## Flow
Builds synthetic preset/arbitrary/anomaly/error/collection fixtures, calls `_render_pane` at two pane widths with and without a search query, and hashes both the rendered output and the resulting `_button_regions` dict.

## Modules

### render_byte_identity.py (107 LOC)

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

## State
No persistent state. `time.time()` is monkeypatched to a fixed constant for the duration of `main()` and restored in a `finally` block; `_toggle_state` (owned by `src.gpu_pane.pane`) is cleared before and after the run.
