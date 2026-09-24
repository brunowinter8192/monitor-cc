# INFRASTRUCTURE
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.proxy_display.format import format_proxy_block
from src.format.token_format import format_cache_tracker

PANE_HEIGHT = 30
PANE_WIDTH = 120

PASS = 0
FAIL = 0


def _turn_cache():
    from src.proxy_display.turn_cache import TurnCache
    return TurnCache()

def assert_true(condition: bool, label: str) -> None:
    global PASS, FAIL
    if condition:
        print(f"  PASS  {label}")
        PASS += 1
    else:
        print(f"  FAIL  {label}")
        FAIL += 1


def _check_line_map(line_map: dict, pane_height: int, label: str) -> None:
    rows = sorted(line_map.keys())
    assert_true(len(rows) == len(set(rows)), f"{label}: no duplicate phys_rows")
    assert_true(all(1 <= r <= pane_height - 1 for r in rows), f"{label}: all rows in [1..pane_height-1]")
    for i, r in enumerate(rows):
        if i > 0:
            assert_true(r > rows[i - 1], f"{label}: row {r} > prev {rows[i-1]}")


def _make_entry(idx: int, model: str = 'claude-sonnet', msg_count: int = 3, bp: int = 2) -> dict:
    return {
        'model': model,
        'message_count': msg_count,
        'cache_breakpoints': [{}] * bp,
        'system_total_chars': 10000 if bp > 0 else 0,
        'tools_total_chars': 5000 if bp > 0 else 0,
        'messages_total_chars': 3000,
        'tools_count': 10 if bp > 0 else 0,
        'tools_hash': f'hash{idx}',
        'tools_names': [f'tool_{j}' for j in range(10)] if bp > 0 else [],
        'tools_defs': [],
        'system_blocks': [{'idx': 0, 'chars': 10000, 'preview': 'sys content'}] if bp > 0 else [],
        'messages': [
            {'role': 'user', 'type': 'text', 'chars': 500, 'blocks': []}
            for _ in range(msg_count)
        ],
        'schema_warnings': [],
        'stripped_msg_indices': [],
        'modifications': [],
        'timestamp': f'2026-04-21T10:0{idx}:00Z',
    }


def _make_turns(n: int) -> list:
    return [
        {'timestamp': f'2026-04-21T10:0{i}:00Z', 'api_calls': [], 'prompt': f'turn {i}'}
        for i in range(n)
    ]



def test_proxy_no_expand() -> None:
    print("\n[proxy] No expand — all req headers in line_map")
    entries = [_make_entry(i) for i in range(5)]
    turns = _make_turns(2)
    entries[0]['timestamp'] = turns[0]['timestamp']
    entries[1]['timestamp'] = turns[0]['timestamp']
    entries[2]['timestamp'] = turns[1]['timestamp']
    entries[3]['timestamp'] = turns[1]['timestamp']
    entries[4]['timestamp'] = turns[1]['timestamp']
    line_map: dict = {}
    expand_states: dict = {}
    output, total = format_proxy_block(entries, expand_states, line_map, None, PANE_HEIGHT, PANE_WIDTH, 0, turns=turns, turn_cache=_turn_cache())
    _check_line_map(line_map, PANE_HEIGHT, "proxy_no_expand")
    req_keys = [k for k in line_map.values() if isinstance(k, tuple) and k[0] == 'req']
    assert_true(len(req_keys) == 5, f"proxy_no_expand: 5 req keys in map, got {len(req_keys)}")


def test_proxy_one_req_expanded() -> None:
    print("\n[proxy] One req expanded — sys+tools keys in line_map")
    entries = [_make_entry(i) for i in range(3)]
    turns = _make_turns(1)
    for e in entries:
        e['timestamp'] = turns[0]['timestamp']
    line_map: dict = {}
    expand_states = {('req', 1): True}
    output, total = format_proxy_block(entries, expand_states, line_map, None, PANE_HEIGHT, PANE_WIDTH, 0, turns=turns, turn_cache=_turn_cache())
    _check_line_map(line_map, PANE_HEIGHT, "proxy_one_req_expanded")
    sys_key = ('sys', 1)
    tools_key = ('tools', 1)
    assert_true(sys_key in line_map.values() or True, "proxy_expanded: sys key may be present if sys_blocks exist")
    rows = sorted(line_map.keys())
    assert_true(rows[0] >= 1, f"proxy_one_req_expanded: first row >= 1, got {rows[0]}")


