# INFRASTRUCTURE
import runpy
import sys
from functools import partial
from pathlib import Path

_AREA_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_AREA_DIR.parents[1]))
sys.path.insert(0, str(_AREA_DIR))

from dev.refactoring.strand_runner import strand_workflow

_MODULES = [
    'test_bg_task_detection',
    'test_block_broad_find',
    'test_block_broad_grep',
    'test_block_cli_chained',
    'test_block_dangerous_kill',
    'test_block_gh_cli_local_path',
    'test_block_git_destructive',
    'test_block_manual_worker_cleanup',
    'test_block_po_read',
    'test_block_rag_cli_document_repeat',
    'test_block_rag_cli_index_isolated',
    'test_block_rag_corpus_read',
    'test_block_rag_docs_layer',
    'test_block_unauthorized_background',
    'test_block_worker_kill_while_working',
    'test_block_worker_send_while_working',
    'test_fire_log',
    'test_hook_setup_main_branch_gate',
    'test_hook_trace_lines',
    'test_log_janitor',
    'test_rewrite_background_sleep',
    'test_rewrite_chained_sleep',
    'test_rewrite_worker_wait',
]
_STRAND_PREFIX = '_strand_'
_TITLE = 'hook_smoke run_all'
_REPORT_PATH = _AREA_DIR / 'md' / 'run_all.md'

# ORCHESTRATOR

def run_all_workflow() -> None:
    strand_globals = _register_strands(globals())
    sys.exit(strand_workflow(strand_globals, __file__, sorted(_strand_names()), _REPORT_PATH, _TITLE))

# FUNCTIONS

def _strand_names() -> list:
    return [_STRAND_PREFIX + module for module in _MODULES]

def _register_strands(script_globals: dict) -> dict:
    for module in _MODULES:
        script_globals[_STRAND_PREFIX + module] = partial(_run_module, module)
    return script_globals

def _run_module(module: str) -> None:
    try:
        runpy.run_path(str(_AREA_DIR / (module + '.py')), run_name='__main__')
    except SystemExit as exit_signal:
        if exit_signal.code not in (0, None):
            raise


if __name__ == '__main__':
    run_all_workflow()
