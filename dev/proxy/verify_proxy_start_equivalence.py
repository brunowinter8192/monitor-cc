# INFRASTRUCTURE
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dev.proxy.proxy_start_sandbox import diff_report, drop_launcher_log_lines, make_case_dir, run_variant
from dev.refactoring.strand_runner import strand_workflow

REPORT_PATH = Path(__file__).resolve().parent / 'md' / 'verify_proxy_start_equivalence.md'
CASES = {
    'default_no_args': {},
    'explicit_model_and_project': {'args': ['--project', '{project}', '--model', 'explicit-x', 'extra']},
    'config_main_injected': {'args': ['--project', '{project}', '-p', 'hi'], 'config': '{"main": "opus-cfg"}'},
    'config_explicit_wins': {'args': ['--model', 'cli', '--project', '{project}'], 'config': '{"main": "opus-cfg"}'},
    'config_malformed': {'config': '{not json'},
    'config_empty_main': {'config': '{"main": ""}'},
    'config_absent': {},
    'port_busy': {'busy': '8080 8081'},
    'first_run_ca': {'ca': False},
    'marker_live_fresh': {'marker': 'live', 'tmp_marker': True},
    'marker_dead': {'marker': 'dead', 'tmp_marker': True},
    'janitor_fixture': {'janitor': True},
}


# ORCHESTRATOR

def equivalence_workflow_case(name: str) -> None:
    case_dir = make_case_dir()
    project = case_dir / 'proj'
    project.mkdir()
    spec = resolve_spec(CASES[name], project)
    try:
        old = run_variant('old', spec, case_dir, project)
        new = run_variant('new', spec, case_dir, project)
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)
    assert_equal(name, old, drop_launcher_log_lines(new))


# FUNCTIONS

def resolve_spec(spec: dict, project: Path) -> dict:
    resolved = dict(spec)
    if 'args' in resolved:
        resolved['args'] = [a.replace('{project}', str(project)) for a in resolved['args']]
    else:
        resolved['args'] = []
    return resolved


def assert_equal(name: str, old: dict, new: dict) -> None:
    if old != new:
        raise AssertionError(f'{name}: old and new differ\n{diff_report(old, new)}')
    assert old['claude'], f'{name}: claude stub never ran, vacuous comparison'


def make_strand(name: str):
    return lambda: equivalence_workflow_case(name)


def register_case_strands(namespace: dict) -> list:
    for name in CASES:
        namespace[f'case_{name}'] = make_strand(name)
    return [f'case_{n}' for n in CASES]


if __name__ == '__main__':
    sys.exit(strand_workflow(globals(), __file__, register_case_strands(globals()), REPORT_PATH, 'verify_proxy_start_equivalence'))
