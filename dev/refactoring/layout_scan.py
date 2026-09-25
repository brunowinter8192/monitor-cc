# INFRASTRUCTURE
import ast
import io
import sys
import tokenize
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dev.refactoring.layout_scan_imports import check_bare_src_imports, check_imports, check_local_imports

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOT = PROJECT_ROOT / 'dev'
REPORT_DIR = Path(__file__).resolve().parent / 'md'
SECTIONS = ('INFRASTRUCTURE', 'ORCHESTRATOR', 'FUNCTIONS')
STRAND_ENTRY = 'strand_workflow'
ALLOWED_INFRA_STATEMENTS = (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign, ast.Expr)
HARD_EXPR = (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp, ast.Lambda)
SOFT_EXPR = (ast.BinOp, ast.BoolOp, ast.IfExp, ast.Compare, ast.UnaryOp, ast.Subscript, ast.JoinedStr)
HARD_STMT = (ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith, ast.FunctionDef, ast.ClassDef, ast.AugAssign, ast.Delete, ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.Raise, ast.Assert)


# ORCHESTRATOR

def scan_workflow() -> int:
    files = list_python_files(SCAN_ROOT)
    findings = collect_findings(files)
    report_path = write_report(REPORT_DIR, files, findings)
    print_summary(files, findings, report_path)
    return exit_code(findings)


# FUNCTIONS

def list_python_files(root: Path) -> list:
    return sorted(p for p in root.rglob('*.py') if '__pycache__' not in p.parts)


def collect_findings(files: list) -> list:
    findings = []
    for path in files:
        for rule, line, detail in analyze_file(path):
            findings.append((str(path.relative_to(PROJECT_ROOT)), rule, line, detail))
    return findings


def analyze_file(path: Path) -> list:
    source = path.read_text(encoding='utf-8')
    tree = ast.parse(source)
    if not tree.body:
        return []
    markers = find_markers(source)
    if not markers:
        return [('L1-no-marker', 1, 'module has code but no section marker')]
    spans = build_spans(markers, len(source.split('\n')))
    found = check_marker_order(markers)
    found += check_section_content(tree, spans)
    found += check_orchestrator(tree, spans)
    found += check_entry(tree, spans, path)
    found += check_stepdown(tree, spans)
    found += check_imports(tree)
    found += check_bare_src_imports(tree, path)
    found += check_local_imports(tree, path)
    return found


def find_markers(source: str) -> list:
    markers = []
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.COMMENT and tok.string.strip() in ('# ' + s for s in SECTIONS):
            markers.append((tok.string.strip()[2:], tok.start[0]))
    return markers


def build_spans(markers: list, total_lines: int) -> dict:
    spans = {}
    for index, (name, line) in enumerate(markers):
        end = markers[index + 1][1] - 1 if index + 1 < len(markers) else total_lines + 1
        spans[name] = (line, end)
    return spans


def check_marker_order(markers: list) -> list:
    names = [name for name, _ in markers]
    found = []
    if len(set(names)) != len(names):
        found.append(('L2-marker-duplicate', markers[0][1], ' '.join(names)))
    expected = [s for s in SECTIONS if s in names]
    if [n for n in names if n in expected] != expected and len(set(names)) == len(names):
        found.append(('L2-marker-order', markers[0][1], ' -> '.join(names)))
    return found


def check_section_content(tree, spans: dict) -> list:
    found = []
    for node in tree.body:
        if node_start(node) < min(s for s, _ in spans.values()):
            found.append(('L3-before-first-marker', node.lineno, type(node).__name__))
    for node in section_nodes(tree, spans, 'INFRASTRUCTURE'):
        if not isinstance(node, ALLOWED_INFRA_STATEMENTS) and not is_path_setup(node):
            found.append(('L3-infra-content', node.lineno, type(node).__name__))
    for node in section_nodes(tree, spans, 'FUNCTIONS'):
        if not isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            found.append(('L3-functions-content', node.lineno, type(node).__name__))
    return found


def node_start(node) -> int:
    decorators = getattr(node, 'decorator_list', [])
    return min([node.lineno] + [d.lineno for d in decorators])


