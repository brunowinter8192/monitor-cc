# INFRASTRUCTURE
from proxy_copy_probe_shared import (
    check, _patch_clipboard, _make_entry, _render_expanded,
    mod_proxy, mod_worker_proxy, mod_shared,
)

# FUNCTIONS

def test_block_row_gets_key_and_copy_registration():
    print("P5.11 -- non-thinking block rows get a ('block', entry_idx, msg_idx, bidx) key and copy-row registration")
    entries = [_make_entry()]
    expand_states = {('req', 0): True}
    line_map, copy_rows, _ = _render_expanded(entries, expand_states)
    block_keys = {k for k in line_map.values() if isinstance(k, tuple) and k[0] == 'block'}
    check("both non-thinking blocks in msg[0] keyed", block_keys == {('block', 0, 0, 0), ('block', 0, 0, 1)})
    block_rows = {r for r, k in line_map.items() if k in block_keys}
    check("both block rows registered as copy rows", block_rows <= copy_rows and len(block_rows) == 2)
    msg_row = next(r for r, k in line_map.items() if k == ('msg', 0, 0))
    check("owning message row still registered as a copy row too", msg_row in copy_rows)
    req_row = next(r for r, k in line_map.items() if k == ('req', 0))
    check("REQ row still registered as a copy row too", req_row in copy_rows)


def test_block_copy_matches_serializer_and_nests_in_msg_and_req():
    print("P5.12 -- block-row copy matches the real serializer, and nests inside BOTH the message copy and the REQ copy")
    entries = [_make_entry()]
    req_text = mod_shared._serialize_proxy_entry(('req', 0), entries)
    msg0_text = mod_shared._serialize_proxy_message(('msg', 0, 0), entries)
    block0_text = mod_shared._serialize_proxy_block(('block', 0, 0, 0), entries)
    block1_text = mod_shared._serialize_proxy_block(('block', 0, 0, 1), entries)
    check("block[0] (text) serialization non-empty", bool(block0_text))
    check("block[1] (tool_use) serialization non-empty", bool(block1_text))
    check("block[0] exact text", block0_text == "--- msg[0] assistant text ---\nhello world")
    check("block[1] exact text", block1_text == "--- msg[0] assistant tool_use ---\nBash\n{\"command\":\"ls\"}")
    check("block[0] text appears verbatim inside its message-level copy", block0_text in msg0_text)
    check("block[1] text appears verbatim inside its message-level copy", block1_text in msg0_text)
    check("block[0] text appears verbatim inside the REQ-level copy (not just via transitivity)", block0_text in req_text)
    check("block[1] text appears verbatim inside the REQ-level copy (not just via transitivity)", block1_text in req_text)
    check("non-think/non-block key returns empty string (defensive dispatch, shared serializer)",
          mod_shared._serialize_proxy_block(('msg', 0, 0), entries) == '')


def _setup_block_click_fixture(mod, pane_name):
    captured = _patch_clipboard(mod)
    entries = [_make_entry()]
    expand_states = {('req', 0): True}
    line_map, copy_rows, copy_feedback = _render_expanded(entries, expand_states)

    entries_attr = mod.proxy_entries if pane_name == 'main' else mod.worker_proxy_entries
    line_map_attr = mod.proxy_line_map if pane_name == 'main' else mod.worker_proxy_line_map
    copy_rows_attr = mod._proxy_copy_rows if pane_name == 'main' else mod._worker_proxy_copy_rows
    feedback_attr = mod._copy_feedback_until if pane_name == 'main' else mod._worker_copy_feedback_until
    expand_states_attr = mod.proxy_expand_states if pane_name == 'main' else mod.worker_proxy_expand_states
    pane_width_attr_name = '_proxy_pane_width' if pane_name == 'main' else '_worker_proxy_pane_width'
    handler = mod._handle_proxy_mouse if pane_name == 'main' else (lambda b, c, r: mod._handle_worker_proxy_mouse(b, c, r, None))

    entries_attr.clear(); entries_attr.extend(entries)
    line_map_attr.clear(); line_map_attr.update(line_map)
    copy_rows_attr.clear(); copy_rows_attr.update(copy_rows)
    feedback_attr.clear()
    expand_states_attr.clear(); expand_states_attr.update(expand_states)
    setattr(mod, pane_width_attr_name, 120)

    return entries, line_map, captured, feedback_attr, expand_states_attr, handler


