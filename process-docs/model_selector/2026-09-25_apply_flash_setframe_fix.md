# Apply success flash: setFrame_display_ failure

2026-09-25

## Observed defect

`/tmp/monitor-cc-menubar.err` twice: `apply success flash failed: '_CursorlessButton' object has no attribute 'setFrame_display_'`. `setFrame_display_` is an NSWindow selector. `_show_apply_success` and `_revert_apply_button` in `src/menubar/model_controller.py` called it on the Apply button (NSButton, arranged view of an NSStackView), so the flash raised before the title was set; the except handler logged it and the user saw no feedback.

## Decision

Both functions now only call `setTitle_`. No frame, no constraint. Measured in the project venv with a real `_make_tab_nspanel` stack view (orientation vertical, gravity-areas distribution) and the real Apply button:

- `Apply` title: width 59.0 after `layoutSubtreeIfNeeded` (the 78 pt initial frame is ignored; the stack view sizes arranged views from intrinsic content size, translatesAutoresizingMaskIntoConstraints is False after being added).
- `Applied successfully` title: width 148.5, no frame call needed.
- Title back to `Apply`: width 59.0.

So the stack view already does the widening the manual frame was meant to do. The planned 2-constant fallback and a width constraint were not needed. Removed constants `_APPLY_SUCCESS_W` from `model_panel_ui.py`; `_APPLY_BTN_W/_H` remain only for the initial frame of the factory.

## Test

`dev/model_selector/verify_apply_flash_layout.py` (venv python, offscreen, `threading.Timer` patched, `log_menubar` captured): asserts no logged failure, flash title/width grows, revert title and width equal the initial width. Run against the pre-fix code it fails with exactly the two logged AttributeError lines from the observed log; against the fix it passes. `verify_four_tab_ring.py` and `verify_model_cycle_and_io.py` still pass.

## Not verified here

Live rendering in the running menubar (Main verifies after merge: menubar.log has no `apply success flash failed` line). `setup_py2app.py` was not run.