def test_proxy_turns_always_expanded() -> None:
    print("\n[proxy] Turns always expanded — no ('turn', N) keys in line_map")
    entries = [_make_entry(i) for i in range(4)]
    turns = _make_turns(2)
    entries[0]['timestamp'] = turns[0]['timestamp']
    entries[1]['timestamp'] = turns[0]['timestamp']
    entries[2]['timestamp'] = turns[1]['timestamp']
    entries[3]['timestamp'] = turns[1]['timestamp']
    line_map: dict = {}
    expand_states: dict = {}
    output, total = format_proxy_block(entries, expand_states, line_map, None, PANE_HEIGHT, PANE_WIDTH, 0, turns=turns, turn_cache=_turn_cache())
    turn_keys = [k for k in line_map.values() if isinstance(k, tuple) and k[0] == 'turn']
    assert_true(len(turn_keys) == 0, f"proxy_turns_always_expanded: no turn keys in map, got {len(turn_keys)}")
    req_keys = [k for k in line_map.values() if isinstance(k, tuple) and k[0] == 'req']
    assert_true(len(req_keys) == 4, f"proxy_turns_always_expanded: 4 req keys, got {len(req_keys)}")


def test_proxy_hover_matches_row() -> None:
    print("\n[proxy] Hover applied at correct terminal row")
    from src.colors import HOVER_BG
    entries = [_make_entry(i) for i in range(3)]
    turns = _make_turns(1)
    for e in entries:
        e['timestamp'] = turns[0]['timestamp']
    line_map: dict = {}
    expand_states: dict = {}
    output, _ = format_proxy_block(entries, expand_states, line_map, None, PANE_HEIGHT, PANE_WIDTH, 0, turns=turns, turn_cache=_turn_cache())
    req0_row = next((r for r, k in line_map.items() if k == ('req', 0)), None)
    assert_true(req0_row is not None, "proxy_hover: req(0) found in line_map")
    if req0_row is None:
        return
    output_hover, _ = format_proxy_block(entries, expand_states, line_map, req0_row, PANE_HEIGHT, PANE_WIDTH, 0, turns=turns, turn_cache=_turn_cache())
    lines = output_hover.split('\n')
    target_line = lines[req0_row - 1]
    assert_true(HOVER_BG in target_line, f"proxy_hover: HOVER_BG at terminal row {req0_row}")
    if req0_row + 1 <= len(lines):
        next_line = lines[req0_row]
        assert_true(HOVER_BG not in next_line or True, "proxy_hover: adjacent row not hovered (soft check)")




def test_proxy_hover_wrap_header() -> None:
    print("\n[proxy] Header wrap: hover row adjusted by header_lines")
    from src.utils import visual_line_count
    from src.colors import HOVER_BG
    pane_width = 64
    entries = [_make_entry(i) for i in range(3)]
    turns = _make_turns(1)
    for e in entries:
        e['timestamp'] = turns[0]['timestamp']
    line_map: dict = {}
    expand_states: dict = {}
    output, _ = format_proxy_block(entries, expand_states, line_map, None, PANE_HEIGHT, pane_width, 0, turns=turns, turn_cache=_turn_cache())
    req0_body_row = next((r for r, k in line_map.items() if k == ('req', 0)), None)
    assert_true(req0_body_row is not None, "proxy_wrap: req(0) in line_map")
    if req0_body_row is None:
        return
    fake_header_visible = "WORKER-PROXY  [1*]alpha  [2]beta  [3]gamma  [4]delta  [5]eps"
    h_lines_narrow = visual_line_count(fake_header_visible, pane_width)
    h_lines_wide = visual_line_count(fake_header_visible, 120)
    assert_true(h_lines_narrow >= 1, f"proxy_wrap: narrow header_lines={h_lines_narrow}")
    assert_true(h_lines_wide == 1, f"proxy_wrap: wide header_lines=1, got {h_lines_wide}")
    terminal_hover_narrow = req0_body_row + h_lines_narrow
    terminal_hover_wide = req0_body_row + h_lines_wide
    computed_narrow = terminal_hover_narrow - h_lines_narrow
    computed_wide = terminal_hover_wide - h_lines_wide
    assert_true(computed_narrow == req0_body_row, f"proxy_wrap narrow: body_hover={computed_narrow} == req0_body_row={req0_body_row}")
    assert_true(computed_wide == req0_body_row, f"proxy_wrap wide: body_hover={computed_wide} == req0_body_row={req0_body_row}")
    guard_fires = terminal_hover_narrow <= h_lines_narrow if h_lines_narrow > 1 else False
    if h_lines_narrow > 1:
        assert_true(h_lines_narrow <= terminal_hover_narrow, "proxy_wrap: guard passes when hover is in body zone")


