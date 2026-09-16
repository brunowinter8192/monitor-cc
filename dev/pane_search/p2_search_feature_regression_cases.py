# INFRASTRUCTURE
import os
import shutil
import tempfile
from pathlib import Path

from p2_search_feature_regression_fixtures import (
    mod_pane, mod_format, mod_search, mod_fwd, mod_colors, mod_click,
    PANE_WIDTH, SEARCH_CURRENT_BG, _BG_RESTORE_SENTINEL,
    check, _make_entry, _reset_pane_state, _fwd_line, _read_keypress_from_bytes,
)

# FUNCTIONS

def test_search_bar_renders_at_row1():
    print("\n[search bar] Always-visible row 1, empty and populated query")
    _reset_pane_state()
    mod_pane.proxy_entries.extend(_make_entry(i) for i in range(2))
    output = mod_pane._build_proxy_output()
    first_line = output.splitlines()[0]
    check("empty query: 'search: _' pattern present", 'search:' in first_line)
    mod_pane._proxy_search.query = 'foo'
    mod_pane._proxy_search.focused = True
    output2 = mod_pane._build_proxy_output()
    first_line2 = output2.splitlines()[0]
    check("populated query: query text 'foo' visible in row 1", 'foo' in first_line2)


def test_line_map_shift():
    print("\n[line_map shift] Header row never gets a body key; body starts at row 2")
    _reset_pane_state()
    mod_pane.proxy_entries.extend(_make_entry(i) for i in range(5))
    mod_pane._build_proxy_output()
    check("row 1 has no line_map entry", mod_pane.proxy_line_map.get(1) is None)
    check("every line_map row is >= 2", all(r >= 2 for r in mod_pane.proxy_line_map))
    req_keys = [k for k in mod_pane.proxy_line_map.values() if isinstance(k, tuple) and k[0] == 'req']
    check("all 5 REQ headers present in shifted line_map", len(req_keys) == 5)


def test_collapsed_hit_marks_req_row():
    print("\n[collapsed hit] Header TEXT EXTENT marked (not the whole row) — no inner line "
          "marked (nothing rendered), no leftover unsubstituted sentinel")
    _reset_pane_state()
    entries = [_make_entry(i) for i in range(4)]
    mod_pane.proxy_entries.extend(entries)
    matches = mod_search.build_search_matches('unique_marker_2', mod_pane.proxy_entries, mod_pane.proxy_expand_states, PANE_WIDTH)
    check("exactly entry 2 matches 'unique_marker_2'", matches == [2])
    mod_pane._proxy_search.query = 'unique_marker_2'
    mod_pane._proxy_search.matches = matches
    mod_pane._proxy_search.match_set = set(matches)
    mod_pane._proxy_search.current_idx = 0
    output = mod_pane._build_proxy_output()
    lines = output.splitlines()
    marked_lines = [l for l in lines if SEARCH_CURRENT_BG in l]
    check("exactly one line carries SEARCH_CURRENT_BG (the collapsed REQ header)", len(marked_lines) == 1)
    header_line = marked_lines[0]
    check("marker sits AFTER the leading indent — NOT at column 0 (whole-row prefix would start there)",
          header_line.index(SEARCH_CURRENT_BG) > 0)
    check("no leftover unsubstituted _BG_RESTORE_SENTINEL in the final rendered output",
          _BG_RESTORE_SENTINEL not in output)
    check("full row is NOT whole-row-hoisted: SEARCH_CURRENT_BG occurrence count is exactly 1 "
          "(a whole-row hoist would ALSO show it prepended a second time via chosen_bg)",
          header_line.count(SEARCH_CURRENT_BG) == 1)


