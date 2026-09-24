# INFRASTRUCTURE
import atexit
import importlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))
os.environ['MONITOR_CC_ROOT'] = str(WORKTREE_ROOT)

from dev.refactoring.strand_runner import check

_FIXED_TERMINAL = os.terminal_size((220, 50))
os.get_terminal_size = lambda fd=1: _FIXED_TERMINAL

_ROOT_PKG = 'src'
mod_wt = importlib.import_module(f'{_ROOT_PKG}.workers.worker_tokens_pane')
mod_search_bar = importlib.import_module(f'{_ROOT_PKG}.search_bar')
mod_colors = importlib.import_module(f'{_ROOT_PKG}.colors')

PANE_WIDTH = 100
_PROJECT_FILTER = f'/tmp/p7proj_{os.getpid()}'
_MONITOR = SimpleNamespace(active_project_filter=_PROJECT_FILTER)
_TMP_ROOT = None


# FUNCTIONS

def _reset_state(query: str = ''):
    mod_wt.worker_tokens_expand_states.clear()
    mod_wt.worker_tokens_line_map.clear()
    mod_wt.worker_tokens_hover_row = None
    mod_wt.worker_tokens_scroll_offset = 0
    mod_wt.worker_tokens_copy_rows.clear()
    mod_wt._worker_tokens_copy_feedback_until.clear()
    mod_wt._worker_tokens_pane_width = PANE_WIDTH
    mod_wt._worker_tokens_turns = []
    mod_wt._worker_tokens_workers = []
    mod_wt._worker_tokens_current_name = None
    mod_wt._worker_tokens_force_reload = False
    mod_wt._worker_tokens_header_regions.clear()
    mod_wt._worker_tokens_header_lines = 2
    mod_wt._worker_tokens_nav.clear()
    mod_wt._worker_tokens_search.query = query
    mod_wt._worker_tokens_search.focused = False
    mod_wt._worker_tokens_search.matches = []
    mod_wt._worker_tokens_search.match_set = set()
    mod_wt._worker_tokens_search.current_idx = 0
    mod_search_bar.clear_selection(mod_wt._worker_tokens_search)
    _remove_selection_file()
    atexit.register(_remove_selection_file)


def _remove_selection_file():
    Path(mod_wt.get_selection_file_path(_PROJECT_FILTER)).unlink(missing_ok=True)


def _select_worker(name: str, workers: list) -> None:
    mod_wt._worker_tokens_workers = workers
    mod_wt.write_selection(_PROJECT_FILTER, name)
    mod_wt._worker_tokens_current_name = name


def _setup_one_worker_jsonl(name: str, prompt: str, call_marker: str = None):
    global _TMP_ROOT
    _TMP_ROOT = Path(tempfile.mkdtemp(prefix='pane_search_p7_'))
    session = f'sess-{name}'
    path = _TMP_ROOT / f'{name}.jsonl'
    lines = [json.dumps({
        'type': 'user', 'userType': 'external', 'message': {'content': prompt},
        'timestamp': '2026-01-01T00:00:00Z',
    })]
    if call_marker:
        content = [{'type': 'tool_use', 'name': 'Bash', 'input': {'command': call_marker}}]
        lines.append(json.dumps({
            'type': 'assistant',
            'message': {
                'usage': {'cache_read_input_tokens': 1000, 'cache_creation_input_tokens': 0,
                          'input_tokens': 0, 'output_tokens': 10},
                'content': content,
            },
            'timestamp': '2026-01-01T00:00:01Z',
        }))
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    worker = {'name': name, 'status': 'working', 'session': session}
    orig_find = mod_wt.find_worker_jsonl
    mod_wt.find_worker_jsonl = lambda s, _p=path, _s=session: (_p if s == _s else None)
    return worker, orig_find


def _cleanup_worker_jsonl(orig_find):
    global _TMP_ROOT
    mod_wt.find_worker_jsonl = orig_find
    if _TMP_ROOT:
        shutil.rmtree(_TMP_ROOT, ignore_errors=True)
        _TMP_ROOT = None


def _load_turns_via_refresh(worker: dict) -> None:
    _select_worker(worker['name'], [worker])
    jsonl_path = mod_wt.find_worker_jsonl(worker['session'])
    turns, pos = mod_wt.build_cache_turns(jsonl_path, 0, [])
    mod_wt._worker_tokens_turns = turns
    mod_wt._worker_tokens_jsonl_position = pos


def _capture_clipboard():
    captured = []
    orig = mod_wt.copy_to_clipboard
    mod_wt.copy_to_clipboard = lambda text: captured.append(text)
    return captured, orig
