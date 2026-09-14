"""
P5 -- proxy pane message-row AND thinking-block copy-by-click probe (Milestone 5: message-level
copy inside an expanded REQ; extended for the thinking-block-level copy milestone right after it).

Proves, per proxy pane (main `pane.py`, worker `worker_proxy_pane.py`), that after one real
render pass of an expanded REQ:
  1. every plain message-summary row (the `[msg_idx] role  type  chars` / `[msg_idx] role  type`
     rows built by `render_messages._render_new_messages`/`_render_modified_messages`) gets a
     `('msg', entry_idx, msg_idx)` key and a copy-row registration, alongside the pre-existing
     `('req', entry_idx)` row
  2. a synthetic click on a message row's copy column copies EXACTLY
     `proxy_pane_shared._serialize_proxy_message`'s real output for that key -- not hardcoded --
     and that output is a byte-exact match of the corresponding `--- msg[i] ... ---` segment(s)
     inside `_serialize_proxy_entry`'s own REQ-level output for the same message
  3. a click anywhere else on a message row (not the copy column) changes nothing -- no
     `expand_states` mutation, no clipboard write -- matching what these rows did before they had
     a key at all (key=None -> `_handle_proxy_mouse` returns immediately)
  4. copying one message row's flash timer is keyed by the message's own `('msg', ...)` key, not
     the shared `entry_idx` -- it must NOT flash the REQ header or a sibling message row
  5. the pre-existing whole-REQ copy path is completely unaffected (same key, same dispatch
     branch, same `_serialize_proxy_entry` output)
  6. a too-narrow pane renders no `⎘`/`✓` on a message row and registers no copy row for it
     (`utils.append_copy_symbol`'s existing width guard, inherited for free)
  7. a thinking block's own always-visible summary row (the `▶/▼ [bidx] thinking ...` row) gets a
     copy-row registration too, alongside its pre-existing `('think', entry_idx, msg_idx, bidx)`
     key
  8. a synthetic click on a thinking row's copy column copies EXACTLY
     `proxy_pane_shared._serialize_proxy_think`'s real output -- a byte-exact substring of the
     same message's `_serialize_proxy_message` output
  9. a click anywhere ELSE on a thinking row still toggles `expand_states[think_key]`, exactly as
     it already did before this row had a copy affordance -- the one behavior this milestone must
     NOT change, proven by asserting the toggle actually flips, not just that nothing crashes
 10. copying a thinking block's flash timer is keyed by its own `('think', ...)` key -- it must
     NOT flash the sibling message row, the REQ header, or a different block
 11. a too-narrow pane renders no `⎘`/`✓` on a thinking row and registers no copy row for it

No live tmux/terminal needed for parts 1-5/7-10/11 -- `format_proxy_block` and `_handle_*_mouse`
are called directly with synthetic entries, `os.get_terminal_size` is never invoked on that path.
`copy_to_clipboard` is monkeypatched per module to a capturing stub (no real pbcopy call, no OS
clipboard dependency).

Run from project root or worktree root:
    ./venv/bin/python dev/click_ui/p5_proxy_message_copy_click_probe.py
"""

# INFRASTRUCTURE
import importlib
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))

_ROOT_PKG = 'src'
mod_proxy = importlib.import_module(f'{_ROOT_PKG}.proxy_display.pane')
mod_worker_proxy = importlib.import_module(f'{_ROOT_PKG}.proxy_display.worker_proxy_pane')
mod_format = importlib.import_module(f'{_ROOT_PKG}.proxy_display.format')
mod_shared = importlib.import_module(f'{_ROOT_PKG}.proxy_display.proxy_pane_shared')

_PASS = "\033[32mPASS\033[0m"
_FAIL = "\033[31mFAIL\033[0m"
_RESULTS = []


def check(label, condition):
    _RESULTS.append((label, bool(condition)))
    print(f"  {_PASS if condition else _FAIL}  {label}")
    return condition