def test_expanded_hit_marks_line():
    print("\n[expanded hit] Header STAYS marked (text-extent only) + the matching inner line "
          "is highlighted browser-find style (substring only, not the whole content row)")
    _reset_pane_state()
    entries = [_make_entry(i) for i in range(4)]
    mod_pane.proxy_entries.extend(entries)
    matches = mod_search.build_search_matches('unique_marker_2', mod_pane.proxy_entries, mod_pane.proxy_expand_states, PANE_WIDTH)
    mod_pane._proxy_search.query = 'unique_marker_2'
    mod_pane._proxy_search.matches = matches
    mod_pane._proxy_search.match_set = set(matches)
    mod_pane._proxy_search.current_idx = 0
    mod_pane.proxy_expand_states[('req', 2)] = True
    output = mod_pane._build_proxy_output()
    marked_lines = [l for l in output.splitlines() if SEARCH_CURRENT_BG in l]
    check("2 lines carry SEARCH_CURRENT_BG (header + inner content line)", len(marked_lines) == 2)
    inner_marked = [l for l in marked_lines if 'unique_marker_2' in l]
    check("the inner marked line actually contains the matched text", len(inner_marked) == 1)
    inner_line = inner_marked[0]
    check("marker sits immediately adjacent to the matched substring (not at line start) — "
          "proves it wraps just the substring, not the whole row",
          inner_line.index(SEARCH_CURRENT_BG) > 0 and
          inner_line[inner_line.index(SEARCH_CURRENT_BG) + len(SEARCH_CURRENT_BG):].startswith('unique_marker_2'))
    check("no leftover unsubstituted _BG_RESTORE_SENTINEL in the final rendered output",
          _BG_RESTORE_SENTINEL not in output)


def test_sentinel_resolves_to_default_bg_not_empty_string_on_zebra_a_rows():
    print("\n[live bug, 2026-08-18] Empty-string chosen_bg (ZEBRA_BG_A rows — every second "
          "zebra row) must NOT delete the sentinel outright: that left the search-highlight BG "
          "active through to \\x1b[K erase-to-EOL, flooding the rest of the row gold. Exact "
          "user-reported + self-reproduced repro, direct call to _apply_row_backgrounds.")
    line = (f"    {SEARCH_CURRENT_BG}62/62 im eigenen Lauf, das Diff{_BG_RESTORE_SENTINEL}")
    out = mod_format._apply_row_backgrounds([line], [('msg', 5, 0)], set(), None, None, 120, 0)
    rendered = out[0]
    check("no unsubstituted _BG_RESTORE_SENTINEL left in the output", _BG_RESTORE_SENTINEL not in rendered)
    check("a real default-bg reset (\\x1b[49m) appears after the matched text",
          '\x1b[49m' in rendered)
    match_end = rendered.index('Diff') + len('Diff')
    reset_pos = rendered.find('\x1b[49m', match_end)
    erase_pos = rendered.index('\x1b[K')
    check("the reset sits BETWEEN the matched text and \\x1b[K — the gold BG is closed before "
          "erase-to-EOL, so no flood reaches the end of the row",
          match_end <= reset_pos < erase_pos)

    line2 = f"    {SEARCH_CURRENT_BG}matched{_BG_RESTORE_SENTINEL} trailing"
    out2 = mod_format._apply_row_backgrounds([line2], [('msg', 6, 0)], set(), None, None, 120, 1)
    check("non-empty chosen_bg (ZEBRA_BG_B) case unaffected by the fix",
          mod_colors.ZEBRA_BG_B in out2[0] and out2[0].count(mod_colors.ZEBRA_BG_B) >= 2)


def test_n_N_ordering():
    print("\n[n/N ordering] Jump forward/backward wraps around the match list")
    _reset_pane_state()
    mod_pane.proxy_entries.extend(_make_entry(i) for i in range(6))
    mod_pane._proxy_search.matches = [1, 3, 5]
    mod_pane._proxy_search.match_set = {1, 3, 5}
    mod_pane._proxy_search.current_idx = 0
    mod_pane._jump_search_match(forward=True)
    check("n: 0 -> 1", mod_pane._proxy_search.current_idx == 1)
    mod_pane._jump_search_match(forward=True)
    check("n: 1 -> 2", mod_pane._proxy_search.current_idx == 2)
    mod_pane._jump_search_match(forward=True)
    check("n wraps: 2 -> 0", mod_pane._proxy_search.current_idx == 0)
    mod_pane._jump_search_match(forward=False)
    check("N wraps backward: 0 -> 2", mod_pane._proxy_search.current_idx == 2)
    mod_pane._proxy_search.matches = []
    mod_pane._proxy_search.match_set = set()
    check("n/N no-op with zero matches", mod_pane._jump_search_match(forward=True) is False)


