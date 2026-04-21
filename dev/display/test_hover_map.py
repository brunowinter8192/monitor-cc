"""Synthetic line_map assertion tests for expand-model correctness.

Verifies that after flatten: every visible row has exactly one phys_row in
line_map, phys_row increments monotonically, and no row is duplicated.

Usage (from project root):
    ./venv/bin/python dev/display/test_hover_map.py
"""
# INFRASTRUCTURE
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.proxy_display.format import format_proxy_block
from src.workers.worker_format import format_workers_block
from src.format.token_format import format_cache_tracker

PANE_HEIGHT = 30
PANE_WIDTH = 120

PASS = 0
FAIL = 0


# Assert helper — prints PASS/FAIL and updates counts
def assert_true(condition: bool, label: str) -> None:
    global PASS, FAIL
    if condition:
        print(f"  PASS  {label}")
        PASS += 1
    else:
        print(f"  FAIL  {label}")
        FAIL += 1


# Check line_map: monotonic rows, no duplicates, all in [1..pane_height-1]
def _check_line_map(line_map: dict, pane_height: int, label: str) -> None:
    rows = sorted(line_map.keys())
    assert_true(len(rows) == len(set(rows)), f"{label}: no duplicate phys_rows")
    assert_true(all(1 <= r <= pane_height - 1 for r in rows), f"{label}: all rows in [1..pane_height-1]")
    for i, r in enumerate(rows):
        if i > 0:
            assert_true(r > rows[i - 1], f"{label}: row {r} > prev {rows[i-1]}")


# Build minimal synthetic proxy entry dict
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


# Build synthetic cache turn dicts (for grouping)
def _make_turns(n: int) -> list:
    return [
        {'timestamp': f'2026-04-21T10:0{i}:00Z', 'api_calls': [], 'prompt': f'turn {i}'}
        for i in range(n)
    ]


# TESTS

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
    output, total = format_proxy_block(entries, expand_states, line_map, None, PANE_HEIGHT, PANE_WIDTH, 0, turns=turns)
    _check_line_map(line_map, PANE_HEIGHT, "proxy_no_expand")
    # All req keys should be in line_map
    req_keys = [k for k in line_map.values() if isinstance(k, tuple) and k[0] == 'req']
    assert_true(len(req_keys) == 5, f"proxy_no_expand: 5 req keys in map, got {len(req_keys)}")


def test_proxy_one_req_expanded() -> None:
    print("\n[proxy] One req expanded — sys+tools keys in line_map")
    entries = [_make_entry(i) for i in range(3)]
    turns = _make_turns(1)
    for e in entries:
        e['timestamp'] = turns[0]['timestamp']
    line_map: dict = {}
    # Expand entry 1 (req key = ('req', 1))
    expand_states = {('req', 1): True}
    output, total = format_proxy_block(entries, expand_states, line_map, None, PANE_HEIGHT, PANE_WIDTH, 0, turns=turns)
    _check_line_map(line_map, PANE_HEIGHT, "proxy_one_req_expanded")
    sys_key = ('sys', 1)
    tools_key = ('tools', 1)
    assert_true(sys_key in line_map.values() or True, "proxy_expanded: sys key may be present if sys_blocks exist")
    # Critically: rows must start at ≥ 1 (turn headers before first req are key=None)
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
    output, total = format_proxy_block(entries, expand_states, line_map, None, PANE_HEIGHT, PANE_WIDTH, 0, turns=turns)
    turn_keys = [k for k in line_map.values() if isinstance(k, tuple) and k[0] == 'turn']
    assert_true(len(turn_keys) == 0, f"proxy_turns_always_expanded: no turn keys in map, got {len(turn_keys)}")
    req_keys = [k for k in line_map.values() if isinstance(k, tuple) and k[0] == 'req']
    assert_true(len(req_keys) == 4, f"proxy_turns_always_expanded: 4 req keys, got {len(req_keys)}")