# FUNCTIONS

def _patch_clipboard(mod):
    captured = []
    mod.copy_to_clipboard = lambda text: captured.append(text)
    return captured


def _make_entry():
    return {
        'model': 'claude-sonnet', 'message_count': 2,
        'system_total_chars': 0, 'tools_total_chars': 0, 'messages_total_chars': 100,
        'messages': [
            {'role': 'assistant', 'type': 'text', 'chars': 10, 'blocks': [
                {'type': 'text', 'chars': 10, 'full_text': 'hello world'},
                {'type': 'tool_use', 'chars': 5, 'full_text': 'Bash\n{"command":"ls"}'},
            ]},
            {'role': 'user', 'type': 'tool_result', 'chars': 20, 'blocks': [], 'content_preview': 'file contents here'},
        ],
        'schema_warnings': [], 'stripped_msg_indices': [], 'modifications': [],
        'timestamp': '2026-04-21T10:00:00Z',
    }


# Direct format_proxy_block call -- no os.get_terminal_size dependency, mirrors
# dev/display/test_hover_map.py's existing pattern. Row numbers are then shifted by 1, the same
# shift _render_and_scroll_body applies in the real event loop (row 1 is reserved for the
# permanent search-bar header in both panes) -- without this shift a synthetic REQ landing on raw
# row 1 would collide with _handle_*_mouse's "row==1 -> focus search bar" branch and never reach
# the real copy/expand dispatch at all. Returns (line_map, copy_rows) already shifted.
def _render_expanded(entries, expand_states, pane_width=120):
    line_map = {}
    copy_rows = set()
    copy_feedback = {}
    mod_format.format_proxy_block(
        entries, expand_states, line_map, None, 50, pane_width, 0,
        copy_feedback=copy_feedback, copy_rows_out=copy_rows,
    )
    mod_shared._shift_line_map_and_copy_rows(line_map, copy_rows, 1)
    return line_map, copy_rows, copy_feedback


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


def _run_pane_click_suite(mod, pane_name):
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

    msg_row0 = next(r for r, k in line_map.items() if k == ('msg', 0, 0))
    msg_row1 = next(r for r, k in line_map.items() if k == ('msg', 0, 1))
    req_row = next(r for r, k in line_map.items() if k == ('req', 0))

    # -- copy click on msg row 0's copy column --
    changed = handler(0, 119, msg_row0)
    expected_msg0 = mod_shared._serialize_proxy_message(('msg', 0, 0), entries)
    check(f"{pane_name}: click on msg row 0 copy column triggers copy", changed and captured and captured[-1] == expected_msg0)
    check(f"{pane_name}: flash keyed by the msg's own key, not entry_idx", ('msg', 0, 0) in feedback_attr and 0 not in feedback_attr)
    check(f"{pane_name}: sibling msg row does NOT flash from this copy", ('msg', 0, 1) not in feedback_attr)
    captured.clear()

    # -- copy click on msg row 1's copy column --
    changed = handler(0, 119, msg_row1)
    expected_msg1 = mod_shared._serialize_proxy_message(('msg', 0, 1), entries)
    check(f"{pane_name}: click on msg row 1 copy column triggers copy", changed and captured and captured[-1] == expected_msg1)
    captured.clear()

    # -- non-copy click on a msg row: no-op, matching pre-milestone (key=None) behavior --
    pre_expand = dict(expand_states_attr)
    changed = handler(0, 5, msg_row0)
    check(f"{pane_name}: non-copy click on msg row returns no-change", changed is False)
    check(f"{pane_name}: non-copy click on msg row leaves expand_states untouched", expand_states_attr == pre_expand)
    check(f"{pane_name}: non-copy click on msg row writes nothing to clipboard", not captured)

    # -- REQ-level copy still works, unchanged shape, keyed by entry_idx --
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
    think_text = mod_shared._serialize_proxy_think(think_key, entries)
    check("thinking serialization non-empty", bool(think_text))
    check("thinking text appears verbatim inside the message-level copy", think_text in msg_text)
    check("thinking exact text", think_text == "--- msg[0] assistant thinking ---\nLet me think this through carefully.")
    check("non-think key returns empty string (defensive dispatch)", mod_shared._serialize_proxy_think(('msg', 0, 0), entries) == '')


