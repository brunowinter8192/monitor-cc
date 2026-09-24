# INFRASTRUCTURE
import importlib
import json
from pathlib import Path
from unittest.mock import patch

_REAL_SHAPED_FULL = [
    'iterative-dev:iterative-dev-doccheck', 'iterative-dev:iterative-dev-duallog', 'iterative-dev:iterative-dev-refactor',
    'websearch:websearch-capture-and-index', 'websearch:websearch-pdf', 'websearch:websearch-web-research',
    'gh-cli:gh-cli-search', 'reddit-cli:reddit-cli-search',
]

# FUNCTIONS

def _imp(name: str):
    return importlib.import_module(f'src.menubar.{name}')

def _write(path: Path, text: str = '') -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')

def _skill_md(path: Path, name=None) -> None:
    name_line = f'name: {name}\n' if name is not None else ''
    _write(path, '---\n' + name_line + 'description: \n---\n\n# body\n')

def _make_plugin(base: Path, key_dir: str, manifest: dict, skill_dirs: dict) -> Path:
    install = base / 'plugins' / 'cache' / key_dir
    _write(install / '.claude-plugin' / 'plugin.json', json.dumps(manifest))
    for rel, fm_name in skill_dirs.items():
        _skill_md(install / rel / 'SKILL.md', fm_name)
    return install

def _make_claude_dir(root: Path) -> Path:
    claude = root / 'dotclaude'
    idev = _make_plugin(claude, 'idev', {'name': 'iterative-dev', 'skills': [
        './skills/iterative-dev-refactor/', './skills/iterative-dev-doccheck/', './skills/iterative-dev-duallog/']},
        {'skills/iterative-dev-refactor': 'iterative-dev-refactor',
         'skills/iterative-dev-doccheck': 'iterative-dev-doccheck',
         'skills/iterative-dev-duallog': 'iterative-dev-duallog'})
    web = _make_plugin(claude, 'web', {'name': 'websearch', 'skills': [
        './skills/websearch-web-research/', './skills/websearch-capture-and-index/', './skills/websearch-pdf/']},
        {'skills/websearch-web-research': 'websearch-web-research',
         'skills/websearch-capture-and-index': 'websearch-capture-and-index',
         'skills/websearch-pdf': 'websearch-pdf'})
    gh = _make_plugin(claude, 'gh', {'name': 'gh-cli', 'skills': ['./skills/gh-cli-search/']},
                      {'skills/gh-cli-search': 'gh-cli-search'})
    rd = _make_plugin(claude, 'rd', {'name': 'reddit-cli', 'skills': ['./skills/reddit-cli-search/']},
                      {'skills/reddit-cli-search': 'reddit-cli-search'})
    lsp = claude / 'plugins' / 'cache' / 'lsp'
    lsp.mkdir(parents=True)
    _write(claude / 'settings.json', json.dumps({'enabledPlugins': {
        'iterative-dev@m': True, 'websearch@m': True, 'gh-cli@m': True, 'reddit-cli@m': True,
        'pyright-lsp@m': True, 'off-plugin@m': False}}))
    entry = lambda p, scope='user': [{'scope': scope, 'installPath': str(p), 'version': '1'}]
    _write(claude / 'plugins' / 'installed_plugins.json', json.dumps({'version': 2, 'plugins': {
        'iterative-dev@m': entry(idev), 'websearch@m': entry(web), 'gh-cli@m': entry(gh),
        'reddit-cli@m': entry(rd), 'pyright-lsp@m': entry(lsp),
        'off-plugin@m': entry(idev)}}))
    (claude / 'skills' / 'synced').mkdir(parents=True)
    return claude

def _make_project(root: Path, name: str, skills: dict) -> str:
    project = root / name
    project.mkdir(parents=True)
    for dirname, fm_name in skills.items():
        _skill_md(project / '.claude' / 'skills' / dirname / 'SKILL.md', fm_name)
    return str(project)

class _Logs:
    def __init__(self, module):
        self.module = module
        self.lines = []

    def __enter__(self):
        self._p = patch.object(self.module, 'log_menubar', lambda c, m: self.lines.append((c, m)))
        self._p.start()
        return self.lines

    def __exit__(self, *a):
        self._p.stop()
