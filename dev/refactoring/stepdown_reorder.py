# INFRASTRUCTURE
import ast
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_FUNCTIONS_MARKER = '# FUNCTIONS'
_ORCHESTRATOR_MARKER = '# ORCHESTRATOR'
_SKIP_FILES = ('src/proxy/addon_dual_log.py', 'src/menubar/model_controller.py', 'src/panes/log_janitor.py')

# ORCHESTRATOR

def stepdown_workflow() -> None:
    write = '--write' in sys.argv
    files = _list_files()
    results = [_reorder_file(path, write) for path in files]
    _print_summary(files, results)

# FUNCTIONS

def _list_files() -> list:
    paths = [p for p in sorted((_ROOT / 'src').rglob('*.py')) if 'logs' not in p.parts]
    paths += [_ROOT / 'workflow.py', _ROOT / 'setup_py2app.py']
    return [p for p in paths if str(p.relative_to(_ROOT)) not in _SKIP_FILES]

def _reorder_file(path: Path, write: bool) -> str:
    source = path.read_text()
    lines = source.split('\n')
    marker = _find_marker(lines, _FUNCTIONS_MARKER)
    if marker is None:
        return 'nomarker'
    tree = ast.parse(source)
    region = [n for n in tree.body if _start(n) > marker]
    verdict = _region_verdict(region)
    if verdict != 'ok':
        return verdict
    if not _has_back_reference(region):
        return 'unchanged'
    ordered = _stepdown_order(tree, region, lines)
    if [n for n in ordered] == region:
        return 'unchanged'
    if write:
        path.write_text(_render(lines, marker, region, ordered))
    return 'reordered'

def _find_marker(lines: list, marker: str):
    for index, line in enumerate(lines):
        if line.strip() == marker:
            return index
    return None

def _start(node) -> int:
    decorators = getattr(node, 'decorator_list', [])
    return min([node.lineno] + [d.lineno for d in decorators]) - 1

def _region_verdict(region: list) -> str:
    defs = (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)
    kinds = [isinstance(n, defs) for n in region]
    if not any(kinds):
        return 'nodefs'
    last_def = max(i for i, k in enumerate(kinds) if k)
    if not all(kinds[:last_def + 1]):
        return 'interleaved'
    return 'ok'

def _has_back_reference(region: list) -> bool:
    funcs = {n.name: n for n in region if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for node in funcs.values():
        for ref in ast.walk(node):
            if isinstance(ref, ast.Name) and isinstance(ref.ctx, ast.Load) and ref.id in funcs and ref.id != node.name:
                if funcs[ref.id].lineno < node.lineno:
                    return True
    return False

def _stepdown_order(tree, region: list, lines: list) -> list:
    defs = [n for n in region if isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef))]
    trailing = [n for n in region if n not in defs]
    classes = [n for n in defs if isinstance(n, ast.ClassDef)]
    funcs = {n.name: n for n in defs if not isinstance(n, ast.ClassDef)}
    roots = _roots(tree, funcs, lines)
    order = []
    seen = set()
    for name in roots:
        _visit(name, funcs, seen, order)
    for name in _unreferenced(funcs):
        _visit(name, funcs, seen, order)
    for name in funcs:
        _visit(name, funcs, seen, order)
    return classes + order + trailing

def _unreferenced(funcs: dict) -> list:
    referenced = set()
    for node in funcs.values():
        referenced.update(n for n in _callees_in_order([node], funcs) if n != node.name)
    return [name for name in funcs if name not in referenced]

def _roots(tree, funcs: dict, lines: list) -> list:
    orchestrators = _orchestrator_nodes(tree, lines)
    if orchestrators:
        return _callees_in_order(orchestrators, funcs)
    referenced = set()
    for node in funcs.values():
        referenced.update(n for n in _callees_in_order([node], funcs) if n != node.name)
    return [name for name in funcs if name not in referenced]

def _orchestrator_nodes(tree, lines: list) -> list:
    marker = _find_marker(lines, _ORCHESTRATOR_MARKER)
    functions = _find_marker(lines, _FUNCTIONS_MARKER)
    if marker is None:
        return []
    return [n for n in tree.body if isinstance(n, ast.FunctionDef) and marker < _start(n) < functions]

def _callees_in_order(nodes: list, funcs: dict) -> list:
    found = []
    for node in nodes:
        names = sorted((n for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id in funcs),
                       key=lambda n: (n.lineno, n.col_offset))
        for n in names:
            if n.id not in found:
                found.append(n.id)
    return found

def _visit(name: str, funcs: dict, seen: set, order: list) -> None:
    if name in seen:
        return
    seen.add(name)
    order.append(funcs[name])
    for callee in _callees_in_order([funcs[name]], funcs):
        _visit(callee, funcs, seen, order)

def _render(lines: list, marker: int, region: list, ordered: list) -> str:
    first = _start(region[0])
    gap = _gap_size(lines, region)
    head = lines[:first]
    texts = [_node_text(lines, n) for n in ordered]
    separator = [''] * gap
    body = []
    for text in texts:
        if body:
            body.extend(separator)
        body.extend(text)
    return '\n'.join(head + body) + '\n'

def _gap_size(lines: list, region: list) -> int:
    if len(region) < 2:
        return 1
    return max(1, _start(region[1]) - region[0].end_lineno)

def _node_text(lines: list, node) -> list:
    return lines[_start(node):node.end_lineno]

def _print_summary(files: list, results: list) -> None:
    counts = {}
    for status in results:
        counts[status] = counts.get(status, 0) + 1
    print(counts)
    for path, status in zip(files, results):
        if status in ('interleaved',):
            print(f'SKIP {status} {path.relative_to(_ROOT)}')

if __name__ == '__main__':
    stepdown_workflow()