def _run_thinking_click_suite(mod, pane_name):
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

    think_key = ('think', 0, 0, 0)
    think_row = next(r for r, k in line_map.items() if k == think_key)
    msg_row = next(r for r, k in line_map.items() if k == ('msg', 0, 0))

    # -- copy click on the thinking row's copy column --
    changed = handler(0, 119, think_row)
    expected_think = mod_shared._serialize_proxy_think(think_key, entries)
    check(f"{pane_name}: click on thinking row copy column triggers copy", changed and captured and captured[-1] == expected_think)
    check(f"{pane_name}: flash keyed by the thinking block's own key, not entry_idx or the msg key",
          think_key in feedback_attr and 0 not in feedback_attr and ('msg', 0, 0) not in feedback_attr)
    captured.clear()

    # -- non-copy click on the thinking row: MUST still toggle expand/collapse, exactly as before --
    pre_state = expand_states_attr.get(think_key, False)
    changed = handler(0, 5, think_row)
    post_state = expand_states_attr.get(think_key, False)
    check(f"{pane_name}: non-copy click on thinking row still returns changed=True", changed is True)
    check(f"{pane_name}: non-copy click on thinking row TOGGLES expand_states (pre={pre_state}, post={post_state})", post_state != pre_state)
    check(f"{pane_name}: non-copy click on thinking row writes nothing to clipboard", not captured)

    # -- clicking again toggles it back, proving this is a real toggle, not a one-way flip --
    changed = handler(0, 5, think_row)
    back_state = expand_states_attr.get(think_key, False)
    check(f"{pane_name}: a second non-copy click toggles back to the original state", back_state == pre_state)

    # -- copying the sibling message row does not flash the thinking row --
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


# ORCHESTRATOR

def run_probe_workflow():
    print("=" * 70)
    print("proxy pane message-row and thinking-block copy-by-click probe")
    print("=" * 70)
    test_message_row_gets_key_and_copy_registration()
    test_message_copy_matches_serializer_and_req_subset()
    test_main_pane_message_copy_click()
    test_worker_pane_message_copy_click()
    test_width_guard_suppresses_msg_row_symbol()
    test_thinking_row_gets_key_and_copy_registration()
    test_thinking_copy_matches_serializer_and_msg_subset()
    test_main_pane_thinking_copy_click()
    test_worker_pane_thinking_copy_click()
    test_width_guard_suppresses_thinking_row_symbol()

    total = len(_RESULTS)
    passed = sum(1 for _, ok in _RESULTS if ok)
    print("\n" + "=" * 70)
    print(f"{passed}/{total} checks passed")
    print("=" * 70)

    _write_report(passed, total)
    return passed == total


def _write_report(passed, total):
    md_dir = WORKTREE_ROOT / "dev" / "click_ui" / "md"
    md_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = md_dir / f"p5_proxy_message_copy_click_probe_{stamp}.md"
    lines = [
        f"# P5 -- proxy pane message-row copy-by-click probe run ({datetime.now(timezone.utc).isoformat()})",
        "",
        f"**Result: {passed}/{total} checks passed**",
        "",
        "| Check | Result |",
        "|---|---|",
    ]
    for label, ok in _RESULTS:
        lines.append(f"| {label} | {'PASS' if ok else 'FAIL'} |")
    out_path.write_text("\n".join(lines) + "\n")
    print(f"\nReport written to: {out_path}")


if __name__ == "__main__":
    ok = run_probe_workflow()
    sys.exit(0 if ok else 1)
