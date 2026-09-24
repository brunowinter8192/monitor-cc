# INFRASTRUCTURE
import importlib
import os
import sys

ROOT = sys.argv[1]
PANE = sys.argv[2]
PROJECT_FILTER = sys.argv[3]
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault('MONITOR_CC_ROOT', ROOT)

_ROOT_PKG = 'src'
_WORKERS = [
    {'name': 'w1', 'status': 'working', 'session': 's1'},
    {'name': 'w2', 'status': 'working', 'session': 's2'},
]

# ORCHESTRATOR

def drive_workflow() -> None:
    monitor = importlib.import_module(f'{_ROOT_PKG}.core.monitor')
    monitor.active_project_filter = PROJECT_FILTER
    if PANE in ('worker_tokens', 'worker_proxy'):
        importlib.import_module(f'{_ROOT_PKG}.workers.worker_selection')._write_selection(PROJECT_FILTER, 'w1')
    _seed_and_run[PANE]()

# FUNCTIONS

def make_turn(idx: int, n_calls: int) -> dict:
    calls = []
    for c in range(n_calls):
        calls.append({
            'cache_read': 40000 + idx * 100 + c, 'cache_creation': 200 + c, 'direct': 5, 'output_tokens': 300 + c,
            'request_id': f'req_{idx}_{c}', 'timestamp': f'2026-01-01T10:{idx % 60:02d}:{c:02d}Z',
            'content_blocks': [
                {'type': 'tool_use', 'tool_name': 'Bash', 'preview': {'command': f'echo turn {idx} call {c}', 'description': 'x'}},
                {'type': 'text', 'preview': f'answer text {idx}/{c}'},
            ],
        })
    return {'prompt': f'prompt number {idx} with some words', 'timestamp': f'2026-01-01T10:{idx % 60:02d}:00Z', 'api_calls': calls}

def make_turns(count: int) -> list:
    return [make_turn(i, 2 + i % 3) for i in range(count)]

def make_proxy_entry(idx: int) -> dict:
    marker = f'unique_marker_{idx}'
    messages = [{'role': 'user', 'type': 'text', 'chars': 10, 'blocks': []} for _ in range(idx)]
    messages.append({
        'role': 'user', 'type': 'text', 'chars': len(marker),
        'blocks': [{'type': 'text', 'chars': len(marker), 'preview': marker, 'full_text': marker, 'has_cc': False}],
    })
    return {
        'model': 'claude-sonnet', 'message_count': idx + 1, 'flow_id': f'flow-{idx}', 'cache_breakpoints': [],
        'system_total_chars': 10000, 'tools_total_chars': 5000, 'messages_total_chars': 3000,
        'tools_count': 1, 'tools_hash': f'hash{idx}', 'tools_names': ['tool_a'],
        'tools_defs': [{'name': 'tool_a', 'description': 'd', 'input_schema': {}, 'stripped_original': None}],
        'system_blocks': [{'idx': 0, 'chars': 3, 'preview': 'sys', 'has_cc': False}],
        'messages': messages,
        'schema_warnings': [], 'stripped_msg_indices': [], 'modifications': [], '_stripped_spans': {'system': {}, 'tools': {}, 'messages': {}, 'fields': {}}, '_injected_spans': {'system': {}, 'tools': {}, 'messages': {}, 'fields': {}},
        'anthropic_beta': [], 'context_management': None, 'diagnostics': None,
        'effort_value': None, 'max_tokens': 0,
        'diff_from_prev': {'messages_added': 1},
        'timestamp': f'2026-04-21T10:{idx:02d}:00Z',
    }

def selected_worker() -> str:
    selection = importlib.import_module(f'{_ROOT_PKG}.workers.worker_selection')
    try:
        with open(selection.get_selection_file_path(PROJECT_FILTER), 'r', encoding='utf-8') as f:
            return f.read().strip()
    except OSError:
        return 'w1'

def run_tokens() -> None:
    mod = importlib.import_module(f'{_ROOT_PKG}.panes.token_pane')
    mod._cache_turns = make_turns(30)
    state = {'first': True}
    def refresh(now, input_changed, last_refresh, last_janitor):
        if state['first']:
            state['first'] = False
            return True, now, last_janitor
        return input_changed, now, last_janitor
    mod._refresh_tokens_data = refresh
    mod.run_tokens_loop()

def run_worker_tokens() -> None:
    mod = importlib.import_module(f'{_ROOT_PKG}.workers.worker_tokens_pane')
    mod._worker_tokens_workers = list(_WORKERS)
    state = {'first': True}
    def refresh(now, input_changed, last_refresh, monitor):
        if state['first'] or mod._worker_tokens_force_reload:
            state['first'] = False
            mod._worker_tokens_force_reload = False
            name = selected_worker()
            mod._worker_tokens_current_name = name
            mod._worker_tokens_turns = make_turns(30) if name == 'w1' else []
            return True, now
        return input_changed, now
    mod._refresh_worker_tokens_data = refresh
    mod.run_worker_tokens_loop()

def run_proxy() -> None:
    mod = importlib.import_module(f'{_ROOT_PKG}.proxy_display.pane')
    mod.proxy_entries.extend(make_proxy_entry(i) for i in range(12))
    monitor = importlib.import_module(f'{_ROOT_PKG}.core.monitor')
    monitor._get_session_start_ts = lambda: '2000-01-01T00:00:00Z'
    state = {'first': True}
    def refresh(now, input_changed, last_refresh, monitor):
        if state['first']:
            state['first'] = False
            return True, now
        return input_changed, now
    mod._refresh_proxy_data = refresh
    mod.run_proxy_loop()

def run_worker_proxy() -> None:
    mod = importlib.import_module(f'{_ROOT_PKG}.proxy_display.worker_proxy_pane')
    mod._worker_proxy_workers = list(_WORKERS)
    state = {'first': True}
    def refresh(now, input_changed, last_refresh, monitor):
        if state['first'] or mod._worker_proxy_force_reload:
            state['first'] = False
            mod._worker_proxy_force_reload = False
            name = selected_worker()
            mod._worker_proxy_last_worker_name = name
            mod.worker_proxy_entries.clear()
            if name == 'w1':
                mod.worker_proxy_entries.extend(make_proxy_entry(i) for i in range(12))
            return True, now
        return input_changed, now
    mod._refresh_worker_proxy_data = refresh
    mod.run_worker_proxy_loop()

_seed_and_run = {
    'tokens': run_tokens,
    'worker_tokens': run_worker_tokens,
    'proxy': run_proxy,
    'worker_proxy': run_worker_proxy,
}

if __name__ == '__main__':
    drive_workflow()