def test_esc_clears_query_bar_stays():
    print("\n[Esc] Clears query + matches; bar remains a permanent row")
    _reset_pane_state()
    mod_pane.proxy_entries.extend(_make_entry(i) for i in range(2))
    mod_pane._proxy_search.query = 'unique_marker_1'
    mod_pane._proxy_search.focused = True
    mod_pane._proxy_search.matches = [1]
    mod_pane._proxy_search.match_set = {1}
    result = mod_pane._handle_proxy_search_cancel()
    check("cancel returns True (always redraws)", result is True)
    check("query cleared", mod_pane._proxy_search.query == '')
    check("focused cleared", mod_pane._proxy_search.focused is False)
    check("matches cleared", mod_pane._proxy_search.matches == [] and mod_pane._proxy_search.match_set == set())
    output = mod_pane._build_proxy_output()
    check("bar still rendered at row 1 after Esc (permanent, not hidden)", 'search:' in output.splitlines()[0])


def test_scroll_jump_clamps():
    print("\n[scroll-jump clamp] Jumping to a match never exceeds max_scroll")
    _reset_pane_state()
    entries = [_make_entry(i) for i in range(40)]
    mod_pane.proxy_entries.extend(entries)
    mod_pane._proxy_search.matches = [2]
    mod_pane._proxy_search.match_set = {2}
    mod_pane._proxy_search.current_idx = 0
    orig_terminal_size = os.get_terminal_size
    os.get_terminal_size = lambda: os.terminal_size((30, 30))
    try:
        mod_pane._jump_to_search_match()
        check("_proxy_just_expanded set to the match's req key", mod_pane._proxy_just_expanded == ('req', 2))
        mod_pane._build_proxy_output()
        check("post-jump scroll_offset is non-negative", mod_pane.proxy_scroll_offset >= 0)
        check("the jumped-to entry is present in the rendered line_map", ('req', 2) in mod_pane.proxy_line_map.values())
        offset_before = mod_pane.proxy_scroll_offset
        mod_pane._build_proxy_output()
        check("scroll_offset stable across a second render (clamp is idempotent)",
              mod_pane.proxy_scroll_offset == offset_before)
    finally:
        os.get_terminal_size = orig_terminal_size


def test_flow_id_lazy_load_fix():
    print("\n[flow_id fix] _lazy_load_messages_forwarded matches by flow_id, not the "
          "call-local _fwd_req_idx (the collision bug found during M2 investigation)")
    tmp = Path(tempfile.mkdtemp(prefix='pane_search_flowid_'))
    full_path = tmp / 'full.jsonl'
    lines = [
        _fwd_line('flow-A', 'claude-opus-5', True, 'first request content AAA'),
        _fwd_line('flow-B', 'claude-opus-5', False, 'second request content BBB'),
        _fwd_line('flow-C', 'claude-opus-5', False, 'third request content CCC'),
        _fwd_line('flow-D', 'claude-opus-5', False, 'fourth request content DDD'),
    ]
    full_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    truth_entries, _ = mod_fwd._parse_forwarded_log(full_path, 0, {})
    truth_by_flow = {e['flow_id']: e for e in truth_entries}

    truncated = tmp / 'truncated.jsonl'
    truncated.write_text('\n'.join(lines[:2]) + '\n', encoding='utf-8')
    acc = {}
    batch1, pos1 = mod_fwd._parse_forwarded_log(truncated, 0, acc)
    batch2, pos2 = mod_fwd._parse_forwarded_log(full_path, pos1, acc)
    check("batch2 has 2 entries (flow-C, flow-D)", len(batch2) == 2)
    check("batch2's _fwd_req_idx COLLIDES with batch1's (0,1) — confirms the bug scenario applies",
          {e['_fwd_req_idx'] for e in batch2} == {0, 1})

    all_ok = True
    for e in batch2:
        truth = truth_by_flow[e['flow_id']]
        ok = mod_fwd._lazy_load_messages_forwarded(e, full_path)
        matched = ok and e.get('messages_total_chars') == truth['messages_total_chars']
        all_ok = all_ok and matched
    check("every batch2 entry lazy-loads its OWN content (flow_id-correct, not index-collided)", all_ok)

    shutil.rmtree(tmp, ignore_errors=True)


