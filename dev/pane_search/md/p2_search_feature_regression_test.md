# P2 — proxy-pane search feature regression suite (M2)

12/12 strands passed

## PASS test_search_bar_renders_at_row1


[search bar] Always-visible row 1, empty and populated query
  PASS  empty query: 'search: _' pattern present
  PASS  populated query: query text 'foo' visible in row 1

## PASS test_line_map_shift


[line_map shift] Header row never gets a body key; body starts at row 2
  PASS  row 1 has no line_map entry
  PASS  every line_map row is >= 2
  PASS  all 5 REQ headers present in shifted line_map

## PASS test_collapsed_hit_marks_req_row


[collapsed hit] Header TEXT EXTENT marked (not the whole row) — no inner line marked (nothing rendered), no leftover unsubstituted sentinel
  PASS  exactly entry 2 matches 'unique_marker_2'
  PASS  exactly one line carries SEARCH_CURRENT_BG (the collapsed REQ header)
  PASS  marker sits AFTER the leading indent — NOT at column 0 (whole-row prefix would start there)
  PASS  no leftover unsubstituted _BG_RESTORE_SENTINEL in the final rendered output
  PASS  full row is NOT whole-row-hoisted: SEARCH_CURRENT_BG occurrence count is exactly 1 (a whole-row hoist would ALSO show it prepended a second time via chosen_bg)

## PASS test_expanded_hit_marks_line


[expanded hit] Header STAYS marked (text-extent only) + the matching inner line is highlighted browser-find style (substring only, not the whole content row)
  PASS  2 lines carry SEARCH_CURRENT_BG (header + inner content line)
  PASS  the inner marked line actually contains the matched text
  PASS  marker sits immediately adjacent to the matched substring (not at line start) — proves it wraps just the substring, not the whole row
  PASS  no leftover unsubstituted _BG_RESTORE_SENTINEL in the final rendered output

## PASS test_sentinel_resolves_to_default_bg_not_empty_string_on_zebra_a_rows


[live bug, 2026-08-18] Empty-string chosen_bg (ZEBRA_BG_A rows — every second zebra row) must NOT delete the sentinel outright: that left the search-highlight BG active through to \x1b[K erase-to-EOL, flooding the rest of the row gold. Exact user-reported + self-reproduced repro, direct call to _apply_row_backgrounds.
  PASS  no unsubstituted _BG_RESTORE_SENTINEL left in the output
  PASS  a real default-bg reset (\x1b[49m) appears after the matched text
  PASS  the reset sits BETWEEN the matched text and \x1b[K — the gold BG is closed before erase-to-EOL, so no flood reaches the end of the row
  PASS  non-empty chosen_bg (ZEBRA_BG_B) case unaffected by the fix

## PASS test_n_N_ordering


[n/N ordering] Jump forward/backward wraps around the match list
  PASS  n: 0 -> 1
  PASS  n: 1 -> 2
  PASS  n wraps: 2 -> 0
  PASS  N wraps backward: 0 -> 2
  PASS  n/N no-op with zero matches

## PASS test_esc_clears_query_bar_stays


[Esc] Clears query + matches; bar remains a permanent row
  PASS  cancel returns True (always redraws)
  PASS  query cleared
  PASS  focused cleared
  PASS  matches cleared
  PASS  bar still rendered at row 1 after Esc (permanent, not hidden)

## PASS test_scroll_jump_clamps


[scroll-jump clamp] Jumping to a match never exceeds max_scroll
  PASS  _proxy_just_expanded set to the match's req key
  PASS  post-jump scroll_offset is non-negative
  PASS  the jumped-to entry is present in the rendered line_map
  PASS  scroll_offset stable across a second render (clamp is idempotent)

## PASS test_flow_id_lazy_load_fix


[flow_id fix] _lazy_load_messages_forwarded matches by flow_id, not the call-local _fwd_req_idx (the collision bug found during M2 investigation)
  PASS  batch2 has 2 entries (flow-C, flow-D)
  PASS  batch2's _fwd_req_idx COLLIDES with batch1's (0,1) — confirms the bug scenario applies
  PASS  every batch2 entry lazy-loads its OWN content (flow_id-correct, not index-collided)

## PASS test_utf8_multibyte_keypress


[UTF-8 keypress] read_keypress decodes multi-byte sequences as ONE character, not N replacement chars (input.click_handler, follow-up fix)
  PASS  plain ASCII (0 continuation bytes): b'a' -> 'a'
  PASS  em-dash U+2014 (3 bytes, 2 continuation) — the reported bug: b'\xe2\x80\x94' -> '—'
  PASS  ä U+00E4 (2 bytes, 1 continuation): b'\xc3\xa4' -> 'ä'
  PASS  ö U+00F6 (2 bytes, 1 continuation): b'\xc3\xb6' -> 'ö'
  PASS  ü U+00FC (2 bytes, 1 continuation): b'\xc3\xbc' -> 'ü'
  PASS  emoji U+1F600 (4 bytes, 3 continuation): b'\xf0\x9f\x98\x80' -> '😀'
  PASS  back-to-back em-dash + 'a' split correctly (no over-consumption)

## PASS test_utf8_search_query_accumulation


[UTF-8 search accumulation] Multi-byte chars fed through the search bar's real input path (_handle_proxy_search_input) accumulate the real characters
  PASS  query accumulates real multi-byte characters, not replacement chars
  PASS  no U+FFFD replacement character leaked into the query

## PASS test_kill_line_after_a_real_search_run


[kill-line] Cmd+Backspace hypothesis (_KILL_LINE_CHAR) clears the query after a REAL Enter-triggered search — matches from that run stay stale (Enter-only recompute, unchanged M2 convention) until the user searches again
  PASS  real search run found the match
  PASS  kill-line reports a change
  PASS  query fully emptied
  PASS  matches from the prior real search run are UNCHANGED (stale until next Enter)
