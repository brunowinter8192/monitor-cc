# INFRASTRUCTURE
import importlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))
os.environ.setdefault('MONITOR_CC_ROOT', str(WORKTREE_ROOT))

_ROOT_PKG = 'src'
mod_pane = importlib.import_module(f'{_ROOT_PKG}.proxy_display.pane')
mod_format = importlib.import_module(f'{_ROOT_PKG}.proxy_display.format')
mod_search = importlib.import_module(f'{_ROOT_PKG}.proxy_display.search')
mod_fwd = importlib.import_module(f'{_ROOT_PKG}.proxy_display.forwarded_parser')
mod_colors = importlib.import_module(f'{_ROOT_PKG}.colors')
mod_click = importlib.import_module(f'{_ROOT_PKG}.input.click_handler')

SEARCH_MATCH_BG = mod_colors.SEARCH_MATCH_BG
SEARCH_CURRENT_BG = mod_colors.SEARCH_CURRENT_BG
_BG_RESTORE_SENTINEL = mod_format._BG_RESTORE_SENTINEL

PANE_WIDTH = 120
_RESULTS = []


def check(label, condition):
    _RESULTS.append((label, bool(condition)))
    status = 'PASS' if condition else 'FAIL'
    print(f"  {status}  {label}")
    return condition


# FUNCTIONS

def _make_entry(idx: int, marker: str = None, model: str = 'claude-sonnet') -> dict:
    marker_text = marker or f'unique_marker_{idx}'
    messages = [{'role': 'user', 'type': 'text', 'chars': 10, 'blocks': []} for _ in range(idx)]
    messages.append({
        'role': 'user', 'type': 'text', 'chars': len(marker_text),
        'blocks': [{'type': 'text', 'chars': len(marker_text), 'preview': marker_text, 'full_text': marker_text, 'has_cc': False}],
    })
    return {
        'model': model,
        'message_count': idx + 1,
        'flow_id': f'flow-{idx}',
        'cache_breakpoints': [],
        'system_total_chars': 10000,
        'tools_total_chars': 5000,
        'messages_total_chars': 3000,
        'tools_count': 1,
        'tools_hash': f'hash{idx}',
        'tools_names': ['tool_a'],
        'tools_defs': [{'name': 'tool_a', 'description': 'd', 'input_schema': {}, 'stripped_original': None}],
        'system_blocks': [{'idx': 0, 'chars': 3, 'preview': 'sys', 'has_cc': False}],
        'messages': messages,
        'schema_warnings': [], 'stripped_msg_indices': [], 'modifications': [], '_stripped_spans': {'system': {}, 'tools': {}, 'messages': {}, 'fields': {}}, '_injected_spans': {'system': {}, 'tools': {}, 'messages': {}, 'fields': {}},
        'anthropic_beta': [], 'context_management': None, 'diagnostics': None,
        'effort_value': None, 'max_tokens': 0,
        'diff_from_prev': {'messages_added': 1},
        'timestamp': f'2026-04-21T10:{idx:02d}:00Z',
    }


def _reset_pane_state():
    mod_pane._proxy_session_start_ts = '2000-01-01T00:00:00Z'
    mod_pane.proxy_entries.clear()
    mod_pane.proxy_expand_states.clear()
    mod_pane.proxy_line_map.clear()
    mod_pane.proxy_hover_row = None
    mod_pane.proxy_scroll_offset = 0
    mod_pane._proxy_search.query = ''
    mod_pane._proxy_search.focused = False
    mod_pane._proxy_search.matches = []
    mod_pane._proxy_search.match_set = set()
    mod_pane._proxy_search.current_idx = 0
    mod_pane._proxy_just_expanded = None
    mod_pane._proxy_pane_width = PANE_WIDTH


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


def _read_keypress_from_bytes(byte_seq: bytes):
    r, w = os.pipe()
    orig_fd = mod_click._stdin_fd
    mod_click._stdin_fd = r
    try:
        os.write(w, byte_seq)
        return mod_click.read_keypress()
    finally:
        mod_click._stdin_fd = orig_fd
        os.close(r)
        os.close(w)
