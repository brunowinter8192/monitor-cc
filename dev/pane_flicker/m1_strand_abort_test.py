# INFRASTRUCTURE
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import m1_frame_e2e_test as m1

_ABORT_DEADLINE_SECONDS = 2
_BAD_ROOT = Path('/nonexistent_root_for_m1_abort_test')


# ORCHESTRATOR

def abort_test_workflow() -> None:
    m1.DEADLINE_SECONDS = _ABORT_DEADLINE_SECONDS
    result = collect_result()
    verify_strand_recorded_as_aborted(result)
    verify_tmux_server_killed('flk_m1_tokens_new')
    verify_verdict_reports_abort(result)
    print('[m1_strand_abort_test] all checks passed')


# FUNCTIONS

def collect_result():
    with tempfile.TemporaryDirectory(prefix='flicker_m1_abort_') as tmp:
        result = m1.run_strand_guarded('tokens', 'new', _BAD_ROOT, Path(tmp))
    return result


def verify_strand_recorded_as_aborted(result: dict) -> None:
    assert list(result) == ['aborted'], result
    assert 'TimeoutError' in result['aborted'], result['aborted']


def verify_tmux_server_killed(sock: str) -> None:
    probe = m1.tmux(sock, 'list-sessions')
    assert probe.returncode != 0, 'tmux server of the aborted strand is still running'


def verify_verdict_reports_abort(aborted: dict) -> None:
    results = {(pane, tree): {'aborted': 'x'} for pane in m1.PANES for tree in m1.TREES}
    results[('tokens', 'new')] = aborted
    verdicts = m1.evaluate(results)
    assert len(verdicts) == len(m1.PANES), verdicts
    assert all(not ok for _, ok, _ in verdicts), verdicts


if __name__ == '__main__':
    abort_test_workflow()