def section_nodes(tree, spans: dict, name: str) -> list:
    return [n for n in tree.body if section_of(node_start(n), spans) == name and not is_main_guard(n)]


def section_of(line: int, spans: dict):
    for name, (start, end) in spans.items():
        if start <= line <= end:
            return name
    return None


def is_main_guard(node) -> bool:
    if not isinstance(node, ast.If):
        return False
    test = node.test
    return isinstance(test, ast.Compare) and isinstance(test.left, ast.Name) and test.left.id == '__name__'


def is_path_setup(node) -> bool:
    return isinstance(node, (ast.Expr, ast.If)) and 'sys.path' in ast.unparse(node)


def check_orchestrator(tree, spans: dict) -> list:
    nodes = section_nodes(tree, spans, 'ORCHESTRATOR')
    if 'ORCHESTRATOR' not in spans:
        return []
    functions = [n for n in nodes if isinstance(n, ast.FunctionDef)]
    found = []
    if len(nodes) != 1 or len(functions) != 1:
        found.append(('L4-orchestrator-not-one-function', spans['ORCHESTRATOR'][0], f'{len(nodes)} nodes, {len(functions)} functions'))
    for func in functions:
        found += orchestrator_logic(func.body)
    return found


def orchestrator_logic(body: list) -> list:
    found = []
    for stmt in body:
        if isinstance(stmt, HARD_STMT):
            found.append(('L5-orchestrator-logic', stmt.lineno, type(stmt).__name__))
        elif isinstance(stmt, ast.If):
            found += orchestrator_logic(stmt.body) + orchestrator_logic(stmt.orelse)
            found += expression_logic(stmt.test, allow_top_test=True)
        elif is_literal_assignment(stmt):
            found.append(('L5-orchestrator-literal', stmt.lineno, 'literal assignment belongs in INFRASTRUCTURE or a helper'))
        else:
            found += expression_logic(stmt, allow_top_test=False)
    return found


def expression_logic(node, allow_top_test: bool) -> list:
    found = []
    for sub in ast.walk(node):
        if allow_top_test and sub is node:
            continue
        if isinstance(sub, HARD_EXPR):
            found.append(('L5-orchestrator-logic', sub.lineno, type(sub).__name__))
        elif isinstance(sub, SOFT_EXPR) and not allow_top_test:
            found.append(('L5-orchestrator-logic', sub.lineno, type(sub).__name__))
    return found[:1]


def is_literal_assignment(stmt) -> bool:
    return isinstance(stmt, (ast.Assign, ast.AnnAssign)) and stmt.value is not None and is_literal(stmt.value, top=True)


def is_literal(node, top: bool) -> bool:
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return bool(node.elts) and all(is_literal(e, False) for e in node.elts)
    if isinstance(node, ast.Dict):
        return bool(node.keys) and all(k is not None and is_literal(k, False) for k in node.keys) and all(is_literal(v, False) for v in node.values)
    return False


def check_entry(tree, spans: dict, path: Path) -> list:
    found = []
    guard = guard_node(tree)
    if guard is not None:
        if len(guard.body) != 1 or guard.orelse:
            found.append(('L6-guard-not-single-call', guard.lineno, 'guard body is not one statement'))
        if not guard_is_strand(guard) and len(module_functions(tree)) >= 2 and 'ORCHESTRATOR' not in spans:
            found.append(('L6-script-without-orchestrator', guard.lineno, f'{len(module_functions(tree))} functions'))
    found += module_level_calls(tree, spans)
    return found


def guard_node(tree):
    guards = [n for n in tree.body if is_main_guard(n)]
    return guards[0] if guards else None


def guard_is_strand(guard) -> bool:
    return STRAND_ENTRY in ast.unparse(guard)


def module_functions(tree) -> list:
    return [n for n in tree.body if isinstance(n, ast.FunctionDef)]


def module_level_calls(tree, spans: dict) -> list:
    found = []
    for node in tree.body:
        if isinstance(node, ast.Expr) and not is_path_setup(node) and section_of(node_start(node), spans) != 'INFRASTRUCTURE':
            found.append(('L6-module-level-call', node.lineno, ast.unparse(node)[:60]))
    return found


