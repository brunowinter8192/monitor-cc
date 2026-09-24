# test_hover_map: synthetic line_map assertions

7/7 strands passed

## PASS test_proxy_no_expand


[proxy] No expand — all req headers in line_map
  PASS  proxy_no_expand: no duplicate phys_rows
  PASS  proxy_no_expand: all rows in [1..pane_height-1]
  PASS  proxy_no_expand: row 3 > prev 2
  PASS  proxy_no_expand: row 6 > prev 3
  PASS  proxy_no_expand: row 7 > prev 6
  PASS  proxy_no_expand: row 8 > prev 7
  PASS  proxy_no_expand: 5 req keys in map, got 5

## PASS test_proxy_one_req_expanded


[proxy] One req expanded — sys+tools keys in line_map
  PASS  proxy_one_req_expanded: no duplicate phys_rows
  PASS  proxy_one_req_expanded: all rows in [1..pane_height-1]
  PASS  proxy_one_req_expanded: row 3 > prev 2
  PASS  proxy_one_req_expanded: row 4 > prev 3
  PASS  proxy_one_req_expanded: row 5 > prev 4
  PASS  proxy_one_req_expanded: row 6 > prev 5
  PASS  proxy_one_req_expanded: first row >= 1, got 2

## PASS test_proxy_turns_always_expanded


[proxy] Turns always expanded — no ('turn', N) keys in line_map
  PASS  proxy_turns_always_expanded: no turn keys in map, got 0
  PASS  proxy_turns_always_expanded: 4 req keys, got 4

## PASS test_proxy_hover_matches_row


[proxy] Hover applied at correct terminal row
  PASS  proxy_hover: req(0) found in line_map
  PASS  proxy_hover: HOVER_BG at terminal row 2

## PASS test_proxy_hover_wrap_header


[proxy] Header wrap: hover row adjusted by header_lines
  PASS  proxy_wrap: req(0) in line_map
  PASS  proxy_wrap: narrow header_lines=1
  PASS  proxy_wrap: wide header_lines=1, got 1
  PASS  proxy_wrap narrow: body_hover=2 == req0_body_row=2
  PASS  proxy_wrap wide: body_hover=2 == req0_body_row=2

## PASS test_proxy_shift_uses_header_lines


[proxy] Shift: line_map rows >= header_lines+1 after shift
  PASS  proxy_shift: narrow pane forces header_lines=2 >= 2
  PASS  proxy_shift: all shifted rows >= 3, min=4
  PASS  proxy_shift: old shift gives min=3 (for reference)

## PASS test_stripped_msg_pair_alignment


[render_messages] Stripped-msg lines/keys exact pairing (no line_map drift)
  PASS  stripped_pair: fixture yields 5 entries, got 5
  PASS  stripped_pair entry[1]: len(lines)=66 == len(keys)=66
  PASS  stripped_pair entry[2]: len(lines)=6 == len(keys)=6
  PASS  stripped_pair entry[3]: len(lines)=1713 == len(keys)=1713
  PASS  stripped_pair entry[4]: len(lines)=0 == len(keys)=0
  PASS  stripped_pair entry[5]: len(lines)=0 == len(keys)=0
  PASS  stripped_pair: at least 3 entries render lines, got 3
