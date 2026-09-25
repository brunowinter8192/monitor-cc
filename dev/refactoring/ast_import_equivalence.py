# INFRASTRUCTURE
import ast
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


# ORCHESTRATOR

def ast_import_equivalence_workflow() -> None:
    base_ref = compute_base_ref()
    changed = _list_changed(base_ref)
    mismatches = _find_mismatches(base_ref, changed)
    _report(changed, mismatches)


# FUNCTIONS

def compute_base_ref():
    return sys.argv[1]


def _list_changed(base_ref: str) -> list:
    out = subprocess.run(['git', 'diff', base_ref, '--name-only', '--', 'src'], capture_output=True, text=True, cwd=str(_ROOT), check=True).stdout
    return [line for line in out.splitlines() if line.endswith('.py') and (_ROOT / line).exists()]


def _find_mismatches(base_ref: str, changed: list) -> list:
    return [path for path in changed if not _equivalent(base_ref, path)]


def _equivalent(base_ref: str, path: str) -> bool:
    old = subprocess.run(['git', 'show', f'{base_ref}:{path}'], capture_output=True, text=True, cwd=str(_ROOT)).stdout
    new = (_ROOT / path).read_text()
    package = _package_of(path)
    return _normalized(old, package) == _normalized(new, package)


def _package_of(path: str) -> list:
    return list(Path(path).with_suffix('').parts[:-1])


def _normalized(source: str, package: list) -> str:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level:
            base = package[:len(package) - (node.level - 1)]
            node.module = '.'.join(base + ([node.module] if node.module else []))
            node.level = 0
    return ast.dump(tree)


def _report(changed: list, mismatches: list) -> None:
    print(f'files_compared={len(changed)} mismatches={len(mismatches)}')
    for path in mismatches:
        print(f'MISMATCH {path}')


if __name__ == '__main__':
    ast_import_equivalence_workflow()