def check_stepdown(tree, spans: dict) -> list:
    orchestrators = [n for n in section_nodes(tree, spans, 'ORCHESTRATOR') if isinstance(n, ast.FunctionDef)]
    if len(orchestrators) != 1:
        return []
    known = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    order = expected_order(orchestrators[0].name, known)
    actual = [n.name for n in known.values()]
    reachable_actual = [n for n in actual if n in order]
    found = []
    if reachable_actual != order:
        first = next(a for a, e in zip(reachable_actual, order) if a != e)
        found.append(('L7-stepdown-order', known[first].lineno, f'{first} out of call order'))
    return found


def expected_order(entry: str, known: dict) -> list:
    order = []
    visit(entry, known, order)
    return apply_eager_dependencies(order, known)


def visit(name: str, known: dict, order: list) -> None:
    if name in order:
        return
    order.append(name)
    for callee in ordered_callees(known[name], known):
        visit(callee, known, order)


def ordered_callees(func, known: dict) -> list:
    seen = []
    references = sorted((s for s in ast.walk(func) if isinstance(s, ast.Name) and isinstance(s.ctx, ast.Load) and s.id in known and s.id != func.name), key=lambda s: (s.lineno, s.col_offset))
    for ref in references:
        if ref.id not in seen:
            seen.append(ref.id)
    return seen


def apply_eager_dependencies(order: list, known: dict) -> list:
    placed = []
    for name in order:
        place_with_dependencies(name, order, known, placed, ())
    return placed


def place_with_dependencies(name: str, order: list, known: dict, placed: list, stack: tuple) -> None:
    if name in placed or name in stack:
        return
    for dep in sorted(eager_references(known[name], known), key=lambda d: order.index(d) if d in order else len(order)):
        place_with_dependencies(dep, order, known, placed, stack + (name,))
    placed.append(name)


def eager_references(node, known: dict) -> set:
    names = set()
    for expr in eager_expressions(node):
        for sub in ast.walk(expr):
            if isinstance(sub, ast.Name) and sub.id in known and sub.id != node.name:
                names.add(sub.id)
    return names


def eager_expressions(node) -> list:
    exprs = list(node.decorator_list)
    if isinstance(node, ast.ClassDef):
        exprs += node.bases + [k.value for k in node.keywords]
        for stmt in node.body:
            exprs += [stmt] if not isinstance(stmt, ast.FunctionDef) else signature_expressions(stmt)
        return exprs
    return exprs + signature_expressions(node, include_decorators=False)


def signature_expressions(func, include_decorators: bool = True) -> list:
    args = func.args
    exprs = list(func.decorator_list) if include_decorators else []
    exprs += args.defaults + [d for d in args.kw_defaults if d is not None]
    exprs += [a.annotation for a in args.args + args.kwonlyargs if a.annotation is not None]
    if func.returns is not None:
        exprs.append(func.returns)
    return exprs


def write_report(report_dir: Path, files: list, findings: list) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f'{Path(__file__).stem}_report.md'
    counts = rule_counts(findings)
    lines = ['# layout_scan report', '', f'files scanned: {len(files)}', f'files with violations: {len({f[0] for f in findings})}', f'violations: {len(findings)}', '']
    lines += [f'- {rule}: {count}' for rule, count in sorted(counts.items())]
    lines += ['', '## Findings', '']
    lines += [f'{f}:{line} {rule} {detail}' for f, rule, line, detail in findings]
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return path


def rule_counts(findings: list) -> dict:
    counts = {}
    for _, rule, _, _ in findings:
        counts[rule] = counts.get(rule, 0) + 1
    return counts


def print_summary(files: list, findings: list, report_path: Path) -> None:
    print(f'files scanned: {len(files)}')
    print(f'violations: {len(findings)} in {len({f[0] for f in findings})} files')
    for rule, count in sorted(rule_counts(findings).items()):
        print(f'  {rule}: {count}')
    print(f'report: {report_path}')


def exit_code(findings: list) -> int:
    return 0 if not findings else 1


if __name__ == '__main__':
    sys.exit(scan_workflow())
