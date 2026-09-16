# INFRASTRUCTURE
from proxy_copy_probe_shared import (
    check, _patch_clipboard, _make_entry, _render_expanded,
    mod_proxy, mod_worker_proxy, mod_shared,
)

# FUNCTIONS

def test_message_row_gets_key_and_copy_registration():
    print("P5.1 -- message rows get a ('msg', entry_idx, msg_idx) key and copy-row registration")
    entries = [_make_entry()]
    expand_states = {('req', 0): True}
    line_map, copy_rows, _ = _render_expanded(entries, expand_states)
    msg_keys = {k for k in line_map.values() if isinstance(k, tuple) and k[0] == 'msg'}
    check("both message rows keyed", msg_keys == {('msg', 0, 0), ('msg', 0, 1)})
    msg_rows = {r for r, k in line_map.items() if k in msg_keys}
    check("both message rows registered as copy rows", msg_rows <= copy_rows and len(msg_rows) == 2)
    req_row = next(r for r, k in line_map.items() if k == ('req', 0))
    check("REQ row still registered as a copy row too", req_row in copy_rows)


def test_message_copy_matches_serializer_and_req_subset():
    print("P5.2 -- message-row copy matches the real serializer, and is a subset of the REQ copy")
    entries = [_make_entry()]
    req_text = mod_shared._serialize_proxy_entry(('req', 0), entries)
    msg0_text = mod_shared._serialize_proxy_message(('msg', 0, 0), entries)
    msg1_text = mod_shared._serialize_proxy_message(('msg', 0, 1), entries)
    check("msg[0] serialization non-empty", bool(msg0_text))
    check("msg[1] serialization non-empty", bool(msg1_text))
    check("msg[0] text appears verbatim inside the REQ-level copy", msg0_text in req_text)
    check("msg[1] text appears verbatim inside the REQ-level copy", msg1_text in req_text)
    check("msg[0] exact text", msg0_text == (
        "--- msg[0] assistant text ---\nhello world\n\n"
        "--- msg[0] assistant tool_use ---\nBash\n{\"command\":\"ls\"}"
    ))
    check("msg[1] exact text", msg1_text == "--- msg[1] user tool_result ---\nfile contents here")


def _setup_pane_click_fixture(mod, pane_name):
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


def _run_pane_click_suite(mod, pane_name):
    entries, line_map, captured, feedback_attr, expand_states_attr, handler = _setup_pane_click_fixture(mod, pane_name)

    msg_row0 = next(r for r, k in line_map.items() if k == ('msg', 0, 0))
    msg_row1 = next(r for r, k in line_map.items() if k == ('msg', 0, 1))
    req_row = next(r for r, k in line_map.items() if k == ('req', 0))

    changed = handler(0, 119, msg_row0)
    expected_msg0 = mod_shared._serialize_proxy_message(('msg', 0, 0), entries)
    check(f"{pane_name}: click on msg row 0 copy column triggers copy", changed and captured and captured[-1] == expected_msg0)
    check(f"{pane_name}: flash keyed by the msg's own key, not entry_idx", ('msg', 0, 0) in feedback_attr and 0 not in feedback_attr)
    check(f"{pane_name}: sibling msg row does NOT flash from this copy", ('msg', 0, 1) not in feedback_attr)
    captured.clear()

    changed = handler(0, 119, msg_row1)
    expected_msg1 = mod_shared._serialize_proxy_message(('msg', 0, 1), entries)
    check(f"{pane_name}: click on msg row 1 copy column triggers copy", changed and captured and captured[-1] == expected_msg1)
    captured.clear()

    pre_expand = dict(expand_states_attr)
    changed = handler(0, 5, msg_row0)
    check(f"{pane_name}: non-copy click on msg row returns no-change", changed is False)
    check(f"{pane_name}: non-copy click on msg row leaves expand_states untouched", expand_states_attr == pre_expand)
    check(f"{pane_name}: non-copy click on msg row writes nothing to clipboard", not captured)

    changed = handler(0, 119, req_row)
    expected_req = mod_shared._serialize_proxy_entry(('req', 0), entries)
    check(f"{pane_name}: REQ copy-click still fires", changed and captured and captured[-1] == expected_req)
    check(f"{pane_name}: REQ flash keyed by entry_idx (unchanged)", 0 in feedback_attr)
    captured.clear()


def test_main_pane_message_copy_click():
    print("P5.3 -- main pane (pane.py) end-to-end click dispatch")
    _run_pane_click_suite(mod_proxy, 'main')


def test_worker_pane_message_copy_click():
    print("P5.4 -- worker pane (worker_proxy_pane.py) end-to-end click dispatch (both panes took the change)")
    _run_pane_click_suite(mod_worker_proxy, 'worker')


def test_width_guard_suppresses_msg_row_symbol():
    print("P5.5 -- width guard: no ⎘/✓ symbol or copy-row registration on a too-narrow pane")
    entries = [_make_entry()]
    expand_states = {('req', 0): True}
    line_map, copy_rows, _ = _render_expanded(entries, expand_states, pane_width=10)
    msg_keys = {k for k in line_map.values() if isinstance(k, tuple) and k[0] == 'msg'}
    check("message keys still present at narrow width (rendering itself unaffected)", len(msg_keys) == 2)
    check("no msg row registered as a copy row at width=10", not any(
        isinstance(line_map.get(r), tuple) and line_map[r][0] == 'msg' for r in copy_rows
    ))
