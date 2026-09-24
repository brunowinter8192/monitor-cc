# P5 — worker-proxy pane search bar parity regression suite

21/21 strands passed

## PASS test_state_shape


[shape] Worker-proxy search state is one search_bar.SearchState, lowercase label
  PASS  _worker_proxy_search is a search_bar.SearchState instance
  PASS  label matches the proxy pane's ('search: ', this pane's structural twin)
  PASS  search bar is fixed 1-line

## PASS test_two_row_header_composition_and_shifts


[2-row header] Search bar row 1, worker-switcher header shifted to row 2+; header_regions and line_map both account for the search bar row
  PASS  row 1 (search bar) contains the label
  PASS  row 1 has no click-arrows
  PASS  worker-switcher header text appears on a LATER line, not row 1
  PASS  row 1 is not a body line_map key
  PASS  row 2 (worker header) is not a body line_map key either
  PASS  all header-region rows are >= 2 (shifted past the search bar row)
  PASS  all body line_map rows are past BOTH header rows (search bar + 1-line worker header)

## PASS test_header_marker_click_still_selects_worker_at_shifted_row


[header click] A click on the (now row-2+) worker marker still selects that worker
  PASS  region exists and is at a shifted (>=2) row
  PASS  marker region row is 2 (single-line worker header, right after the search bar)
  PASS  header-marker click at the shifted row selects the worker
  PASS  force_reload set

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

## PASS test_body_row_click_clears_selection


[clear] Click on the buffer area (row >= 2, unmapped) clears a live drag-selection
  PASS  selection exists before the elsewhere-click
  PASS  elsewhere-click reports a change (selection cleared)
  PASS  selection cleared after clicking elsewhere

## PASS test_body_row_drag_never_arms_search_selection


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


[matches] Editing (plain backspace, selection-delete, kill-line) never clears _worker_proxy_search.matches — Enter remains the sole recompute trigger
  PASS  matches survive plain backspace
  PASS  matches survive kill-line

## PASS test_enter_runs_real_search_no_log_path


[real search] Enter with _worker_proxy_log_path=None skips reconstruction and runs build_search_matches directly against the pre-populated synthetic entries
  PASS  _worker_proxy_log_path is None (no reconstruction)
  PASS  Enter reports a change
  PASS  real search found exactly entry 1
  PASS  match_set mirrors matches
  PASS  current_idx reset to 0
  PASS  Enter unfocuses the bar
  PASS  _wp_just_expanded set to the match's req key (reuses the expand-click auto-scroll anchor)

## PASS test_enter_always_reruns_not_gated_on_unchanged_query


[always-rerun] A repeated Enter with the SAME query re-runs the search — no unchanged-query gate exists on this pane (proxy's convention, nothing to correct here)
  PASS  first Enter found 1 match
  PASS  second Enter (same query) picked up the new entry -> 2 matches now

## PASS test_enter_triggers_reconstruction_merge_when_log_path_set


[reconstruction] Enter merges reconstruct_all_messages(fwd_path) by flow_id into worker_proxy_entries when _worker_proxy_log_path is set — the NEW wiring for this pane
  PASS  Enter reports a change
  PASS  entry 1's messages were populated from the reconstruction merge (were None before)
  PASS  the reconstructed content is findable — real search found entry 1

## PASS test_n_N_jump_wraps_both_directions


[nav] n/N jump forward/backward through matches, wrapping around; no-op with zero matches
  PASS  no-op with zero matches
  PASS  n advances to idx 1
  PASS  n advances to idx 2
  PASS  n wraps back to idx 0
  PASS  N (backward) wraps to idx 2
  PASS  _wp_just_expanded tracks the current match's req key

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

## PASS test_worker_switch_resets_search_state


[worker switch] Switching the selected worker resets _worker_proxy_search — mirrors pane.py's session-change reset and the fix just landed on the main pane; fires for BOTH digit-key and header-marker selection (both converge on this same code path)
  PASS  search state populated before the switch
  PASS  selected worker actually changed
  PASS  query cleared by the worker switch
  PASS  matches cleared by the worker switch
  PASS  focused cleared by the worker switch
