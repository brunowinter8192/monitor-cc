# 2026-10-04 - claude-sonnet-5-5 added to the Models-tab cycle

## Task

`claude-sonnet-5-5` must be selectable for Main and Worker in the menubar Models tab. Before the
change, the orchestrator had set `~/.claude/shared-rules/model_selection.json` to
`{"main": "claude-opus-5-5", "worker": "claude-sonnet-5-5"}` and added a `claude-sonnet-5-5` entry to
`model_params` in `proxy_rules.json` (adaptive/summarized thinking, effort high, max_tokens 64000).
The user then saw `Worker: claude-sonnet-5` in the open tab.

## Change

`_MODEL_CHOICES` in `src/menubar/model_selection.py` grew 5 -> 6, `claude-sonnet-5-5` appended after
`claude-sonnet-5`:

```python
_MODEL_CHOICES = ("claude-opus-5", "claude-opus-5-5", "claude-fable-5", "claude-fable-5-1", "claude-sonnet-5", "claude-sonnet-5-5")
```

Appending kept the index-derived defaults unchanged (`_DEFAULT_MAIN` = index 1 = claude-opus-5-5,
`_DEFAULT_WORKER` = index 4 = claude-sonnet-5). Default worker deliberately stays claude-sonnet-5; the
task did not ask to change it. Cycle order: sonnet-5 -> sonnet-5-5 -> wraps to opus-5.

## Why the tab showed claude-sonnet-5 (not proven)

Checked facts on 2026-10-04:

- The installed bundle `~/Applications/monitor-cc-menubar.app` (running since 2026-09-26) contains
  `model_controller.py`, `model_selection.py` and `panel_lifecycle.py` byte-identical to the source.
- Every path that shows the Models panel (status item, ring arrows, tab clicks) goes through
  `_open_models_panel` -> `ModelController.open()` -> `_PendingSelection.load()`, which re-reads
  `model_selection.json` on each open.
- `_load_model_selection` returns the file value verbatim, even when it is outside `_MODEL_CHOICES`.
  So a file with `claude-sonnet-5-5` would display as `claude-sonnet-5-5` on open.
- No read-failure line in `menubar.log` around the file mtime (18:14).
- After open, the in-memory selection is never reloaded: cycle clicks and the rebuild after a live
  resize use the in-memory state only.

Conclusion: the code does not explain the stale value on a fresh open. Most plausible cause
(hypothesis, not observed): the Models panel was already open and loaded when the file was written,
so it still held the old in-memory value. Loading behaviour was left unchanged.

Real trap the code does have: an in-memory value outside `_MODEL_CHOICES` makes the next cycle click
jump to the first entry (`claude-opus-5`). With `claude-sonnet-5-5` in the tuple this no longer
happens for that value.

## Test

`dev/model_selector/verify_model_cycle_and_io.py`: length assertion 5 -> 6; new strand
`_strand_sonnet55_selection` (section 10), hermetic with temp files, no real shared-rules. It asserts:
a selection file with sonnet-5-5 loads as sonnet-5-5; params come from its own rules entry (example
fixture: medium / 128000); `_next_model("claude-sonnet-5")` is `claude-sonnet-5-5`; the next step wraps
to `claude-opus-5`; defaults are unchanged. Result 2026-10-04: 9/9 strands pass.

## Making it live

The menubar runs from the py2app bundle (a copy of the code), so a restart alone does not pick up the
change; the bundle has to be rebuilt. From the main checkout:
`./venv/bin/python setup_py2app.py py2app` (builds, prunes, signs, installs to
`~/Applications`, then `launchctl bootout` + `bootstrap gui/<uid>/com.brunowinter.monitor-cc-menubar`).
Not run by the worker; the orchestrator does it after merge.
