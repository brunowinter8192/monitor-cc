# INFRASTRUCTURE
import importlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = sys.argv[1]
PANE = sys.argv[2]
JSONL_PATH = Path(sys.argv[3])
OUT_PATH = sys.argv[4]
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault('MONITOR_CC_ROOT', ROOT)

_ROOT_PKG = 'src'
_TERM = {'cols': 120, 'lines': 45}
_FAR_FUTURE = 10 ** 10


# ORCHESTRATOR

def sequence_workflow() -> None:
    os.get_terminal_size = lambda *a: os.terminal_size((_TERM['cols'], _TERM['lines']))
    pane = make_adapter(PANE)
    records = []
    run_sequence(pane, records)
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(records, f)


# FUNCTIONS

def make_adapter(pane_name: str) -> SimpleNamespace:
    cache_turns = importlib.import_module(f'{_ROOT_PKG}.panes.cache_turns')
    token_format = importlib.import_module(f'{_ROOT_PKG}.format.token_format')
    turns, _pos = cache_turns.build_cache_turns(JSONL_PATH, 0, [])
    counter = {'renders': 0}
    original = token_format._render_turn_lines
    def counting(*args, **kwargs):
        counter['renders'] += 1
        return original(*args, **kwargs)
    token_format._render_turn_lines = counting
    if pane_name == 'tokens':
        return tokens_adapter(turns, counter)
    return worker_tokens_adapter(turns, counter)


def tokens_adapter(turns: list, counter: dict) -> SimpleNamespace:
    mod = importlib.import_module(f'{_ROOT_PKG}.panes.token_pane')
    mod.copy_to_clipboard = lambda text: None
    mod._cache_turns = turns
    def build():
        return mod._build_tokens_output()
    def set_turns(new_turns):
        mod._cache_turns = new_turns
    def set_scroll(value):
        mod.cache_scroll_offset = value
    def scroll_of():
        return mod.cache_scroll_offset
    return SimpleNamespace(
        mod=mod, counter=counter, build=build, turns=lambda: mod._cache_turns, set_turns=set_turns,
        mouse=mod._handle_tokens_mouse, line_map=lambda: mod.cache_line_map, copy_rows=lambda: mod.cache_copy_rows,
        nav=lambda: mod._tokens_nav, feedback=lambda: mod._cache_copy_feedback_until,
        expand=lambda: mod.cache_expand_states, search=mod._tokens_search,
        search_input=mod._handle_tokens_search_input, search_cancel=mod._handle_tokens_search_cancel,
        jump=mod._jump_tokens_search_match, width=lambda: mod._cache_pane_width,
        rid_map=lambda: mod._response_rid_map, set_scroll=set_scroll, scroll_of=scroll_of,
        clear_nav=lambda: mod._tokens_nav.clear(),
    )


def worker_tokens_adapter(turns: list, counter: dict) -> SimpleNamespace:
    mod = importlib.import_module(f'{_ROOT_PKG}.workers.worker_tokens_pane')
    mod.copy_to_clipboard = lambda text: None
    mod._read_selected_worker_name = lambda monitor: 'w1'
    mod._worker_tokens_workers = [{'name': 'w1', 'status': 'working', 'session': 's1'}]
    mod._worker_tokens_turns = turns
    monitor = SimpleNamespace(active_project_filter='/tmp/flk_m2_proj')
    def build():
        result = mod._build_worker_tokens_output(monitor)
        return result[0] if isinstance(result, tuple) else result
    def set_turns(new_turns):
        mod._worker_tokens_turns = new_turns
    def set_scroll(value):
        mod.worker_tokens_scroll_offset = value
    return SimpleNamespace(
        mod=mod, counter=counter, build=build, turns=lambda: mod._worker_tokens_turns, set_turns=set_turns,
        mouse=lambda b, c, r: mod._handle_worker_tokens_mouse(b, c, r, monitor),
        line_map=lambda: mod.worker_tokens_line_map, copy_rows=lambda: mod.worker_tokens_copy_rows,
        nav=lambda: mod._worker_tokens_nav, feedback=lambda: mod._worker_tokens_copy_feedback_until,
        expand=lambda: mod.worker_tokens_expand_states, search=mod._worker_tokens_search,
        search_input=mod._handle_worker_tokens_search_input, search_cancel=mod._handle_worker_tokens_search_cancel,
        jump=mod._jump_worker_tokens_search_match, width=lambda: mod._worker_tokens_pane_width,
        rid_map=lambda: {}, set_scroll=set_scroll, scroll_of=lambda: mod.worker_tokens_scroll_offset,
        clear_nav=lambda: mod._worker_tokens_nav.clear(),
    )


