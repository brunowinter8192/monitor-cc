# run_sequence split in the M2 state sequence driver — 2026-09-24

`run_sequence` in `dev/pane_flicker/m2_state_sequence_driver.py` was 96 lines. It is now a caller of six phase functions: `hover_scroll_and_expand`, `copy_feedback_phase`, `response_entry_phase`, `search_phase`, `width_phase`, `growth_and_reset_phase`. The statements were moved as text slices in the original order. The variables that used to cross phase boundaries (`rows`, `copy_rows`, `expanded_key`, `rid`) are each defined and used inside a single phase, so no state is passed between phases except `pane` and `records`.

## Equivalence proof

The driver takes root, pane, session JSONL and output path as arguments, so the old version (from `git show HEAD:`) and the new version were run on the same frozen copies of two real sessions (`ae01f367...` many turns, `b390fcfd...` many calls) for both panes, four runs each in parallel. All four JSON dumps (0.8 to 1.1 MB each) are byte-identical (`cmp`). The driver only patches `os.get_terminal_size` and imports pane modules; it opens no window.
