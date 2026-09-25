# INFRASTRUCTURE
import importlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))
os.environ['MONITOR_CC_ROOT'] = str(WORKTREE_ROOT)

from dev.refactoring.strand_runner import check

_FIXED_TERMINAL = os.terminal_size((220, 50))
os.get_terminal_size = lambda fd=1: _FIXED_TERMINAL

_ROOT_PKG = 'src'
mod_wp = importlib.import_module(f'{_ROOT_PKG}.proxy_display.worker_proxy_pane')
mod_search_bar = importlib.import_module(f'{_ROOT_PKG}.search_bar')

PANE_WIDTH = 100


# FUNCTIONS

class _FakeMonitor:
    active_project_filter = 'proj'


def _make_wp_entry(idx: int, marker: str = None, model: str = 'claude-sonnet') -> dict:
    marker_text = marker or f'unique_marker_{idx}'
    messages = [{'role': 'user', 'type': 'text', 'chars': 10, 'blocks': []} for _ in range(idx)]
    messages.append({
        'role': 'user', 'type': 'text', 'chars': len(marker_text),
        'blocks': [{'type': 'text', 'chars': len(marker_text), 'preview': marker_text, 'full_text': marker_text, 'has_cc': False}],
    })
    return {
        'model': model, 'message_count': idx + 1, 'flow_id': f'flow-{idx}', 'cache_breakpoints': [],
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


def _reset_state(query: str = ''):
    mod_wp.worker_proxy_entries.clear()
    mod_wp.worker_proxy_expand_states.clear()
    mod_wp.worker_proxy_line_map.clear()
    mod_wp.worker_proxy_hover_row = None
    mod_wp.worker_proxy_scroll_offset = 0
    mod_wp._worker_proxy_pane_width = PANE_WIDTH
    mod_wp._worker_proxy_workers = []
    mod_wp._worker_proxy_header_regions.clear()
    mod_wp._worker_proxy_copy_rows.clear()
    mod_wp._worker_proxy_log_path = None
    mod_wp._wp_just_expanded = None
    mod_wp._worker_proxy_force_reload = False
    mod_wp._worker_proxy_last_worker_name = None
    mod_wp._worker_proxy_search.query = query
    mod_wp._worker_proxy_search.focused = False
    mod_wp._worker_proxy_search.matches = []
    mod_wp._worker_proxy_search.match_set = set()
    mod_wp._worker_proxy_search.current_idx = 0
    mod_search_bar.clear_selection(mod_wp._worker_proxy_search)


def _click(button, col, row):
    return mod_wp._handle_worker_proxy_mouse(button, col, row, _FakeMonitor())


def _capture_clipboard():
    captured = []
    orig = mod_wp.copy_to_clipboard
    mod_wp.copy_to_clipboard = lambda text: captured.append(text)
    return captured, orig


def _build_output_with_worker(worker_name):
    tmp_dir = Path(tempfile.mkdtemp(prefix='pane_search_p5_sel_'))
    sel_path = tmp_dir / 'selection.txt'
    if worker_name is not None:
        sel_path.write_text(worker_name, encoding='utf-8')
    orig = mod_wp.get_selection_file_path
    mod_wp.get_selection_file_path = lambda pf: sel_path
    try:
        return mod_wp._build_worker_proxy_output(_FakeMonitor())
    finally:
        mod_wp.get_selection_file_path = orig
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _fwd_line(flow_id: str, model: str, is_first: bool, msg_text: str) -> str:
    entry = {
        'type': 'forwarded_delta', 'request_id': '', 'timestamp': datetime.now(timezone.utc).isoformat(),
        'model': model, 'max_tokens': 100, 'output_config': None, 'context_management': None,
        'diagnostics': None, 'is_first': is_first,
        'counts': {'system': 0, 'tools': 0, 'messages': 1},
        'system_delta': {}, 'tools_delta': {},
        'messages_delta': {'0': {'role': 'user', 'content': msg_text}},
        'flow_id': flow_id,
    }
    return json.dumps(entry)
