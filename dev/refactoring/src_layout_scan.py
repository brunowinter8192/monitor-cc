# INFRASTRUCTURE
import ast
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_MARKERS = ('# INFRASTRUCTURE', '# ORCHESTRATOR', '# FUNCTIONS')
_EMOJI_RE = re.compile('[\U0001F300-\U0001FAFF☀-➿]')
_ENTRY_STATEMENTS = {
    'src/proxy_addon.py': 'mitmproxy shim: bootstrap call and addon re-export at module level',
    'src/proxy/addon.py': 'mitmproxy reads the module-level addons list; log filter registration',
    'src/menubar/menubar_main.py': 'py2app APP entry runs main() unconditionally at load',
    'src/menubar/paths.py': 'import-time creation of the application support directory',
    'src/gpu_pane/status.py': 'import-time logger configuration',
}
_FRAMEWORK_ORCHESTRATOR_FREE = ('src/proxy/addon.py', 'src/menubar/hotkey_controller.py')

# ORCHESTRATOR

def src_layout_scan_workflow() -> None:
    findings = _scan_all(_list_files())
    _print_findings(findings)
    sys.exit(1 if _hard_violations(findings) else 0)

# FUNCTIONS

def _list_files() -> list:
    paths = [p for p in sorted((_ROOT / 'src').rglob('*.py')) if 'logs' not in p.parts]
    return paths + [_ROOT / 'workflow.py', _ROOT / 'setup_py2app.py']

def _scan_all(files: list) -> dict:
    findings = {}
    for path in files:
        source = path.read_text()
        if not source.strip():
            continue
        rel = str(path.relative_to(_ROOT))
        for rule, detail in _scan_file(rel, source):
            findings.setdefault(rule, []).append(f'{rel}:{detail}')
    return findings

def _scan_file(rel: str, source: str) -> list:
    lines = source.split('\n')
    tree = ast.parse(source)
    positions = {line.strip(): index for index, line in enumerate(lines) if line.strip() in _MARKERS}
    found = []
    found += _comment_findings(lines)
    found += _docstring_findings(tree)
    found += _import_findings(tree)
    found += _marker_findings(rel, tree, lines, positions)
    found += _orchestrator_findings(rel, tree, lines, positions)
    found += _statement_findings(rel, tree, positions)
    found += _emoji_findings(lines)
    return found

def _comment_findings(lines: list) -> list:
    return [('comment', str(i + 1)) for i, line in enumerate(lines)
            if line.strip().startswith('#') and line.strip() not in _MARKERS]

def _docstring_findings(tree) -> list:
    nodes = [tree] + [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef))]
    return [('docstring', str(getattr(n, 'lineno', 0))) for n in nodes if ast.get_docstring(n)]

def _import_findings(tree) -> list:
    return [('relative_import', str(n.lineno)) for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level]

def _marker_findings(rel: str, tree, lines: list, positions: dict) -> list:
    if not positions:
        return [] if not tree.body else [('no_marker', '1')]
    order = [m for m in _MARKERS if m in positions]
    found = []
    if sorted(positions, key=positions.get) != order:
        found.append(('section_order', '1'))
    first = min(positions.values())
    found += [('code_before_marker', str(n.lineno)) for n in tree.body if n.lineno - 1 < first]
    found += _misplaced_findings(tree, positions) if rel not in _ENTRY_STATEMENTS else []
    return found

def _misplaced_findings(tree, positions: dict) -> list:
    cut = min([v for k, v in positions.items() if k != '# INFRASTRUCTURE'] or [10 ** 9])
    found = []
    for n in tree.body:
        if isinstance(n, (ast.Assign, ast.AnnAssign)) and n.lineno - 1 > cut and not _is_main_guard_tail(n, tree):
            found.append(('assignment_after_infrastructure', str(n.lineno)))
        if isinstance(n, (ast.Import, ast.ImportFrom)) and n.lineno - 1 > cut:
            found.append(('import_after_infrastructure', str(n.lineno)))
        if isinstance(n, ast.FunctionDef) and n.lineno - 1 < cut:
            found.append(('function_in_infrastructure', str(n.lineno)))
    return found

