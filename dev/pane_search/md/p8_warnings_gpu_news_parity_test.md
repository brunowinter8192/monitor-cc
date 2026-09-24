# P8 -- warnings + gpu + news panes search bar parity regression suite

23/23 strands passed

## PASS test_warnings_state_shape


[warnings shape] SearchState instance, lowercase label, header_lines composition
  PASS  _warnings_search is a search_bar.SearchState instance
  PASS  label is 'search: '
  PASS  search bar is fixed 1-line

## PASS test_warnings_dim_yellow_bg_already_used_in_not_startswith


[verification] warnings_render.py's pre-existing DIM_YELLOW_BG detection already uses 'in line', not '.startswith()' -- confirmed by reading the source directly, no collateral fix needed here (unlike token_pane/worker_pane)
  PASS  source contains 'DIM_YELLOW_BG in line' (substring form)
  PASS  source does NOT contain a '.startswith(DIM_YELLOW_BG)' call

## PASS test_warnings_search_bar_row1_and_refresh_header_shifted


[2-row header] Search bar row 1; [refresh] region shifted to row 2
  PASS  row 1 shows the 'search: ' label
  PASS  no click-arrows
  PASS  [refresh] region exists and is at row 2 (shifted past the search bar)
  PASS  clicking the shifted [refresh] region still sets _force_refresh

## PASS test_warnings_row1_press_focuses_and_arms_drag


[press] A row-1 click focuses the bar and anchors a drag-select
  PASS  press returns True (redraw)
  PASS  press focuses the bar
  PASS  press arms dragging
  PASS  press anchors at index 1 ('e')

## PASS test_warnings_drag_select_copies_to_clipboard


[drag flow] press -> motion -> release copies the selected substring
  PASS  motion extends sel_end only
  PASS  release copies exactly the selected substring

## PASS test_warnings_plain_click_no_clipboard_and_body_clears_selection


[plain click / body clear] No motion -> zero clipboard calls; body click clears selection
  PASS  release still returns True (dragging disarmed)
  PASS  NO clipboard call on a plain click
  PASS  elsewhere-click clears the selection (reports a change)
  PASS  selection actually cleared

## PASS test_warnings_editing_mechanics


[editing] Backspace-selection-delete, plain backspace, kill-line, matches survive editing
  PASS  selection-delete removed 'ello '
  PASS  plain backspace trims last char
  PASS  kill-line empties the query
  PASS  matches survive plain backspace

## PASS test_warnings_collapsed_container_mark_and_expanded_substring_mark


[two-stage match] Collapsed error container-marks its header row; expanded ADDITIONALLY substring-highlights the matching detail line
  PASS  error is NOT expanded
  PASS  Enter reports a change
  PASS  real search found the error
  PASS  collapsed header line is container-marked
  PASS  the marker text itself does NOT leak into the collapsed row (only 'echo' shows)
  PASS  header line STILL container-marked when expanded
  PASS  the matched substring itself is browser-find highlighted
  PASS  no unsubstituted _BG_RESTORE_SENTINEL leaks into the final output

## PASS test_warnings_sentinel_resolves_to_default_bg_not_empty_string