def test_utf8_multibyte_keypress():
    print("\n[UTF-8 keypress] read_keypress decodes multi-byte sequences as ONE character, "
          "not N replacement chars (input.click_handler, follow-up fix)")
    cases = [
        (b'a', 'a', 'plain ASCII (0 continuation bytes)'),
        ('—'.encode('utf-8'), '—', 'em-dash U+2014 (3 bytes, 2 continuation) — the reported bug'),
        ('ä'.encode('utf-8'), 'ä', 'ä U+00E4 (2 bytes, 1 continuation)'),
        ('ö'.encode('utf-8'), 'ö', 'ö U+00F6 (2 bytes, 1 continuation)'),
        ('ü'.encode('utf-8'), 'ü', 'ü U+00FC (2 bytes, 1 continuation)'),
        ('😀'.encode('utf-8'), '😀', 'emoji U+1F600 (4 bytes, 3 continuation)'),
    ]
    for byte_seq, expected, label in cases:
        result = _read_keypress_from_bytes(byte_seq)
        check(f"{label}: {byte_seq!r} -> {result!r}", result == expected)

    r, w = os.pipe()
    orig_fd = mod_click._stdin_fd
    mod_click._stdin_fd = r
    try:
        os.write(w, '—a'.encode('utf-8'))
        c1 = mod_click.read_keypress()
        c2 = mod_click.read_keypress()
        check("back-to-back em-dash + 'a' split correctly (no over-consumption)", (c1, c2) == ('—', 'a'))
    finally:
        mod_click._stdin_fd = orig_fd
        os.close(r)
        os.close(w)


def test_utf8_search_query_accumulation():
    print("\n[UTF-8 search accumulation] Multi-byte chars fed through the search bar's real "
          "input path (_handle_proxy_search_input) accumulate the real characters")
    _reset_pane_state()
    mod_pane.proxy_entries.extend(_make_entry(i) for i in range(2))
    mod_pane._proxy_search.focused = True
    for byte_seq in [b'f', b'o', b'o', ' '.encode(), '—'.encode('utf-8'), b'b', 'ä'.encode('utf-8'), '😀'.encode('utf-8')]:
        ch = _read_keypress_from_bytes(byte_seq)
        mod_pane._handle_proxy_search_input(ch)
    check("query accumulates real multi-byte characters, not replacement chars",
          mod_pane._proxy_search.query == 'foo —bä😀')
    check("no U+FFFD replacement character leaked into the query",
          '�' not in mod_pane._proxy_search.query)


def test_kill_line_after_a_real_search_run():
    print("\n[kill-line] Cmd+Backspace hypothesis (_KILL_LINE_CHAR) clears the query after a "
          "REAL Enter-triggered search — matches from that run stay stale (Enter-only recompute, "
          "unchanged M2 convention) until the user searches again")
    _reset_pane_state()
    entries = [_make_entry(i) for i in range(3)]
    mod_pane.proxy_entries.extend(entries)
    mod_pane._proxy_search.query = 'unique_marker_1'
    mod_pane._proxy_search.focused = True
    mod_pane._handle_proxy_search_input('\r')
    check("real search run found the match", mod_pane._proxy_search.matches == [1])
    mod_pane._proxy_search.focused = True
    changed = mod_pane._handle_proxy_search_input(mod_pane._KILL_LINE_CHAR)
    check("kill-line reports a change", changed)
    check("query fully emptied", mod_pane._proxy_search.query == '')
    check("matches from the prior real search run are UNCHANGED (stale until next Enter)",
          mod_pane._proxy_search.matches == [1])