def _is_main_guard_tail(node, tree) -> bool:
    return node is tree.body[-1] and isinstance(node, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id == 'addons' for t in node.targets)

def _orchestrator_findings(rel: str, tree, lines: list, positions: dict) -> list:
    if '# ORCHESTRATOR' not in positions:
        return []
    start = positions['# ORCHESTRATOR']
    end = positions.get('# FUNCTIONS', 10 ** 9)
    inside = [n for n in tree.body if start < n.lineno - 1 < end]
    functions = [n for n in inside if isinstance(n, ast.FunctionDef)]
    if len(inside) != 1 or not functions:
        return [('orchestrator_shape', str([type(n).__name__ for n in inside]))]
    return [('orchestrator_logic', f'{functions[0].name}:{functions[0].lineno}')
            for _ in [0] if not all(_allowed_statement(s) for s in functions[0].body)]

def _simple(expr) -> bool:
    if isinstance(expr, (ast.Name, ast.Constant, ast.Attribute)):
        return True
    if isinstance(expr, (ast.Tuple, ast.List)):
        return all(_simple(x) for x in expr.elts)
    if isinstance(expr, ast.Dict):
        return all(k is None or _simple(k) for k in expr.keys) and all(_simple(v) for v in expr.values)
    if isinstance(expr, ast.Call):
        return _simple(expr.func) and all(_simple(a) for a in expr.args) and all(_simple(k.value) for k in expr.keywords)
    return isinstance(expr, ast.Starred) and _simple(expr.value)

def _condition(expr) -> bool:
    if isinstance(expr, ast.BoolOp):
        return all(_condition(v) for v in expr.values)
    if isinstance(expr, ast.UnaryOp) and isinstance(expr.op, ast.Not):
        return _condition(expr.operand)
    if isinstance(expr, ast.Compare):
        return _simple(expr.left) and all(_simple(c) for c in expr.comparators)
    return _simple(expr)

def _allowed_statement(stmt) -> bool:
    if isinstance(stmt, ast.Assign):
        return _simple(stmt.value)
    if isinstance(stmt, ast.AnnAssign):
        return stmt.value is None or _simple(stmt.value)
    if isinstance(stmt, (ast.Expr, ast.Return)):
        return stmt.value is None or _simple(stmt.value)
    if isinstance(stmt, ast.If):
        return _condition(stmt.test) and all(_allowed_statement(s) for s in stmt.body + stmt.orelse)
    return isinstance(stmt, (ast.Pass, ast.Import, ast.ImportFrom))

def _statement_findings(rel: str, tree, positions: dict) -> list:
    if rel in _ENTRY_STATEMENTS:
        return []
    found = []
    for n in tree.body:
        if isinstance(n, ast.If) and '__main__' in ast.unparse(n.test):
            continue
        if isinstance(n, (ast.Expr, ast.If, ast.For, ast.While, ast.Try, ast.With)) and not _is_path_bootstrap(n):
            found.append(('toplevel_statement', str(n.lineno)))
    return found

def _is_path_bootstrap(node) -> bool:
    return isinstance(node, ast.Expr) and 'sys.path.insert' in ast.unparse(node)

def _emoji_findings(lines: list) -> list:
    return [('emoji', str(i + 1)) for i, line in enumerate(lines) if _EMOJI_RE.search(line)]

def _hard_violations(findings: dict) -> list:
    return [k for k in findings if k not in ('emoji',)]

def _print_findings(findings: dict) -> None:
    for rule in sorted(findings):
        print(f'{rule}: {len(findings[rule])}')
        for item in findings[rule][:40]:
            print(f'  {item}')
    if not findings:
        print('no findings')

if __name__ == '__main__':
    src_layout_scan_workflow()
