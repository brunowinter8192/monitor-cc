# INFRASTRUCTURE
import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_MUTATIONS = ('os.environ[', 'os.environ.setdefault', 'os.environ.update', 'putenv', 'sys.path.insert', 'sys.path.append', 'sys.modules', 'reload(', 'chdir', 'monkeypatch', 'patch(', 'patch.object', 'patch.dict', 'load_root', 'setenv', 'environ.pop')
PROJECT_PACKAGES = ('src', 'dev')


# FUNCTIONS

def check_imports(tree) -> list:
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level > 0:
            found.append(('L8-relative-import', node.lineno, ast.unparse(node)))
        elif isinstance(node, ast.Import) and any(a.name == 'src' or a.name.startswith('src.') for a in node.names):
            found.append(('L8-import-src-module', node.lineno, ast.unparse(node)))
    return found


def check_bare_src_imports(tree, path: Path) -> list:
    found = []
    top_names = src_top_level_names() - {'src'}
    for node in ast.walk(tree):
        module = node.module if isinstance(node, ast.ImportFrom) and node.level == 0 else None
        if isinstance(node, ast.Import):
            module = node.names[0].name
        if module and module.split('.')[0] in top_names and not is_local_sibling(module.split('.')[0], path):
            found.append(('L8-bare-src-import', node.lineno, ast.unparse(node)))
    return found


def src_top_level_names() -> set:
    return {p.stem for p in (PROJECT_ROOT / 'src').iterdir() if (p.suffix == '.py' or p.is_dir()) and p.stem != '__pycache__'}


def is_local_sibling(name: str, path: Path) -> bool:
    return (path.parent / f'{name}.py').exists() or (path.parent / name).is_dir()


def check_local_imports(tree, path: Path) -> list:
    found = []
    mutates = mutates_at_runtime(tree)
    has_path = has_path_evidence(tree)
    guarded = import_error_guarded(tree)
    for func in ast.walk(tree):
        if isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found += local_import_findings(func, mutates, has_path, guarded)
    return found


def mutates_at_runtime(tree) -> bool:
    for func in ast.walk(tree):
        if isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for stmt in ast.walk(func):
                if any(k in statement_head(stmt) for k in RUNTIME_MUTATIONS):
                    return True
    return False


def statement_head(stmt) -> str:
    if isinstance(stmt, (ast.With, ast.AsyncWith)):
        return ' '.join(ast.unparse(item.context_expr) for item in stmt.items)
    if isinstance(stmt, (ast.Assign, ast.Expr, ast.AugAssign)):
        return ast.unparse(stmt)
    return ''


def has_path_evidence(tree) -> bool:
    for node in tree.body:
        if 'sys.path' in ast.unparse(node) and mentions_repo_root(node):
            return True
        if isinstance(node, (ast.Import, ast.ImportFrom)) and imported_module(node).split('.')[0] in PROJECT_PACKAGES:
            return True
    return False


def mentions_repo_root(node) -> bool:
    text = ast.unparse(node)
    return any(key in text for key in ('parents[', '.parent.parent', 'ROOT', 'WORKTREE', "'..'", 'MONITOR_CC_ROOT'))


def imported_module(node) -> str:
    return (node.module or '') if isinstance(node, ast.ImportFrom) else node.names[0].name


def import_error_guarded(tree) -> set:
    guarded = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try) and any(catches_import_error(h) for h in node.handlers):
            for stmt in node.body:
                guarded.update(id(n) for n in ast.walk(stmt))
    return guarded


def catches_import_error(handler) -> bool:
    return isinstance(handler.type, ast.Name) and handler.type.id in ('ImportError', 'ModuleNotFoundError')


def local_import_findings(func, mutates: bool, has_path: bool, guarded: set) -> list:
    found = []
    for node in ast.walk(func):
        if isinstance(node, (ast.Import, ast.ImportFrom)) and not local_import_allowed(node, mutates, has_path, guarded):
            found.append(('L8-local-import', node.lineno, ast.unparse(node)))
    return found


def local_import_allowed(node, mutates: bool, has_path: bool, guarded: set) -> bool:
    module = imported_module(node)
    head = module.split('.')[0]
    if id(node) in guarded or project_module_missing(module):
        return True
    if head in sys.stdlib_module_names:
        return False
    return mutates or (head in PROJECT_PACKAGES and not has_path)


def project_module_missing(module: str) -> bool:
    parts = module.split('.')
    target = PROJECT_ROOT.joinpath(*parts)
    return parts[0] in PROJECT_PACKAGES and not target.with_suffix('.py').exists() and not target.is_dir()