[sentinel fix] ZEBRA_BG_A=='' applies here too -- an explicit \033[49m must appear after a highlighted detail line, not a raw leaked sentinel
  PASS  ZEBRA_BG_A is indeed the empty string
  PASS  an explicit \033[49m appears right after the highlighted detail-line text
  PASS  no raw _BG_RESTORE_SENTINEL leaked

## PASS test_warnings_n_N_cycles_without_touching_scroll


[nav] n/N cycles current_idx (this pane HAS real scroll infra, but n/N deliberately never touches error_scroll_offset -- only cycles which match is 'current')
  PASS  no-op with zero matches
  PASS  n advances to idx 1
  PASS  n advances to idx 2
  PASS  n wraps back to idx 0
  PASS  N (backward) wraps to idx 2
  PASS  error_scroll_offset untouched by n/N

## PASS test_warnings_esc_cancel_and_reverse_video


[Esc + render] Cancel clears state, bar stays visible; drag-select renders reverse-video
  PASS  cancel reports a change
  PASS  query/matches/selection cleared
  PASS  bar still renders (never hidden)
  PASS  reverse-video wraps exactly the selected substring

## PASS test_gpu_state_shape


[gpu shape] SearchState instance, lowercase label, no scroll infra confirmed
  PASS  _gpu_search is a search_bar.SearchState instance
  PASS  label is 'search: '
  PASS  search bar is fixed 1-line

## PASS test_gpu_render_pane_stays_unshifted_and_button_region_shifts_externally


[unshifted _render_pane] Direct call keeps row numbering relative to its own top (mirrors gpu_news_button_probe's own direct-call convention, needed zero changes); the search-bar row shift happens externally, in the loop
  PASS  direct _render_pane call registers its own header region at row 1 (its own top)
  PASS  after the external shift, the region is at row 2
  PASS  a click at the shifted row still correctly dispatches to 'refresh'

## PASS test_gpu_row1_click_focuses_search_bar


[press] A row-1 click (inline dispatch) focuses the bar
  PASS  row-1 dispatch returns True (search_bar handled it)
  PASS  press focuses the bar
  PASS  press arms dragging

## PASS test_gpu_drag_select_and_editing


[drag + editing] press -> motion -> release copies the substring; editing mechanics
  PASS  release copies exactly the selected substring
  PASS  plain backspace trims last char
  PASS  kill-line empties the query

## PASS test_gpu_highlight_only_match_no_sentinel_needed


[highlight-only] Real Enter-triggered search finds and highlights a match; NO sentinel machinery involved (this pane has no per-row background at all)
  PASS  matcher found at least one match line
  PASS  matched line is highlighted with SEARCH_CURRENT_BG
  PASS  the query substring itself is wrapped exactly (browser-find style)

## PASS test_gpu_n_N_cycles_current_idx_no_scroll_infra


[nav, no scroll] n/N cycles current_idx with zero scroll call -- this pane has no scroll/viewport infra at all
  PASS  no-op with zero matches
  PASS  n advances to idx 1
  PASS  n advances to idx 2
  PASS  n wraps back to idx 0
  PASS  N (backward) wraps to idx 2

## PASS test_gpu_esc_cancel_bar_stays


[Esc] Cancel clears state; bar stays visible
  PASS  cancel reports a change
  PASS  query/matches cleared
  PASS  bar still renders (never hidden)

## PASS test_news_state_shape


[news shape] SearchState instance, lowercase label
  PASS  _news_search is a search_bar.SearchState instance
  PASS  label is 'search: '
  PASS  search bar is fixed 1-line

## PASS test_news_render_pane_stays_unshifted


[unshifted _render_pane] Direct call keeps row numbering relative to its own top; the external shift mirrors gpu's own pattern
  PASS  [refresh] region (first inserted) is at its own top, row 1
  PASS  every region shifted by exactly _NEWS_SEARCH_BAR_LINES

## PASS test_news_highlight_only_match


[highlight-only] Real Enter-triggered search finds and highlights a match against the collection name (stable, independent of _is_running()'s real filesystem check)
  PASS  matcher found at least one match line
  PASS  matched line is highlighted with SEARCH_CURRENT_BG
  PASS  collection name substring wrapped exactly (browser-find style)

## PASS test_news_drag_select_and_n_N


[drag + nav] Drag-select copies exact substring; n/N cycles with no scroll infra
  PASS  release copies exactly the selected substring
  PASS  no-op with zero matches
  PASS  n advances to idx 1
  PASS  n wraps back to idx 0

## PASS test_news_esc_cancel_bar_stays


[Esc] Cancel clears state; bar stays visible
  PASS  cancel reports a change
  PASS  query/matches cleared
  PASS  bar still renders (never hidden)