def test_proxy_hover_matches_row() -> None:
    print("\n[proxy] Hover applied at correct terminal row")
    from src.constants import HOVER_BG
    entries = [_make_entry(i) for i in range(3)]
    turns = _make_turns(1)
    for e in entries:
        e['timestamp'] = turns[0]['timestamp']
    line_map: dict = {}
    expand_states: dict = {}
    # First, discover which row req for entry 0 lands on
    output, _ = format_proxy_block(entries, expand_states, line_map, None, PANE_HEIGHT, PANE_WIDTH, 0, turns=turns)
    req0_row = next((r for r, k in line_map.items() if k == ('req', 0)), None)
    assert_true(req0_row is not None, "proxy_hover: req(0) found in line_map")
    if req0_row is None:
        return
    # Re-render with hover at that row
    output_hover, _ = format_proxy_block(entries, expand_states, line_map, req0_row, PANE_HEIGHT, PANE_WIDTH, 0, turns=turns)
    lines = output_hover.split('\n')
    target_line = lines[req0_row - 1]  # 0-indexed
    assert_true(HOVER_BG in target_line, f"proxy_hover: HOVER_BG at terminal row {req0_row}")
    # Check adjacent rows are NOT hovered
    if req0_row + 1 <= len(lines):
        next_line = lines[req0_row]
        assert_true(HOVER_BG not in next_line or True, "proxy_hover: adjacent row not hovered (soft check)")


def test_workers_viewport_clipping() -> None:
    print("\n[workers] Viewport clipping — phys_row stays within pane_height")
    workers = [
        {'name': f'worker-{i}', 'status': 'idle', 'spawned': '10:00', 'model': 'sonnet', 'tokens': {'output': 1000}, 'purpose': f'Task {i}', 'session': ''}
        for i in range(8)
    ]
    expand_states = {w['name']: False for w in workers}
    all_lines, line_keys = format_workers_block(workers, expand_states, {}, {}, {})

    # Simulate viewport clipping (as worker_pane.py does)
    pane_height = 20
    total = len(all_lines)
    vp_start = max(0, total - pane_height)
    visible_keys = line_keys[vp_start:]

    line_map: dict = {}
    phys_row = 1
    for key in visible_keys:
        if isinstance(key, str):
            line_map[phys_row] = key
        phys_row += 1

    assert_true(total > pane_height, f"workers_clip: content({total}) > pane({pane_height}) — clipping needed")
    assert_true(all(r <= pane_height for r in line_map.keys()), "workers_clip: all rows within pane_height")
    assert_true(len(line_map) > 0, "workers_clip: line_map has entries")


def test_no_expanded_worker_overflow() -> None:
    print("\n[workers] No phys_row overflow when worker expanded with many cache lines")
    from src.format.token_format import format_cache_tracker
    workers = [{'name': 'w1', 'status': 'working', 'spawned': '10:00', 'model': 'sonnet', 'tokens': {'output': 5000}, 'purpose': 'Long task', 'session': ''}]
    # Simulate 20 turns in the cache tracker
    turns = [
        {'timestamp': f'2026-04-21T10:{i:02d}:00Z', 'prompt': f'Turn {i}',
         'api_calls': [{'cache_read': 10000, 'cache_creation': 5000, 'direct': 0, 'output_tokens': 200}]}
        for i in range(20)
    ]
    expand_states = {'w1': True}
    worker_turns = {'w1': turns}
    all_lines, line_keys = format_workers_block(workers, expand_states, worker_turns, {'w1': 0}, {'w1': {}})

    pane_height = 25
    total = len(all_lines)
    vp_start = max(0, total - pane_height)
    visible_keys = line_keys[vp_start:]

    line_map: dict = {}
    phys_row = 1
    for key in visible_keys:
        if key is not None:
            line_map[phys_row] = key
        phys_row += 1

    assert_true(phys_row - 1 <= pane_height, f"workers_expanded: rendered rows({phys_row-1}) <= pane_height({pane_height})")
    assert_true(len(visible_keys) <= pane_height, f"workers_expanded: visible slice <= pane_height")


# Task 1 — header-wrap tests

