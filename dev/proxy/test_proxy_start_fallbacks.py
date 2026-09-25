# INFRASTRUCTURE
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dev.proxy.proxy_start_sandbox import make_case_dir, run_variant
from dev.refactoring.strand_runner import strand_workflow

REPORT_PATH = Path(__file__).resolve().parent / 'md' / 'test_proxy_start_fallbacks.md'
LOG_PREFIX = 'claude_proxy_start:'
VALID_CONFIG = '{"main": "opus-cfg"}'


# ORCHESTRATOR
def fallback_workflow_case(spec: dict, variants: list) -> dict:
    case_dir = make_case_dir()
    project = case_dir / 'proj'
    project.mkdir()
    try:
        return {v: run_variant(v, spec, case_dir, project) for v in variants}
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)


# FUNCTIONS
def launcher_lines(result: dict) -> list:
    return [l for l in result['stderr'].splitlines() if l.startswith(LOG_PREFIX)]


def injected_model(result: dict) -> bool:
    return 'ARG: --model' in result['claude']


def case_jq_missing():
    new = fallback_workflow_case({'config': VALID_CONFIG, 'jq': False}, ['new'])['new']
    assert new['returncode'] == 0 and new['claude'], new
    assert len(launcher_lines(new)) == 1 and 'jq not found' in launcher_lines(new)[0], new['stderr']
    assert not injected_model(new)


def case_config_unreadable():
    new = fallback_workflow_case({'config': VALID_CONFIG, 'config_unreadable': True}, ['new'])['new']
    assert new['returncode'] == 0 and new['claude'], new
    assert len(launcher_lines(new)) == 1 and 'unreadable' in launcher_lines(new)[0], new['stderr']
    assert not injected_model(new)


def case_config_malformed():
    new = fallback_workflow_case({'config': '{not json'}, ['new'])['new']
    assert new['returncode'] == 0 and new['claude'], new
    assert len(launcher_lines(new)) == 1 and 'not valid JSON' in launcher_lines(new)[0], new['stderr']
    assert not injected_model(new)


def case_config_absent_is_silent():
    new = fallback_workflow_case({}, ['new'])['new']
    assert launcher_lines(new) == [], new['stderr']
    assert new['claude'] and not injected_model(new)


def case_config_empty_main_is_silent():
    new = fallback_workflow_case({'config': '{"main": ""}'}, ['new'])['new']
    assert launcher_lines(new) == [], new['stderr']
    assert new['claude'] and not injected_model(new)


def case_config_valid_is_silent_and_injects():
    new = fallback_workflow_case({'config': VALID_CONFIG}, ['new'])['new']
    assert launcher_lines(new) == [], new['stderr']
    assert 'ARG: opus-cfg' in new['claude']


def case_mitmdump_start_failure_aborts():
    results = fallback_workflow_case({'mitm_exit': '1'}, ['old', 'new'])
    old, new = results['old'], results['new']
    assert old['claude'] and old['returncode'] == 0, 'base ref no longer launches claude after a failed proxy start'
    assert new['returncode'] == 1, new['returncode']
    assert new['claude'] == '', 'claude must not start after a failed proxy start'
    assert len(launcher_lines(new)) == 1 and 'mitmdump failed to start' in launcher_lines(new)[0], new['stderr']
    leftovers = [k for k in new['tree'] if k.startswith('.proxy_addon_live_') or k.startswith('.proxy_live_') or k.startswith('.proxy_session_')]
    assert leftovers == [], leftovers
    assert new['tmp_marker_left'] is False


def collect_strands():
    return [n for n in list(globals()) if n.startswith('case_')]


if __name__ == '__main__':
    sys.exit(strand_workflow(globals(), __file__, collect_strands(), REPORT_PATH, 'test_proxy_start_fallbacks'))
