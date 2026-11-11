# Fable 5.2 selectable in the menubar Models tab (2026-11-11)

## What changed

- `claude-fable-5-2` was inserted into the model choice tuple in `src/menubar/model_selection.py`, directly after `claude-fable-5-1`.
- The tuple grew from 6 to 7 entries. Cycle order on 2026-11-11: opus-5, opus-5-5, fable-5, fable-5-1, fable-5-2, sonnet-5, sonnet-5-5.
- No other code knows the choice list. The launcher, proxy and worker readers take whatever model ID the selection file holds.

## Pitfall: defaults are positional

`_DEFAULT_WORKER` is defined as an index into the choice tuple, not as a model ID. Inserting before `claude-sonnet-5` shifted index 4 from `claude-sonnet-5` to `claude-fable-5-2`. The index was moved from 4 to 5 so the default worker stays `claude-sonnet-5`. `_DEFAULT_MAIN` (index 1, `claude-opus-5-5`) was not affected because the insert is behind it.

Any future insert in front of a default index must move that index, or the default silently changes.

## Model ID decision

The user named the model "fable 5.2" without an ID. `claude-fable-5-2` follows the observed naming of `claude-fable-5-1` and `claude-opus-5-5`. Hypothesis, not verified against the API: the ID is accepted upstream. If requests with this ID fail, the ID string is the first thing to check.

## Test

`dev/model_selector/verify_model_cycle_and_io.py` pinned the choice count to 6. It now asserts 7 choices, presence of `claude-fable-5-2`, and that the default worker is still `claude-sonnet-5`. All 9 strands pass.

`dev/menubar/p5_g2_state.py` model-selection checks pass under system python3; the script later aborts on `AppKit` import when not run with the project venv. That abort is environmental and unrelated.

## Verification

The bundle was rebuilt and installed with `./venv/bin/python setup_py2app.py py2app` from the project root. The installed bundle copy of `model_selection.py` contains `claude-fable-5-2`, and the launch agent bootstrapped the new process. A code change in `src/menubar/` has no effect on the running menubar until this rebuild, because py2app bundles a copy of `src/`.

The live selection was not changed. On 2026-11-11 the selection file held main `claude-opus-5-5`, worker `claude-fable-5-1`. The user selects Fable 5.2 in the Models tab and clicks Apply, which also writes the `model_params` entry for the new ID.