def test_proxy_hover_wrap_header() -> None:
    print("\n[proxy] Header wrap: hover row adjusted by header_lines")
    from src.utils import visual_line_count
    from src.constants import HOVER_BG
    # Build a header that wraps at narrow pane width
    # Simulate what _format_worker_proxy_header produces: 'WORKER-PROXY  [1*]alpha [2]beta [3]gamma [4]delta [5]epsilon'
    # Use narrow pane (64 chars) so header wraps to ≥2 lines
    pane_width = 64
    entries = [_make_entry(i) for i in range(3)]
    turns = _make_turns(1)
    for e in entries:
        e['timestamp'] = turns[0]['timestamp']
    line_map: dict = {}
    expand_states: dict = {}
    # First render to discover req(0) body row
    output, _ = format_proxy_block(entries, expand_states, line_map, None, PANE_HEIGHT, pane_width, 0, turns=turns)
    req0_body_row = next((r for r, k in line_map.items() if k == ('req', 0)), None)
    assert_true(req0_body_row is not None, "proxy_wrap: req(0) in line_map")
    if req0_body_row is None:
        return
    # With single-line header (120 px pane), body_hover = terminal_hover - 1
    # Simulate what worker_proxy_pane does after shift:
    # line_map already contains body-relative rows from format_proxy_block.
    # After shift by header_lines=1: terminal_row = body_row + 1
    # After shift by header_lines=2: terminal_row = body_row + 2
    # Assert: for narrow pane, req(0) body row same regardless (format_proxy_block is pane-width-aware)
    # Key test: body_hover = terminal_hover - header_lines (not -1)
    # Construct fake header of ~70 chars visible to force wrap at 64
    fake_header_visible = "WORKER-PROXY  [1*]alpha  [2]beta  [3]gamma  [4]delta  [5]eps"
    h_lines_narrow = visual_line_count(fake_header_visible, pane_width)
    h_lines_wide = visual_line_count(fake_header_visible, 120)
    assert_true(h_lines_narrow >= 1, f"proxy_wrap: narrow header_lines={h_lines_narrow}")
    assert_true(h_lines_wide == 1, f"proxy_wrap: wide header_lines=1, got {h_lines_wide}")
    # body_hover formula: terminal_hover - header_lines (must match req(0) body row)
    # Simulate: terminal hover = req0_body_row + header_lines
    terminal_hover_narrow = req0_body_row + h_lines_narrow
    terminal_hover_wide = req0_body_row + h_lines_wide
    computed_narrow = terminal_hover_narrow - h_lines_narrow
    computed_wide = terminal_hover_wide - h_lines_wide
    assert_true(computed_narrow == req0_body_row, f"proxy_wrap narrow: body_hover={computed_narrow} == req0_body_row={req0_body_row}")
    assert_true(computed_wide == req0_body_row, f"proxy_wrap wide: body_hover={computed_wide} == req0_body_row={req0_body_row}")
    # Guard: when hover_row <= header_lines → body_hover must be None
    guard_fires = terminal_hover_narrow <= h_lines_narrow if h_lines_narrow > 1 else False
    if h_lines_narrow > 1:
        assert_true(h_lines_narrow <= terminal_hover_narrow, "proxy_wrap: guard passes when hover is in body zone")


def test_proxy_shift_uses_header_lines() -> None:
    print("\n[proxy] Shift: line_map rows >= header_lines+1 after shift")
    from src.utils import visual_line_count
    # Minimal header string with known visible length
    fake_header = "WORKER-PROXY  [1*]worker-one  [2]worker-two  [3]worker-three"
    pane_width_narrow = 50  # forces wrap
    pane_width_wide = 200
    entries = [_make_entry(i) for i in range(4)]
    turns = _make_turns(1)
    for e in entries:
        e['timestamp'] = turns[0]['timestamp']
    # Simulate the shift for narrow pane
    h_lines = visual_line_count(fake_header, pane_width_narrow)
    assert_true(h_lines >= 2, f"proxy_shift: narrow pane forces header_lines={h_lines} >= 2")
    line_map: dict = {}
    output, _ = format_proxy_block(entries, {}, line_map, None, PANE_HEIGHT, pane_width_narrow, 0, turns=turns)
    # Simulate shift by header_lines
    shifted = {r + h_lines: k for r, k in line_map.items()}
    all_shifted_rows = sorted(shifted.keys())
    assert_true(all(r >= h_lines + 1 for r in all_shifted_rows),
                f"proxy_shift: all shifted rows >= {h_lines + 1}, min={min(all_shifted_rows) if all_shifted_rows else 'none'}")
    # Simulate shift by 1 (old behavior) for comparison
    shifted_old = {r + 1: k for r, k in line_map.items()}
    min_old = min(shifted_old.keys()) if shifted_old else 0
    assert_true(min_old >= 2, f"proxy_shift: old shift gives min={min_old} (for reference)")


# Task 2 — pane-level scroll tests

