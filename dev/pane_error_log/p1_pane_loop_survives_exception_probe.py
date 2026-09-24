# INFRASTRUCTURE
import sys
from pathlib import Path

from p1_pane_tests import (
    test_gpu_pane, test_keyboard_interrupt_and_system_exit_not_swallowed, test_news_log_pane,
    test_news_pane, test_proxy_pane, test_tokens_pane, test_warnings_pane,
    test_worker_proxy_pane, test_worker_tokens_pane,
)
from p1_sink_tests import test_failing_log_write_does_not_raise, test_log_size_capping

from dev.refactoring.strand_runner import strand_workflow

_STRAND_NAMES = [
    'test_worker_tokens_pane',
    'test_proxy_pane',
    'test_worker_proxy_pane',
    'test_tokens_pane',
    'test_warnings_pane',
    'test_gpu_pane',
    'test_news_pane',
    'test_news_log_pane',
    'test_keyboard_interrupt_and_system_exit_not_swallowed',
    'test_failing_log_write_does_not_raise',
    'test_log_size_capping',
]
_TITLE = 'pane_error_log probe: 8 pane loops survive an uncaught exception'
_REPORT_PATH = Path(__file__).resolve().parent / 'md' / 'p1_pane_loop_survives_exception_probe.md'

# ORCHESTRATOR


def run_probe_workflow():
    sys.exit(strand_workflow(globals(), __file__, _STRAND_NAMES, _REPORT_PATH, _TITLE))


if __name__ == '__main__':
    run_probe_workflow()
