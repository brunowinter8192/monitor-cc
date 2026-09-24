# P7 -- worker-tokens pane search bar + worker-switch header parity suite

23/23 strands passed

## PASS test_state_shape_and_label


[shape] Worker-tokens search state is one search_bar.SearchState, lowercase label
  PASS  _worker_tokens_search is a search_bar.SearchState instance
  PASS  label is 'search: '
  PASS  search bar is fixed 1-line

## PASS test_two_row_header_composition


[2-row header] Search bar row 1, worker-switch header row 2+; body rows past both
  PASS  row 1 (search bar) contains the label
  PASS  row 1 has no click-arrows
  PASS  worker-switch header text appears on a LATER line, not row 1
  PASS  row 1 is not a body line_map key
  PASS  row 2 (worker header) is not a body line_map key either
  PASS  header regions exist and are all on rows >= 2 (shifted past the search bar)
  PASS  all body line_map rows are past both header rows

## PASS test_row1_press_focuses_and_arms_drag


[press] A row-1 click focuses the bar and anchors a drag-select
  PASS  press returns True (redraw)
  PASS  press focuses the bar
  PASS  press arms dragging
  PASS  press anchors at index 1 ('e')

## PASS test_drag_select_copies_to_clipboard


[drag flow] press -> motion -> release copies the selected substring
  PASS  motion extends sel_end only
  PASS  release returns True (redraw)
  PASS  release disarms dragging
  PASS  release copies exactly the selected substring

## PASS test_plain_click_no_motion_no_clipboard


[plain click] press+release with NO motion makes zero clipboard calls
  PASS  release still returns True (dragging disarmed)
  PASS  NO clipboard call on a plain click
  PASS  selection cleared after a plain click

## PASS test_release_noop_without_active_drag


[release no-op] A release with no prior row-1 press changes nothing
  PASS  release with no armed drag returns False

## PASS test_body_click_clears_selection


[clear] Click on the body (row >= 3, unmapped) clears a live drag-selection
  PASS  selection exists before the elsewhere-click
  PASS  elsewhere-click reports a change (selection cleared)
  PASS  selection cleared after clicking elsewhere

## PASS test_body_drag_never_arms_search_selection


[scope] A drag starting on a BODY row never arms search-bar dragging
  PASS  body-row press does not arm dragging
  PASS  motion after a body-row press falls through to generic hover

## PASS test_new_input_clears_selection


[clear] New keyboard input clears a live drag-selection
  PASS  selection exists before typing
  PASS  typing reports a change
  PASS  selection cleared after typing
  PASS  typed char appended at the end

## PASS test_backspace_deletes_active_selection


[editor-style delete] Backspace with an active selection deletes the SELECTED substring
  PASS  backspace reports a change
  PASS  query has the SELECTED substring removed
  PASS  selection cleared after selection-delete

## PASS test_backspace_without_selection_still_trims_last_char


[editor-style delete] Backspace with no selection still trims the last char
  PASS  backspace reports a change
  PASS  last char trimmed

## PASS test_kill_line_empties_query


[editor-style delete] Kill-line (search_bar.KILL_LINE_CHAR) empties the whole query
  PASS  kill-line reports a change
  PASS  query fully emptied

## PASS test_editing_never_clears_matches


[matches] Editing (plain backspace, kill-line) never clears _worker_tokens_search.matches -- Enter remains the sole recompute trigger
  PASS  matches survive plain backspace
  PASS  matches survive kill-line

## PASS test_call_level_match_collapsed_container_marked


[match: call, collapsed] Whole call-header line container-marked even though the match text lives in unrendered (collapsed) detail content -- real worker JSONL fixture
  PASS  call is NOT expanded
  PASS  Enter reports a change
  PASS  real search found the call
  PASS  collapsed call header line is container-marked (SEARCH_CURRENT_BG present)
  PASS  the marker text itself does NOT leak into the collapsed row (still collapsed)

## PASS test_call_level_match_expanded_substring_marked


[match: call, expanded] Header stays container-marked AND the specific matching detail line gets browser-find substring-highlighted
  PASS  real search found the call
  PASS  header line STILL container-marked when expanded
  PASS  the matched substring itself is browser-find highlighted somewhere in the output
  PASS  no unsubstituted _BG_RESTORE_SENTINEL leaks into the final output

## PASS test_turn_level_match


[match: turn] A match in the turn's own prompt line gets the turn header container-marked
  PASS  Enter reports a change
  PASS  real search found the turn
  PASS  turn header is container-marked in the rendered output
  PASS  no ('turn', 0) key leaked into worker_tokens_line_map (turn headers stay non-interactive)

## PASS test_light_red_bg_still_detected_when_call_is_also_a_match


[regression] LIGHT_RED_BG (cc_broken row) detection uses 'in line', not '.startswith()' -- a search-match wrap now precedes it in the string
  PASS  real search found the call
  PASS  row's OUTER chosen_bg is still LIGHT_RED_BG despite the search-marker wrap preceding it

## PASS test_n_N_jump_wraps_both_directions


[nav] n/N jump forward/backward through matches, wrapping around; no-op with zero matches
  PASS  no-op with zero matches
  PASS  n advances to idx 1
  PASS  n advances to idx 2
  PASS  n wraps back to idx 0
  PASS  N (backward) wraps to idx 2

## PASS test_esc_cancel_clears_state_bar_stays


[Esc] Cancel clears query/matches/selection; the bar itself is never hidden
  PASS  cancel reports a change
  PASS  query cleared
  PASS  matches cleared
  PASS  focused cleared
  PASS  selection cleared
  PASS  bar still renders (never hidden)

## PASS test_render_reverse_video_bracket


[render] Active selection renders SGR reverse-video around the exact substring
  PASS  reverse-video ON code present
  PASS  reverse-video OFF code present
  PASS  the reversed span wraps exactly the selected substring
  PASS  no reverse-video codes when there is no selection

## PASS test_sentinel_resolves_to_default_bg_not_empty_string


[sentinel fix] Same bug class as the proxy/tokens/worker-proxy panes: ZEBRA_BG_A=='' -- the sentinel must resolve to an explicit \033[49m on a detail line, not be deleted outright (which would flood the search highlight color to the rest of the row)
  PASS  ZEBRA_BG_A is indeed the empty string (confirms the trap applies here)
  PASS  an explicit \033[49m appears right after the highlighted detail-line text
  PASS  no raw _BG_RESTORE_SENTINEL leaked into the final output

## PASS test_jump_to_match_moves_scroll_offset


[jump] Enter jumps worker_tokens_scroll_offset to bring an off-screen early match into view
  PASS  scroll starts at 0 (default view = newest/bottom)
  PASS  real search found the early call
  PASS  jump pushed worker_tokens_scroll_offset above 0 (turn 0 is far from the default bottom view)

## PASS test_worker_switch_resets_search_state_and_scroll


[worker switch] Switching the selected worker resets _worker_tokens_search AND worker_tokens_scroll_offset -- a DELIBERATE behavior change from the deleted worker_pane.py, which had no current-worker concept to switch away from; mirrors worker_proxy_pane.py's own worker-switch reset
  PASS  search state populated before the switch
  PASS  selected worker actually changed
  PASS  query cleared by the worker switch
  PASS  matches cleared by the worker switch
  PASS  focused cleared by the worker switch
  PASS  scroll offset reset to 0 by the worker switch
  PASS  turns cleared by the worker switch (stale worker's data does not leak)