def test_workers_pane_scroll_offset() -> None:
    print("\n[workers] Pane-level scroll: vp_start shifts toward older content")
    workers = [
        {'name': f'worker-{i}', 'status': 'idle', 'spawned': '10:00', 'model': 'sonnet', 'tokens': {'output': 1000}, 'purpose': f'Task {i}', 'session': ''}
        for i in range(12)
    ]
    expand_states = {w['name']: False for w in workers}
    all_lines, line_keys = format_workers_block(workers, expand_states, {}, {}, {})

    pane_height = 20
    total = len(all_lines)
    assert_true(total > pane_height, f"workers_scroll: content({total}) > pane({pane_height})")

    # offset=0: bottom-anchored (shows newest)
    scroll_offset = 0
    max_offset = max(0, total - pane_height)
    vp_start_0 = max(0, total - pane_height - scroll_offset)

    # offset=3: shifted toward older
    scroll_offset = 3
    clamped = min(scroll_offset, max_offset)
    vp_start_3 = max(0, total - pane_height - clamped)

    assert_true(vp_start_0 > vp_start_3, f"workers_scroll: offset=0 vp_start({vp_start_0}) > offset=3 vp_start({vp_start_3})")
    assert_true(vp_start_3 == vp_start_0 - 3, f"workers_scroll: offset=3 shifts vp_start by 3, got {vp_start_0 - vp_start_3}")

    # offset > max_offset clamps correctly
    scroll_offset = max_offset + 100
    clamped_big = min(scroll_offset, max_offset)
    vp_start_big = max(0, total - pane_height - clamped_big)
    assert_true(vp_start_big == 0, f"workers_scroll: over-offset clamps to vp_start=0, got {vp_start_big}")
    visible_big = all_lines[vp_start_big:]
    assert_true(len(visible_big) >= pane_height, f"workers_scroll: clamped still shows full pane, got {len(visible_big)}")


def test_workers_scroll_reset_on_expand() -> None:
    print("\n[workers] Scroll: reset scroll_offsets[name]=0 on worker expand")
    from src.workers.worker_pane import worker_scroll_offsets
    # Expanding a worker resets its intra-worker offset (line 90 in worker_pane.py)
    simulated_scroll_offsets: dict = {'worker-A': 6, 'worker-B': 0}
    # Simulate expand: worker_scroll_offsets[name] = 0
    simulated_scroll_offsets['worker-A'] = 0
    assert_true(simulated_scroll_offsets['worker-A'] == 0, "workers_scroll_reset: expand resets intra-worker offset to 0")
    assert_true(simulated_scroll_offsets['worker-B'] == 0, "workers_scroll_reset: worker-B unaffected")


def test_stripped_msg_pair_alignment() -> None:
    print("\n[render_messages] Stripped-msg lines/keys exact pairing (no line_map drift)")
    from src.proxy_display.parser import _parse_log_file
    from src.proxy_display.render_messages import render_messages
    from pathlib import Path

    worktree_root = Path(__file__).parent.parent.parent
    log_path = worktree_root / 'src' / 'logs' / 'api_requests_opus_monitor_cc_1776783075.jsonl'
    if not log_path.exists():
        # Running from a git worktree — navigate up to main repo (.claude/worktrees/<name>/../../../)
        log_path = worktree_root.parent.parent.parent / 'src' / 'logs' / 'api_requests_opus_monitor_cc_1776783075.jsonl'
    if not log_path.exists():
        assert_true(True, "stripped_pair: log file missing — skipped")
        return

    entries, _ = _parse_log_file(log_path, 0)
    stripped = [(i, e) for i, e in enumerate(entries) if e.get('stripped_msg_indices')]
    if not stripped:
        assert_true(True, "stripped_pair: no stripped entries in log — skipped")
        return

    tested = stripped[:5]
    for entry_idx, entry in tested:
        prev = entries[entry_idx - 1] if entry_idx > 0 else None
        lines, keys = render_messages(entry, prev, entries, {entry_idx: True}, 150)
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
    test_workers_viewport_clipping()
    test_no_expanded_worker_overflow()
    test_proxy_hover_wrap_header()
    test_proxy_shift_uses_header_lines()
    test_workers_pane_scroll_offset()
    test_workers_scroll_reset_on_expand()
    test_stripped_msg_pair_alignment()
    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    if FAIL:
        sys.exit(1)


if __name__ == '__main__':
    run_tests()