def _run_block_click_suite(mod, pane_name):
    entries, line_map, captured, feedback_attr, expand_states_attr, handler = _setup_block_click_fixture(mod, pane_name)

    block_row0 = next(r for r, k in line_map.items() if k == ('block', 0, 0, 0))
    block_row1 = next(r for r, k in line_map.items() if k == ('block', 0, 0, 1))
    msg_row = next(r for r, k in line_map.items() if k == ('msg', 0, 0))
    req_row = next(r for r, k in line_map.items() if k == ('req', 0))

    changed = handler(0, 119, block_row0)
    expected_block0 = mod_shared._serialize_proxy_block(('block', 0, 0, 0), entries)
    check(f"{pane_name}: click on block row 0 copy column triggers copy", changed and captured and captured[-1] == expected_block0)
    check(f"{pane_name}: flash keyed by the block's own key, not entry_idx or the msg key",
          ('block', 0, 0, 0) in feedback_attr and 0 not in feedback_attr and ('msg', 0, 0) not in feedback_attr)
    check(f"{pane_name}: sibling block row does NOT flash from this copy", ('block', 0, 0, 1) not in feedback_attr)
    captured.clear()

    changed = handler(0, 119, block_row1)
    expected_block1 = mod_shared._serialize_proxy_block(('block', 0, 0, 1), entries)
    check(f"{pane_name}: click on block row 1 copy column triggers copy", changed and captured and captured[-1] == expected_block1)
    captured.clear()

    pre_expand = dict(expand_states_attr)
    changed = handler(0, 5, block_row0)
    check(f"{pane_name}: non-copy click on block row returns no-change", changed is False)
    check(f"{pane_name}: non-copy click on block row leaves expand_states untouched", expand_states_attr == pre_expand)
    check(f"{pane_name}: non-copy click on block row writes nothing to clipboard", not captured)

    feedback_attr.clear()
    handler(0, 119, msg_row)
    check(f"{pane_name}: copying the owning message row does NOT flash block row 0", ('block', 0, 0, 0) not in feedback_attr)
    check(f"{pane_name}: copying the owning message row does NOT flash block row 1", ('block', 0, 0, 1) not in feedback_attr)
    captured.clear()

    feedback_attr.clear()
    changed = handler(0, 119, req_row)
    expected_req = mod_shared._serialize_proxy_entry(('req', 0), entries)
    check(f"{pane_name}: REQ copy-click still fires after block-row changes", changed and captured and captured[-1] == expected_req)
    check(f"{pane_name}: REQ flash keyed by entry_idx (unchanged), not any block key",
          0 in feedback_attr and ('block', 0, 0, 0) not in feedback_attr and ('block', 0, 0, 1) not in feedback_attr)


def test_main_pane_block_copy_click():
    print("P5.13 -- main pane (pane.py) end-to-end block-row click dispatch")
    _run_block_click_suite(mod_proxy, 'main')


def test_worker_pane_block_copy_click():
    print("P5.14 -- worker pane (worker_proxy_pane.py) end-to-end block-row click dispatch (both panes took the change)")
    _run_block_click_suite(mod_worker_proxy, 'worker')


def test_width_guard_suppresses_block_row_symbol():
    print("P5.15 -- width guard: no copy symbol or copy-row registration on a block row on a too-narrow pane")
    entries = [_make_entry()]
    expand_states = {('req', 0): True}
    line_map, copy_rows, _ = _render_expanded(entries, expand_states, pane_width=10)
    block_keys = {k for k in line_map.values() if isinstance(k, tuple) and k[0] == 'block'}
    check("block keys still present at narrow width (rendering itself unaffected)", len(block_keys) == 2)
    check("no block row registered as a copy row at width=10", not any(
        isinstance(line_map.get(r), tuple) and line_map[r][0] == 'block' for r in copy_rows
    ))