def run_sequence(pane: SimpleNamespace, records: list) -> None:
    hover_scroll_and_expand(pane, records)
    copy_feedback_phase(pane, records)
    response_entry_phase(pane, records)
    search_phase(pane, records)
    width_phase(pane, records)
    growth_and_reset_phase(pane, records)


def hover_scroll_and_expand(pane: SimpleNamespace, records: list) -> None:
    snapshot(pane, 'initial', records)
    for row in (3, 4, 5, 6, 7, 8, 9):
        hover(pane, row)
        snapshot(pane, f'hover_row_{row}', records)
    for _ in range(3):
        pane.mouse(64, 10, 6)
    snapshot(pane, 'scroll_up_3x', records)
    hover(pane, 7)
    snapshot(pane, 'hover_after_scroll', records)
    rows = key_rows(pane)
    pane.mouse(0, 10, rows[0])
    snapshot(pane, 'expand_first_visible_call', records)
    hover(pane, rows[0] + 1)
    snapshot(pane, 'hover_after_expand', records)
    rows = key_rows(pane)
    pane.mouse(0, 10, rows[min(3, len(rows) - 1)])
    snapshot(pane, 'expand_second_call', records)
    pane.set_scroll(10 ** 6)
    snapshot(pane, 'scroll_to_top', records)
    rows = key_rows(pane)
    pane.mouse(0, 10, rows[0])
    snapshot(pane, 'expand_call_in_oldest_turn', records)
    hover(pane, 5)
    snapshot(pane, 'hover_in_oldest_turn', records)
    pane.mouse(0, 10, key_rows(pane)[0])
    snapshot(pane, 'collapse_call_in_oldest_turn', records)


def snapshot(pane: SimpleNamespace, name: str, records: list) -> None:
    pane.counter['renders'] = 0
    exc = None
    output = None
    try:
        output = pane.build()
    except Exception as e:
        exc = type(e).__name__
    records.append({
        'name': name, 'output': output, 'exc': exc, 'turn_renders': pane.counter['renders'],
        'line_map': sorted((r, repr(k)) for r, k in pane.line_map().items()),
        'copy_rows': sorted(pane.copy_rows()),
        'nav': sorted((repr(k), v) for k, v in pane.nav().items()),
        'scroll': pane.scroll_of(), 'width': pane.width(),
    })


def hover(pane: SimpleNamespace, row: int) -> None:
    pane.mouse(35, 10, row)


def key_rows(pane: SimpleNamespace) -> list:
    return sorted(pane.line_map())


def copy_feedback_phase(pane: SimpleNamespace, records: list) -> None:
    copy_rows = sorted(pane.copy_rows())
    pane.mouse(0, pane.width() - 1, copy_rows[0])
    key = pane.line_map()[copy_rows[0]]
    pane.feedback()[key] = _FAR_FUTURE
    snapshot(pane, 'copy_feedback_on', records)
    hover(pane, copy_rows[0] + 1)
    snapshot(pane, 'hover_with_feedback_active', records)
    pane.feedback().clear()
    snapshot(pane, 'copy_feedback_expired', records)
    pane.set_scroll(0)
    snapshot(pane, 'scroll_bottom', records)


def response_entry_phase(pane: SimpleNamespace, records: list) -> None:
    expanded_key = expand_call_with_request_id(pane)
    snapshot(pane, 'expand_call_with_request_id', records)
    turn_idx, call_idx = expanded_key
    rid = pane.turns()[turn_idx]['api_calls'][call_idx].get('request_id', '')
    if rid:
        entry = {
            'headers': {'anthropic-ratelimit-unified-5h-utilization': '0.42', 'anthropic-ratelimit-unified-5h-reset': '1790000000',
                        'anthropic-ratelimit-unified-7d-utilization': '0.10', 'anthropic-ratelimit-unified-status': 'allowed'},
            'answering_model': 'model-a', 'proxy_forwarded_model': 'model-a',
        }
        pane.rid_map()[rid] = entry
        snapshot(pane, 'response_entry_added', records)
        entry['answering_model'] = 'model-b'
        snapshot(pane, 'response_entry_mutated_in_place', records)
        pane.rid_map()[rid] = dict(entry, answering_model='model-c')
        snapshot(pane, 'response_entry_replaced', records)


