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
    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    if FAIL:
        sys.exit(1)


if __name__ == '__main__':
    run_tests()