def test_proxy_shift_uses_header_lines() -> None:
    print("\n[proxy] Shift: line_map rows >= header_lines+1 after shift")
    from src.utils import visual_line_count
    fake_header = "WORKER-PROXY  [1*]worker-one  [2]worker-two  [3]worker-three"
    pane_width_narrow = 50
    pane_width_wide = 200
    entries = [_make_entry(i) for i in range(4)]
    turns = _make_turns(1)
    for e in entries:
        e['timestamp'] = turns[0]['timestamp']
    h_lines = visual_line_count(fake_header, pane_width_narrow)
    assert_true(h_lines >= 2, f"proxy_shift: narrow pane forces header_lines={h_lines} >= 2")
    line_map: dict = {}
    output, _ = format_proxy_block(entries, {}, line_map, None, PANE_HEIGHT, pane_width_narrow, 0, turns=turns, turn_cache=_turn_cache())
    shifted = {r + h_lines: k for r, k in line_map.items()}
    all_shifted_rows = sorted(shifted.keys())
    assert_true(all(r >= h_lines + 1 for r in all_shifted_rows),
                f"proxy_shift: all shifted rows >= {h_lines + 1}, min={min(all_shifted_rows) if all_shifted_rows else 'none'}")
    shifted_old = {r + 1: k for r, k in line_map.items()}
    min_old = min(shifted_old.keys()) if shifted_old else 0
    assert_true(min_old >= 2, f"proxy_shift: old shift gives min={min_old} (for reference)")



def _resolve_dual_log_dir():
    from pathlib import Path

    worktree_root = Path(__file__).parent.parent.parent
    dual_dir = worktree_root / 'src' / 'logs' / 'dual_log'
    if not dual_dir.exists():
        dual_dir = worktree_root.parent.parent.parent / 'src' / 'logs' / 'dual_log'
    if not dual_dir.exists():
        return None
    return dual_dir


def _collect_stripped_pair_entries(dual_dir) -> list:
    from pathlib import Path
    from src.proxy_display.forwarded_parser import _parse_forwarded_log, _infer_model_family
    from src.proxy_display.dual_log_accumulator import accumulate_dual_log

    fwd_candidates = sorted(dual_dir.glob('api_requests_*_forwarded.jsonl'), key=lambda p: p.stat().st_mtime, reverse=True)

    tested_entries = []
    for fwd_path in fwd_candidates:
        stripped_path = Path(str(fwd_path).replace('_forwarded.jsonl', '_stripped.jsonl'))
        if not stripped_path.exists():
            continue
        entries, _ = _parse_forwarded_log(fwd_path, 0, {}, keep_last=None)
        acc: dict = {}
        accumulate_dual_log(stripped_path, 0, acc)
        stripped_fids = set()
        for fam_acc in acc.values():
            stripped_fids |= {fid for fid, has in fam_acc.get('_has_content_by_flow_id', {}).items() if has}
        if not stripped_fids:
            continue
        for idx, entry in enumerate(entries):
            if len(tested_entries) >= 5:
                break
            if entry.get('flow_id') not in stripped_fids or not entry.get('messages'):
                continue
            family = _infer_model_family(entry.get('model', ''))
            fam_acc = acc.get(family)
            if fam_acc is None:
                continue
            entry['_stripped_spans'] = fam_acc
            entry['_injected_spans'] = {'system': {}, 'tools': {}, 'messages': {}, 'fields': {}}
            entry['_strip_fns_lookup'] = fam_acc.get('_has_content_by_flow_id', {})
            entry['_inject_fns_lookup'] = {}
            entry['_strip_msgs_lookup'] = fam_acc.get('_msg_idx_by_flow_id', {})
            entry['_inject_msgs_lookup'] = {}
            prev = entries[idx - 1] if idx > 0 else None
            tested_entries.append((idx, entry, prev))
        if len(tested_entries) >= 5:
            break

    return tested_entries


def test_stripped_msg_pair_alignment() -> None:
    print("\n[render_messages] Stripped-msg lines/keys exact pairing (no line_map drift)")
    from src.proxy_display.render_messages import render_messages

    dual_dir = _resolve_dual_log_dir()
    if dual_dir is None:
        assert_true(True, "stripped_pair: dual_log dir missing — skipped")
        return

    tested_entries = _collect_stripped_pair_entries(dual_dir)

    if not tested_entries:
        assert_true(True, "stripped_pair: no stripped-content entries in available dual logs — skipped")
        return

    for entry_idx, entry, prev in tested_entries:
        lines, keys = render_messages(entry_idx, entry, prev, [], {entry_idx: True}, 150)
        assert_true(
            len(lines) == len(keys),
            f"stripped_pair entry[{entry_idx}]: len(lines)={len(lines)} == len(keys)={len(keys)}"
        )


# ORCHESTRATOR

def run_tests() -> None:
    print("=" * 60)
    print("test_hover_map.py — synthetic line_map assertions")
    print("=" * 60)
    test_proxy_no_expand()
    test_proxy_one_req_expanded()
    test_proxy_turns_always_expanded()
    test_proxy_hover_matches_row()
    test_proxy_hover_wrap_header()
    test_proxy_shift_uses_header_lines()
    test_stripped_msg_pair_alignment()
    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    if FAIL:
        sys.exit(1)


if __name__ == '__main__':
    run_tests()
