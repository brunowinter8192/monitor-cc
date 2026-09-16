# INFRASTRUCTURE
from proxy_copy_probe_shared import (
    check, _patch_clipboard, _render_expanded,
    mod_proxy, mod_worker_proxy, mod_shared,
)

# FUNCTIONS

def _make_entry_with_thinking():
    return {
        'model': 'claude-sonnet', 'message_count': 1,
        'system_total_chars': 0, 'tools_total_chars': 0, 'messages_total_chars': 60,
        'messages': [
            {'role': 'assistant', 'type': 'text', 'chars': 10, 'blocks': [
                {'type': 'thinking', 'chars': 37, 'sig_chars': 44,
                 'full_text': 'Let me think this through carefully.', 'preview': 'Let me think this through care'},
                {'type': 'text', 'chars': 19, 'full_text': 'Here is my answer.'},
            ]},
        ],
        'schema_warnings': [], 'stripped_msg_indices': [], 'modifications': [],
        'timestamp': '2026-04-21T10:00:00Z',
    }


def test_thinking_row_gets_key_and_copy_registration():
    print("P5.6 -- thinking row gets a ('think', entry_idx, msg_idx, bidx) key and copy-row registration")
    entries = [_make_entry_with_thinking()]
    expand_states = {('req', 0): True}
    line_map, copy_rows, _ = _render_expanded(entries, expand_states)
    think_keys = {k for k in line_map.values() if isinstance(k, tuple) and k[0] == 'think'}
    check("thinking block keyed", think_keys == {('think', 0, 0, 0)})
    think_rows = {r for r, k in line_map.items() if k in think_keys}
    check("thinking row registered as a copy row", think_rows <= copy_rows and len(think_rows) == 1)
    msg_row = next(r for r, k in line_map.items() if k == ('msg', 0, 0))
    check("sibling message row still registered as a copy row too", msg_row in copy_rows)
    req_row = next(r for r, k in line_map.items() if k == ('req', 0))
    check("REQ row still registered as a copy row too", req_row in copy_rows)
    check("thinking row registered EVEN WHILE COLLAPSED (copy affordance is not gated on expand state)",
          not expand_states.get(('think', 0, 0, 0), False) and len(think_rows) == 1)


def test_thinking_copy_matches_serializer_and_msg_subset():
    print("P5.7 -- thinking-block copy matches the real serializer, and is a subset of the message copy")
    entries = [_make_entry_with_thinking()]
    think_key = ('think', 0, 0, 0)
    msg_text = mod_shared._serialize_proxy_message(('msg', 0, 0), entries)
    think_text = mod_shared._serialize_proxy_block(think_key, entries)
    check("thinking serialization non-empty", bool(think_text))
    check("thinking text appears verbatim inside the message-level copy", think_text in msg_text)
    check("thinking exact text", think_text == "--- msg[0] assistant thinking ---\nLet me think this through carefully.")
    check("non-think/non-block key returns empty string (defensive dispatch)", mod_shared._serialize_proxy_block(('msg', 0, 0), entries) == '')


def _setup_thinking_click_fixture(mod, pane_name):
    captured = _patch_clipboard(mod)
    entries = [_make_entry_with_thinking()]
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


def _run_thinking_click_suite(mod, pane_name):
    entries, line_map, captured, feedback_attr, expand_states_attr, handler = _setup_thinking_click_fixture(mod, pane_name)

    think_key = ('think', 0, 0, 0)
    think_row = next(r for r, k in line_map.items() if k == think_key)
    msg_row = next(r for r, k in line_map.items() if k == ('msg', 0, 0))

    changed = handler(0, 119, think_row)
    expected_think = mod_shared._serialize_proxy_block(think_key, entries)
    check(f"{pane_name}: click on thinking row copy column triggers copy", changed and captured and captured[-1] == expected_think)
    check(f"{pane_name}: flash keyed by the thinking block's own key, not entry_idx or the msg key",
          think_key in feedback_attr and 0 not in feedback_attr and ('msg', 0, 0) not in feedback_attr)
    captured.clear()

    pre_state = expand_states_attr.get(think_key, False)
    changed = handler(0, 5, think_row)
    post_state = expand_states_attr.get(think_key, False)
    check(f"{pane_name}: non-copy click on thinking row still returns changed=True", changed is True)
    check(f"{pane_name}: non-copy click on thinking row TOGGLES expand_states (pre={pre_state}, post={post_state})", post_state != pre_state)
    check(f"{pane_name}: non-copy click on thinking row writes nothing to clipboard", not captured)

    changed = handler(0, 5, think_row)
    back_state = expand_states_attr.get(think_key, False)
    check(f"{pane_name}: a second non-copy click toggles back to the original state", back_state == pre_state)

    feedback_attr.clear()
    handler(0, 119, msg_row)
    check(f"{pane_name}: copying the sibling message row does NOT flash the thinking row", think_key not in feedback_attr)


def test_main_pane_thinking_copy_click():
    print("P5.8 -- main pane (pane.py) end-to-end thinking-block click dispatch")
    _run_thinking_click_suite(mod_proxy, 'main')


def test_worker_pane_thinking_copy_click():
    print("P5.9 -- worker pane (worker_proxy_pane.py) end-to-end thinking-block click dispatch (both panes took the change)")
    _run_thinking_click_suite(mod_worker_proxy, 'worker')


def test_width_guard_suppresses_thinking_row_symbol():
    print("P5.10 -- width guard: no ⎘/✓ symbol or copy-row registration on a thinking row on a too-narrow pane")
    entries = [_make_entry_with_thinking()]
    expand_states = {('req', 0): True}
    line_map, copy_rows, _ = _render_expanded(entries, expand_states, pane_width=10)
    think_keys = {k for k in line_map.values() if isinstance(k, tuple) and k[0] == 'think'}
    check("thinking key still present at narrow width (rendering itself unaffected)", len(think_keys) == 1)
    check("no thinking row registered as a copy row at width=10", not any(
        isinstance(line_map.get(r), tuple) and line_map[r][0] == 'think' for r in copy_rows
    ))
