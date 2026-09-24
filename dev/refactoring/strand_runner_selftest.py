# INFRASTRUCTURE
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dev.refactoring.strand_runner import STRAND_FLAG, launch_strand, run_strands_parallel

_FAKE_SCRIPT = '''
import sys, time
sys.path.insert(0, {root!r})
from dev.refactoring.strand_runner import check, strand_workflow

def strand_ok():
    check("first ok", True)
    time.sleep(1.0)
    check("second ok", True)

def strand_slow_ok():
    time.sleep(1.0)
    check("slow ok", True)

def strand_fail():
    check("before failure", True)
    check("the failing check", False)
    check("after failure must never run", True)

def strand_raises():
    raise RuntimeError("boom")

if __name__ == "__main__":
    sys.exit(strand_workflow(globals(), __file__, {names!r}, report_path={report!r}, title="fake"))
'''

# ORCHESTRATOR


def selftest_workflow() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        passing = write_fake_script(tmp_path, 'pass_case.py', ['strand_ok', 'strand_slow_ok'])
        failing = write_fake_script(tmp_path, 'fail_case.py', ['strand_ok', 'strand_fail', 'strand_raises', 'strand_slow_ok'])
        verify_parallel_and_pass(passing, tmp_path)
        verify_fail_fast_and_siblings_finish(failing, tmp_path)
        verify_single_strand_entry(failing)
    print('[strand_runner_selftest] all checks passed')


# FUNCTIONS


def write_fake_script(tmp_path: Path, filename: str, names: list) -> Path:
    path = tmp_path / filename
    report = str(tmp_path / (filename + '.md'))
    path.write_text(_FAKE_SCRIPT.format(root=str(REPO_ROOT), names=names, report=report), encoding='utf-8')
    return path


def verify_parallel_and_pass(script: Path, tmp_path: Path) -> None:
    started = time.monotonic()
    proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    elapsed = time.monotonic() - started
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert 'PASS  strand_ok' in proc.stdout and 'PASS  strand_slow_ok' in proc.stdout, proc.stdout
    assert '2/2 strands passed' in proc.stdout, proc.stdout
    assert elapsed < 1.9, f'two 1s strands took {elapsed:.2f}s, not parallel'
    report = (tmp_path / 'pass_case.py.md').read_text(encoding='utf-8')
    assert '2/2 strands passed' in report and 'PASS  first ok' in report, report


def verify_fail_fast_and_siblings_finish(script: Path, tmp_path: Path) -> None:
    proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert proc.returncode == 1, proc.returncode
    assert 'ABORT strand_fail' in proc.stdout and 'ABORT strand_raises' in proc.stdout, proc.stdout
    assert 'aborted strands: strand_fail, strand_raises' in proc.stdout, proc.stdout
    assert 'PASS  strand_ok' in proc.stdout and 'PASS  strand_slow_ok' in proc.stdout, proc.stdout
    assert 'after failure must never run' not in proc.stdout, proc.stdout
    assert 'RuntimeError: boom' in proc.stdout, proc.stdout
    report = (tmp_path / 'fail_case.py.md').read_text(encoding='utf-8')
    assert '## ABORT strand_fail' in report and '## PASS strand_slow_ok' in report, report
    assert '2/4 strands passed' in report, report


def verify_single_strand_entry(script: Path) -> None:
    result = launch_strand(str(script), 'strand_fail')
    assert result['returncode'] == 1 and 'FAIL  the failing check' in result['stdout'], result
    results = run_strands_parallel(str(script), ['strand_ok'])
    assert results[0]['returncode'] == 0, results
    assert STRAND_FLAG == '--strand'


if __name__ == '__main__':
    selftest_workflow()
