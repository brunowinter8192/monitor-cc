# src/news_pane/pane.py — run_news_loop split (2026-09)

## Task

`run_news_loop` was 111 LOC (hard target, over the 50-LOC function ceiling); the file itself
(336 LOC) was already under the 400-LOC file ceiling, so this was a function-only split, not a
module split. Apply the exact shape already established the same day in `src/gpu_pane/pane.py`
(`_poll_gpu_input`/`_handle_gpu_mouse`/`_build_gpu_output`), byte-identical behavior.

## Investigation before implementing

Read `src/news_pane/pane.py`, `log_pane.py`, `log_parser.py`, `DOCS.md`, `src/gpu_pane/pane.py`
(the just-established reference shape), and all four required probes in full. AST-scanned every
function in the package for the 50-LOC threshold — confirmed `run_news_loop` (111) was the only
violator; `_render_pane` (49 LOC) sits right at the edge but compliant, untouched by this
milestone (task explicitly noted no byte-identity harness was needed since `_render_pane`'s own
behavior doesn't change).

**Probe attribute list confirmed by reading, not assumed from the brief:** grepped
`dev/pane_search/p8_warnings_gpu_news_parity_test.py`'s `mod_news.*` references and
`dev/click_ui/p4_gpu_news_button_probe.py`'s `mod_news.*` references — both matched exactly the
attribute list the task brief gave. `dev/click_ui/p3_button_click_probe.py` confirmed to have
ZERO `news_pane`/`mod_news` references (grep-confirmed) — not a constraint source for this task.
No `inspect.getsource` pin anywhere across all 4 probes on any news function (grep-confirmed) —
no equivalent of the panes-split milestone's warnings conflict.

## The `_pipeline_proc` constraint (same rule as gpu_pane's `_toggle_server`)

`_pipeline_proc: subprocess.Popen | None` is a scalar rebound via `global` in `_fire_pipeline`
(`_pipeline_proc = subprocess.Popen(...)`) and read in `_is_running`
(`_pipeline_proc.poll() is None`). Both `p8` and `p4` directly assign
`mod_news._pipeline_proc = None` before exercising the pane. Per the established rule ("a
function that rebinds a scalar module global via `global` must stay physically in that module"),
`_fire_pipeline` and `_is_running` both had to stay exactly where they were — the task brief
stated this explicitly up front, and the investigation independently confirmed the same
conclusion by reading the probes, same reasoning class as `gpu_pane.pane._toggle_server`'s
`PRESET_NAMES` dependency from the previous milestone (see `process-docs/gpu_pane/` area).

One difference from the gpu_pane case worth noting: `p4_gpu_news_button_probe.py` also
monkeypatches `mod_news.subprocess.Popen` directly (`mod.subprocess.Popen = _FakePopen`) — but
since `subprocess` is a real stdlib module (a `sys.modules` singleton), that particular patch
would have worked regardless of which module `_fire_pipeline` lived in; it was the SCALAR
`_pipeline_proc` rebind + the probes' direct `mod_news._pipeline_proc = None` assignment that
forced the placement, not the `subprocess.Popen` patch.

## What changed

Applied the identical 3-helper shape from `gpu_pane.pane`, intra-file (no new sibling module,
since the file was already under 400 LOC):

- `_poll_news_input(status) -> (input_changed, force_refresh)` — the drain loop, extracted
  verbatim. Stays physically in `pane.py` (bare-name `read_keypress`/`read_mouse_event` calls —
  `p1_pane_loop_survives_exception_probe.py`'s monkeypatch constraint).
- `_handle_news_mouse(button, col, row) -> (changed, refresh_hit)` — the real-button-event
  dispatch (`button == 0`/`button == 32`-drag), extracted from the inline block; release/cancel
  handling stayed inline in the poll loop, mirroring `gpu_pane._poll_gpu_input`'s own precedent.
  Preserves the exact `break`-after-match-regardless-of-fire semantics (a click on a matched
  region while the pipeline is already running clears the drag-selection but doesn't itself
  report a change).
- `_build_news_output(status, last_output) -> last_output` — render + `_button_regions` shift +
  diff + print tail.

Unlike `gpu_pane`, no dedicated data-refresh helper was extracted — the news pane has only one
poll cadence (vs. gpu's two: status + collections), so the 5-line refresh block stayed inline in
`run_news_loop` without threatening the 50-LOC ceiling. The task brief's own helper list named
only 3 functions, matching this.

The now-redundant `force_refresh = False` local initializer at the top of `run_news_loop` was
dropped — `force_refresh` is no longer a loop-persistent local; it's freshly returned by
`_poll_news_input` every iteration, so it self-resets without an explicit reset line.

## Verification

`run_news_loop` dropped from 111 to 29 LOC. Full-package AST re-scan after the change: no function
≥50 LOC anywhere in `src/news_pane/`. All 4 required probes passed unchanged. No byte-identity
harness needed or built — the task brief was explicit that `_render_pane` (the only function whose
output actually gets hashed in the sibling `gpu_pane` milestone's harness) was untouched here.
