# INFRASTRUCTURE
import ast
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

# ORCHESTRATOR

def ast_reorder_equivalence_workflow() -> None:
    base_ref = sys.argv[1]
    changed = _list_changed(base_ref)
    mismatches = [path for path in changed if not _same_nodes(base_ref, path)]
    _report(changed, mismatches)

# FUNCTIONS

def _list_changed(base_ref: str) -> list:
    out = subprocess.run(['git', 'diff', base_ref, '--name-only', '--', 'src', 'workflow.py', 'setup_py2app.py'],
                         capture_output=True, text=True, cwd=str(_ROOT), check=True).stdout
    return [line for line in out.splitlines() if line.endswith('.py') and (_ROOT / line).exists()]

def _same_nodes(base_ref: str, path: str) -> bool:
    old = subprocess.run(['git', 'show', f'{base_ref}:{path}'], capture_output=True, text=True, cwd=str(_ROOT)).stdout
    new = (_ROOT / path).read_text()
    return _sorted_dumps(old) == _sorted_dumps(new)

def _sorted_dumps(source: str) -> list:
    return sorted(ast.dump(node) for node in ast.parse(source).body)

def _report(changed: list, mismatches: list) -> None:
    print(f'files_compared={len(changed)} mismatches={len(mismatches)}')
    for path in mismatches:
        print(f'MISMATCH {path}')

if __name__ == '__main__':
    ast_reorder_equivalence_workflow()
