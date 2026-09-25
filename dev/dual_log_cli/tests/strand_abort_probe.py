# INFRASTRUCTURE
import ast
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_INJECTED = "strand_injected_failure"
_INJECTION = (
    f"def {_INJECTED}():\n"
    "    print('  PASS  injected-before')\n"
    "    assert False, 'injected failure'\n"
    "    print('  PASS  injected-after')\n\n\n"
)
_GUARD = "if __name__ == "
_STRAND_LIST_HEAD = "_STRANDS = [\n"


# ORCHESTRATOR

def strand_abort_probe_workflow() -> int:
    targets = compute_targets()
    verdicts = compute_verdicts(targets)
    return report_verdicts(verdicts)


# FUNCTIONS

def compute_targets():
    return parse_targets(sys.argv[1:])


def parse_targets(argv: list) -> list:
    if not argv:
        raise SystemExit('usage: strand_abort_probe.py <path relative to dev/> [...]')
    return [_ROOT / 'dev' / rel for rel in argv]


def compute_verdicts(targets):
    return [probe_target(target) for target in targets]


def probe_target(target: Path) -> dict:
    strands = read_strands(target)
    mutant = target.with_name('__mut_' + target.name)
    mutant.write_text(build_mutant_text(target.read_text()), encoding='utf-8')
    try:
        proc = subprocess.run([sys.executable, str(mutant)], capture_output=True, text=True, cwd=str(_ROOT), timeout=600)
    finally:
        mutant.unlink()
    return {'target': target, 'strands': strands, 'proc': proc}


def read_strands(target: Path) -> list:
    for node in ast.parse(target.read_text()).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', '') == '_STRANDS':
            return ast.literal_eval(node.value)
    raise SystemExit(f'{target}: no _STRANDS list')


def build_mutant_text(text: str) -> str:
    text = text.replace(_STRAND_LIST_HEAD, _STRAND_LIST_HEAD + f"    '{_INJECTED}',\n", 1)
    index = text.rindex(_GUARD)
    return text[:index] + _INJECTION + text[index:]


def report_verdicts(verdicts: list) -> int:
    failed = 0
    for verdict in verdicts:
        problems = check_verdict(verdict)
        print(('OK   ' if not problems else 'FAIL ') + str(verdict['target'].relative_to(_ROOT / 'dev')) + ''.join(f' | {p}' for p in problems))
        failed += bool(problems)
    return 1 if failed else 0


def check_verdict(verdict: dict) -> list:
    out = verdict['proc'].stdout
    strands = verdict['strands']
    problems = []
    if verdict['proc'].returncode != 1:
        problems.append(f"exit code {verdict['proc'].returncode}, want 1")
    if f'ABORT {_INJECTED}' not in out:
        problems.append('injected strand not reported as aborted')
    if 'injected-after' in out:
        problems.append('strand continued after its first failing assertion')
    missing = [s for s in strands if f'PASS  {s}' not in out]
    if missing:
        problems.append(f'siblings not finished: {missing}')
    if f'{len(strands)}/{len(strands) + 1} strands passed' not in out:
        problems.append('summary line wrong')
    return problems


if __name__ == '__main__':
    sys.exit(strand_abort_probe_workflow())
