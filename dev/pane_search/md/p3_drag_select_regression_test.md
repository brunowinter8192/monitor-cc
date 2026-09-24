# P3 — proxy-pane search bar drag-to-select regression suite

17/17 strands passed

## PASS test_col_to_index_ascii


[col mapping] Plain ASCII query — 1-cell-per-char boundary snapping
  PASS  click before/at label end -> index 0
  PASS  click on first char -> boundary 0 (before it)
  PASS  click on 7th query col -> boundary 6 (before 'w' in 'hello world')
  PASS  click past the end -> clamped to len(query)
  PASS  empty query always maps to 0

## PASS test_col_to_index_wide_char


[col mapping] Wide-char (emoji, 2-cell) query — left/right half snapping
  PASS  click on 'a' -> boundary 0 (before 'a')
  PASS  click on emoji's LEFT cell -> boundary 1 (before emoji)
  PASS  click on emoji's RIGHT cell -> boundary 2 (after emoji, before 'b')
  PASS  click on 'b' -> boundary 2 (same boundary, before 'b')
  PASS  click past 'b' -> boundary 3 (end of query)

## PASS test_drag_select_copies_to_clipboard


[drag flow] press -> motion -> release copies the selected substring
  PASS  press returns True (redraw)
  PASS  press focuses the bar (existing behavior preserved)
  PASS  press arms dragging
  PASS  press sets anchor==end (empty range until motion)
  PASS  motion returns True (redraw)
  PASS  motion extends sel_end only, anchor unchanged
  PASS  release returns True (redraw)
  PASS  release disarms dragging
  PASS  release copies exactly the selected substring
  PASS  release KEEPS the selection range visible (finished, not cleared)

## PASS test_plain_click_no_motion_no_clipboard


[plain click] press+release with NO motion — today's focus-only behavior preserved
  PASS  release still returns True (state changed: dragging disarmed)
  PASS  NO clipboard call on a plain click (never clobber the real clipboard)
  PASS  selection state fully cleared after a plain click
  PASS  focus is still set (existing behavior)

## PASS test_release_noop_without_active_drag


[release no-op] A release with no prior row-1 press changes nothing
  PASS  release with no armed drag returns False
  PASS  no clipboard call

## PASS test_body_row_drag_never_arms_search_selection


[scope] A drag starting on a BODY row never arms search-bar dragging
  PASS  body-row press does not arm dragging
  PASS  motion after a body-row press falls through to generic hover (proxy_hover_row set)
  PASS  search selection untouched by a body-row drag

## PASS test_click_elsewhere_clears_selection


[clear] Click elsewhere (body row) clears a live drag-selection
  PASS  selection exists before the elsewhere-click
  PASS  elsewhere-click reports a change (selection cleared)
  PASS  selection cleared after clicking elsewhere

## PASS test_new_input_clears_selection


[clear] New keyboard input clears a live drag-selection
  PASS  selection exists before typing
  PASS  typing reports a change
  PASS  selection cleared after typing
  PASS  query still gets the typed char appended (typing keeps operating at the end)

## PASS test_backspace_deletes_active_selection


[editor-style delete] Backspace with an active selection deletes the SELECTED substring (not just the last char) and clears the selection
  PASS  selection is 'ello ' before backspace
  PASS  backspace reports a change
  PASS  query has the SELECTED substring removed (not just the last char)
  PASS  selection cleared after selection-delete

## PASS test_backspace_without_selection_still_trims_last_char


[editor-style delete] Backspace with NO active selection still trims the last char — the pre-existing single-char behavior is unaffected
  PASS  no selection active
  PASS  backspace reports a change
  PASS  last char trimmed (regression: unchanged pre-existing behavior)

## PASS test_kill_line_empties_query


[editor-style delete] Kill-line (_KILL_LINE_CHAR, Cmd+Backspace hypothesis) empties the WHOLE query
  PASS  kill-line reports a change
  PASS  query fully emptied

## PASS test_kill_line_ignores_active_selection


[editor-style delete] Kill-line empties the query REGARDLESS of an active selection (not selection-aware, matches standard editor Cmd+Backspace semantics)
  PASS  selection is active before kill-line
  PASS  query fully emptied (not just the selected substring)
  PASS  selection also cleared

## PASS test_kill_line_not_silently_swallowed_by_isprintable_fallthrough


[editor-style delete] \x15 is intercepted by the kill-line branch BEFORE the isprintable() fallthrough — regression guard for the exact bug being fixed
  PASS  '\x15'.isprintable() is False (confirms the fallthrough risk this branch prevents)
  PASS  query was actually cleared, not silently ignored

## PASS test_editing_never_clears_matches


[matches] Editing (any form: plain backspace, selection-delete, kill-line) never clears _proxy_search.matches — Enter remains the sole recompute trigger (confirmed: neither did the pre-existing plain-backspace/typing path)
  PASS  matches survive plain backspace
  PASS  matches survive selection-delete backspace
  PASS  matches survive kill-line

## PASS test_esc_cancel_clears_selection


[clear] Esc-cancel clears a live drag-selection (alongside the query)
  PASS  selection exists before Esc
  PASS  selection cleared after Esc
  PASS  query also cleared (existing Esc behavior)

## PASS test_render_reverse_video_bracket


[render] Active selection renders SGR reverse-video around the exact substring; no selection renders without it
  PASS  reverse-video ON code present
  PASS  reverse-video OFF code present
  PASS  the reversed span wraps exactly the selected substring
  PASS  no reverse-video codes when there is no selection

## PASS test_session_change_clears_selection


[clear] Session change clears a live drag-selection
  PASS  selection exists before session change
  PASS  selection cleared on session change