def expand_call_with_request_id(pane: SimpleNamespace) -> tuple:
    for row in reversed(key_rows(pane)[:-1]):
        key = pane.line_map()[row]
        if key[0] != 'turn' and pane.turns()[key[0]]['api_calls'][key[1]].get('request_id'):
            pane.mouse(0, 10, row)
            return key
    raise RuntimeError('no visible call with a request_id')


def search_phase(pane: SimpleNamespace, records: list) -> None:
    query = first_call_word(pane.turns())
    type_query(pane, query)
    snapshot(pane, 'search_committed', records)
    for i in range(3):
        pane.jump(True)
        snapshot(pane, f'search_next_{i}', records)
    pane.jump(False)
    snapshot(pane, 'search_prev', records)
    hover(pane, 8)
    snapshot(pane, 'hover_during_search', records)
    pane.search_cancel()
    snapshot(pane, 'search_cancelled', records)
    type_query(pane, 'zzzqqq')
    snapshot(pane, 'search_no_match', records)
    pane.search_cancel()
    snapshot(pane, 'search_cancelled_again', records)


def first_call_word(turns: list) -> str:
    for turn in turns:
        for call in turn.get('api_calls', []):
            for block in call.get('content_blocks', []):
                if block.get('type') == 'tool_use' and block.get('tool_name'):
                    return block['tool_name'].lower()
    return 'text'


def type_query(pane: SimpleNamespace, query: str) -> None:
    pane.search.focused = True
    for ch in query:
        pane.search_input(ch)
    pane.search_input('\r')


def width_phase(pane: SimpleNamespace, records: list) -> None:
    _TERM['cols'] = 50
    snapshot(pane, 'width_50', records)
    hover(pane, 6)
    snapshot(pane, 'hover_width_50', records)
    _TERM['cols'] = 120
    snapshot(pane, 'width_120_again', records)
    hover(pane, 6)
    snapshot(pane, 'hover_width_120', records)


def growth_and_reset_phase(pane: SimpleNamespace, records: list) -> None:
    pane.set_scroll(0)
    turns = pane.turns()
    pane.set_turns(turns + [make_new_turn(turns)])
    snapshot(pane, 'new_turn_appended', records)
    pane.set_turns(grow_last_turn(pane.turns()))
    snapshot(pane, 'last_turn_grew_1', records)
    pane.set_turns(grow_last_turn(pane.turns()))
    snapshot(pane, 'last_turn_grew_2', records)
    hover(pane, 9)
    snapshot(pane, 'hover_after_growth', records)
    saved = pane.turns()
    pane.set_turns([])
    pane.clear_nav()
    snapshot(pane, 'session_reset_empty', records)
    pane.set_turns(list(saved))
    snapshot(pane, 'session_restored_new_list', records)
    hover(pane, 5)
    snapshot(pane, 'hover_final', records)


def make_new_turn(turns: list) -> dict:
    last = turns[-1]
    return {'prompt': 'appended turn prompt', 'timestamp': last.get('timestamp', ''), 'api_calls': [dict(c) for c in last.get('api_calls', [])[:2]]}


def grow_last_turn(turns: list) -> list:
    last = dict(turns[-1])
    calls = list(last.get('api_calls', []))
    extra = dict(calls[-1]) if calls else {'cache_read': 1, 'cache_creation': 1, 'direct': 1, 'output_tokens': 1, 'content_blocks': []}
    extra['request_id'] = extra.get('request_id', 'x') + '_grown'
    extra['cache_creation'] = extra.get('cache_read', 0) + 5
    calls.append(extra)
    last['api_calls'] = calls
    return turns[:-1] + [last]


if __name__ == '__main__':
    sequence_workflow()
