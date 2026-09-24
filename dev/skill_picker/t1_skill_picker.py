# INFRASTRUCTURE
import argparse
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from dev.session_launcher.space_lib import write_report
from dev.session_launcher.test_env import isolate_home

_REPORT_DIR = Path(__file__).resolve().parent / 'md'

# ORCHESTRATOR

def main() -> None:
    args = _parse_args()
    if args.case:
        _run_case_in_child(args.case)
        return
    names = sorted(_CASES)
    with ThreadPoolExecutor(max_workers=len(names)) as pool:
        results = list(pool.map(_spawn_case, names))
    text = _build_report(results)
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = _REPORT_DIR / f'{Path(__file__).stem}.md'
    path.write_text(text, encoding='utf-8')
    print(text)
    print(f'report: {path}')
    if any(not r['ok'] for r in results):
        sys.exit(1)

# FUNCTIONS

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument('--case')
    return p.parse_args()

def _spawn_case(name: str) -> dict:
    r = subprocess.run([sys.executable, '-m', 'dev.skill_picker.t1_skill_picker', '--case', name],
                       capture_output=True, text=True, cwd=str(_ROOT), timeout=120)
    lines = [l for l in r.stdout.splitlines() if l.startswith('{')]
    if r.returncode != 0 or not lines:
        return {'name': name, 'ok': False, 'detail': f'rc={r.returncode} stderr={r.stderr.strip()[-400:]}'}
    out = json.loads(lines[-1])
    out['name'] = name
    return out

def _run_case_in_child(name: str) -> None:
    try:
        isolate_home()
        detail = _CASES[name]()
        print(json.dumps({'ok': True, 'detail': detail}))
    except AssertionError as exc:
        print(json.dumps({'ok': False, 'detail': f'ASSERT {exc}'}))
    except Exception as exc:
        print(json.dumps({'ok': False, 'detail': f'ERROR {exc!r}'}))

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

_REAL_SHAPED_FULL = [
    'iterative-dev:iterative-dev-doccheck', 'iterative-dev:iterative-dev-duallog', 'iterative-dev:iterative-dev-refactor',
    'websearch:websearch-capture-and-index', 'websearch:websearch-pdf', 'websearch:websearch-web-research',
    'gh-cli:gh-cli-search', 'reddit-cli:reddit-cli-search',
]

def _case_discovery_plugins() -> str:
    sd = _imp('skill_discovery')
    root = Path(tempfile.mkdtemp(prefix='skillpicker_'))
    claude = _make_claude_dir(root)
    with _Logs(sd) as logs:
        skills = sd.discover_skills_workflow('', claude)
    full = sorted(s.full for s in skills)
    assert full == sorted(_REAL_SHAPED_FULL), f'full names {full}'
    assert all(s.source == 'plugin' for s in skills)
    assert not any('off-plugin' in s.full for s in skills), 'disabled plugin listed'
    assert logs == [('skill', 'FAILED plugin=pyright-lsp@m reason=manifest_missing')], f'logs {logs}'
    shutil.rmtree(root)
    return f'8 plugin skills, disabled plugin absent, pyright-like plugin without manifest logged: {logs[0][1]}'

def _case_discovery_tripwires() -> str:
    sd = _imp('skill_discovery')
    root = Path(tempfile.mkdtemp(prefix='skillpicker_'))
    claude = root / 'dotclaude'
    noarr = _make_plugin(claude, 'noarr', {'name': 'noarr'}, {})
    noname = _make_plugin(claude, 'noname', {'skills': ['./skills/x/']}, {'skills/x': 'x'})
    missing = _make_plugin(claude, 'miss', {'name': 'miss', 'skills': ['./skills/gone/', './skills/here/']},
                           {'skills/here': None})
    default_only = _make_plugin(claude, 'defonly', {'name': 'defonly'}, {'skills/hidden': 'hidden'})
    _write(claude / 'settings.json', json.dumps({'enabledPlugins': {
        'noarr@m': True, 'noname@m': True, 'miss@m': True, 'defonly@m': True, 'ghost@m': True}}))
    ent = lambda p: [{'scope': 'user', 'installPath': str(p)}]
    _write(claude / 'plugins' / 'installed_plugins.json', json.dumps({'plugins': {
        'noarr@m': ent(noarr), 'noname@m': ent(noname), 'miss@m': ent(missing), 'defonly@m': ent(default_only)}}))
    with _Logs(sd) as logs:
        skills = sd.discover_skills_workflow('', claude)
    assert [s.full for s in skills] == ['miss:here'], f'skills {[s.full for s in skills]}'
    msgs = sorted(m for _, m in logs)
    want = sorted([
        'FAILED plugin=defonly@m reason=no_skills_array',
        'FAILED plugin=ghost@m reason=not_installed',
        'FAILED plugin=miss@m reason=skill_file_missing entry=./skills/gone/',
        'FAILED plugin=noarr@m reason=no_skills_array',
        'FAILED plugin=noname@m reason=manifest_name_missing',
    ])
    assert msgs == want, f'logs {msgs}'
    broken = root / 'broken'
    _write(broken / 'settings.json', '{not json')
    with _Logs(sd) as logs2:
        assert sd.discover_skills_workflow('', broken) == []
    assert len(logs2) == 1 and 'settings_unreadable' in logs2[0][1], logs2
    shutil.rmtree(root)
    return 'no skills array (also for a plugin with only a default skills/ folder), no name, missing skill file, not installed, unreadable settings: each logged FAILED and skipped'

def _case_discovery_names() -> str:
    sd = _imp('skill_discovery')
    root = Path(tempfile.mkdtemp(prefix='skillpicker_'))
    claude = root / 'dotclaude'
    plug = _make_plugin(claude, 'p', {'name': 'realname', 'skills': [
        './skills/dirA/', './skills/dirB/', './skills/dirC/']},
        {'skills/dirA': 'labelA', 'skills/dirB': '', 'skills/dirC': None})
    _write(plug / 'skills' / 'dirD' / 'SKILL.md', '# no frontmatter at all\n')
    manifest = json.loads((plug / '.claude-plugin' / 'plugin.json').read_text())
    manifest['skills'].append('./skills/dirD/')
    _write(plug / '.claude-plugin' / 'plugin.json', json.dumps(manifest))
    _write(claude / 'settings.json', json.dumps({'enabledPlugins': {'keyprefix@m': True}}))
    _write(claude / 'plugins' / 'installed_plugins.json', json.dumps({'plugins': {
        'keyprefix@m': [{'scope': 'local', 'projectPath': '/x', 'installPath': '/nonexistent'},
                        {'scope': 'user', 'installPath': str(plug)}]}}))
    with _Logs(sd):
        skills = sd.discover_skills_workflow('', claude)
    got = [(s.short, s.full) for s in skills]
    assert got == [('labelA', 'realname:labelA'), ('dirB', 'realname:dirB'),
                   ('dirC', 'realname:dirC'), ('dirD', 'realname:dirD')], f'got {got}'
    shutil.rmtree(root)
    return f'plugin name from manifest (not key), frontmatter name else dir name, user scope entry preferred: {got}'

def _case_discovery_project_personal() -> str:
    sd = _imp('skill_discovery')
    root = Path(tempfile.mkdtemp(prefix='skillpicker_'))
    claude = _make_claude_dir(root)
    _skill_md(claude / 'skills' / 'mine' / 'SKILL.md', 'Pretty Label')
    general = _make_project(root, 'general', {'penny': 'penny', 'wise2627-tracker': 'wise2627-tracker', 'x-dir': 'Different Label'})
    (Path(general) / '.claude' / 'skills' / 'no-skill-file').mkdir()
    other = _make_project(root, 'other', {})
    with _Logs(sd):
        in_general = sd.discover_skills_workflow(general, claude)
        in_other = sd.discover_skills_workflow(other, claude)
        in_none = sd.discover_skills_workflow('', claude)
    proj = [(s.short, s.full) for s in in_general if s.source == 'project']
    assert proj == [('penny', 'penny'), ('wise2627-tracker', 'wise2627-tracker'), ('x-dir', 'x-dir')], f'project {proj}'
    pers = [(s.short, s.full) for s in in_general if s.source == 'personal']
    assert pers == [('mine', 'mine')], f'personal {pers} (synced folder without SKILL.md must not appear)'
    assert not any(s.source == 'project' for s in in_other), 'project skills leaked into another project'
    assert not any(s.source == 'project' for s in in_none)
    assert [s.source for s in in_general] == ['project'] * 3 + ['personal'] + ['plugin'] * 8, 'group order'
    shutil.rmtree(root)
    return f'project {proj}; personal {pers}; other project and empty cwd see no project skills; order project, personal, plugin'

def _case_insert_text() -> str:
    si = _imp('skill_insert')
    names = _REAL_SHAPED_FULL + ['penny', 'wise2627-tracker']
    for name in names:
        assert si._build_insert_text(name) == f'Aktiviere den Skill {name}.', name
    assert si._build_insert_text('iterative-dev:iterative-dev-doccheck') == 'Aktiviere den Skill iterative-dev:iterative-dev-doccheck.'
    return f'{len(names)} inserted texts exact, e.g. {si._build_insert_text(names[0])!r}'

def _case_applescript() -> str:
    si = _imp('skill_insert')
    text = si._build_insert_text('websearch:websearch-pdf')
    script = si._build_script('TERM-1', text)
    assert script == ('tell application "Ghostty"\n'
                      '  set t to first terminal whose id is "TERM-1"\n'
                      '  input text "Aktiviere den Skill websearch:websearch-pdf." to t\n'
                      'end tell'), script
    for forbidden in ('send key', 'activate', 'focus', 'System Events', 'keystroke'):
        assert forbidden not in script, f'{forbidden} in script'
    tricky = si._build_script('T"1', 'a "quoted" \\ back')
    assert 'whose id is "T\\"1"' in tricky and 'input text "a \\"quoted\\" \\\\ back" to t' in tricky, tricky
    tmp = Path(tempfile.mkdtemp(prefix='skillpicker_'))
    r = subprocess.run(['osacompile', '-o', str(tmp / 'x.scpt'), '-e', script], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, f'osacompile rc={r.returncode} {r.stderr}'
    shutil.rmtree(tmp)
    return 'script exact, no send key/activate/focus/System Events, quoting escaped, osacompile (compile only, nothing executed) rc=0'

def _run_insert(terminal_id, run_effect=None):
    si = _imp('skill_insert')
    logs = []
    calls = []
    def fake_run(cmd, **kw):
        calls.append((cmd, kw))
        if isinstance(run_effect, Exception):
            raise run_effect
        return run_effect or SimpleNamespace(returncode=0, stdout='', stderr='')
    with patch.object(si, 'get_ghostty_terminal_id', lambda cwd: terminal_id), \
         patch.object(si.subprocess, 'run', fake_run), \
         patch.object(si, 'log_menubar', lambda c, m: logs.append((c, m))):
        si.insert_skill_workflow('/p/x', 'gh-cli:gh-cli-search')
    return calls, logs

def _case_insert_paths() -> str:
    out = []
    calls, logs = _run_insert(None)
    assert calls == [], 'osascript called without terminal id'
    assert len(logs) == 1 and logs[0][0] == 'skill' and logs[0][1].startswith('FAILED cwd=/p/x skill=gh-cli:gh-cli-search stage=terminal_id no_terminal_id'), logs
    out.append(f'no terminal id: {logs[0][1]}')
    calls, logs = _run_insert('T9', SimpleNamespace(returncode=1, stdout='', stderr='not allowed'))
    assert len(calls) == 1 and logs[0][1].startswith('FAILED') and 'stage=osascript' in logs[0][1] and 'not allowed' in logs[0][1], logs
    out.append(f'rc=1: {logs[0][1]}')
    calls, logs = _run_insert('T9', subprocess.TimeoutExpired('osascript', 5))
    assert len(calls) == 1 and logs[0][1].startswith('FAILED') and 'stage=osascript' in logs[0][1] and 'TimeoutExpired' in logs[0][1], logs
    out.append(f'timeout: {logs[0][1][:120]}')
    calls, logs = _run_insert('T9')
    assert len(calls) == 1 and calls[0][0][:2] == ['osascript', '-e'], calls
    assert 'Aktiviere den Skill gh-cli:gh-cli-search.' in calls[0][0][2] and 'send key' not in calls[0][0][2]
    assert calls[0][1]['timeout'] == 5
    assert logs[0][1].startswith('OK cwd=/p/x skill=gh-cli:gh-cli-search stage=osascript terminal=T9'), logs
    out.append(f'success: one osascript call, {logs[0][1][:90]}')
    return ' | '.join(out)

def _case_menu() -> str:
    sc = _imp('skill_controller')
    sd = _imp('skill_discovery')
    S = sd.Skill
    skills = [S('penny', 'penny', 'project'), S('mine', 'mine', 'personal'),
              S('a', 'p:a', 'plugin'), S('b', 'p:b', 'plugin')]
    menu = sc._build_menu(skills, None)
    items = list(menu.itemArray())
    kinds = ['sep' if i.isSeparatorItem() else str(i.title()) for i in items]
    assert kinds == ['penny', 'sep', 'mine', 'sep', 'a', 'b'], f'kinds {kinds}'
    reps = [str(i.representedObject()) for i in items if not i.isSeparatorItem()]
    assert reps == ['penny', 'mine', 'p:a', 'p:b'], reps
    assert all(str(i.action()).strip("b'") == 'insertSkill:' for i in items if not i.isSeparatorItem()), [i.action() for i in items]
    empty = list(sc._build_menu([], None).itemArray())
    assert len(empty) == 1 and str(empty[0].title()) == 'no skills' and not empty[0].isEnabled(), empty
    return f'titles {kinds}, represented full names {reps}, empty list -> one disabled "no skills"'

class _FakeApp:
    def __init__(self, sessions=None):
        self.settings = SimpleNamespace(panel_width=422, panel_min_height=460)
        self._panel_controller = None

def _find_grid(pm):
    for v in pm._widgets.stack.arrangedSubviews():
        if hasattr(v, 'numberOfColumns'):
            return v
    raise AssertionError('no grid in stack')

def _case_grid() -> str:
    pm_mod = _imp('panel_manager')
    S = _imp('discover').SessionInfo
    main = S('alpha', 'idle', False, '-a', 'alpha', False, '/tmp/alpha', 's1', '', 2)
    other = S('beta', 'working', False, '-b', 'beta', False, '/tmp/beta', 's2', '', None)
    worker = S('w1', 'idle', False, '-a-w', 'alpha', True, '', 's3', 'worker-alpha-w1', None)
    app = _FakeApp()
    pm = pm_mod.PanelManager(app)
    pm.rebuild([main, other, worker], {})
    grid = _find_grid(pm)
    assert grid.numberOfColumns() == 7, grid.numberOfColumns()
    rows = []
    for r in range(grid.numberOfRows()):
        rows.append([grid.cellAtIndex_(r, c) if False else grid.cellAtColumnIndex_rowIndex_(c, r) for c in range(7)])
    main_rows = [cells for cells in rows if cells[6].contentView() is not None and hasattr(cells[6].contentView(), 'title')
                 and str(cells[6].contentView().attributedTitle().string()) == 'skill']
    assert len(main_rows) == 2, f'skill buttons on {len(main_rows)} rows, want 2 main rows'
    for cells in main_rows:
        btn = cells[6].contentView()
        assert str(btn.action()).strip("b'") == 'showSkillMenu:', btn.action()
        assert btn.tag() == cells[5].contentView().tag(), 'skill tag differs from the mon tag of the row'
        assert str(cells[5].contentView().attributedTitle().string()) == 'mon', 'skill button is not right after mon'
    cwd_by_tag = pm._lookups.cwd_map
    assert sorted(cwd_by_tag.values()) == ['/tmp/alpha', '/tmp/beta'], cwd_by_tag
    worker_rows = [cells for cells in rows if cells[2].contentView() is not None
                   and hasattr(cells[2].contentView(), 'attributedTitle')
                   and str(cells[2].contentView().attributedTitle().string()) == 'w1']
    assert len(worker_rows) == 1, f'worker rows {len(worker_rows)}'
    worker_cell = worker_rows[0][6].contentView()
    assert worker_cell is None or not hasattr(worker_cell, 'attributedTitle'), 'worker row has a button in column 6'
    return f'7 columns, skill button on both main rows right after mon with matching tag, cwd_map {cwd_by_tag}, worker row column 6 empty'

def _case_controller() -> str:
    sc = _imp('skill_controller')
    app = SimpleNamespace(_panel_controller='CTL')
    ctl = sc.SkillController(app)
    logs = []
    inserted = []
    with patch.object(sc, 'log_menubar', lambda c, m: logs.append((c, m))), \
         patch.object(sc, 'insert_skill_workflow', lambda cwd, full: inserted.append((cwd, full))), \
         patch.object(sc, 'discover_skills_workflow', lambda cwd: [_imp('skill_discovery').Skill('a', 'p:a', 'plugin')]):
        button = MagicMock()
        button.bounds.return_value = SimpleNamespace(size=SimpleNamespace(height=20.0))
        ctl.show_menu(button, '')
        assert logs and logs[-1][1].startswith('FAILED stage=menu detail=no_cwd_for_row'), logs
        fake_menu = MagicMock()
        with patch.object(sc, '_build_menu', lambda skills, target: (fake_menu if target == 'CTL' else None)):
            ctl.show_menu(button, '/p/x')
        assert fake_menu.popUpMenuPositioningItem_atLocation_inView_.call_count == 1
        args = fake_menu.popUpMenuPositioningItem_atLocation_inView_.call_args[0]
        assert args[0] is None and args[2] is button and args[1].y == 20.0 and args[1].x == 0.0, args
        assert ctl._menu_cwd == '/p/x'
        item = MagicMock()
        item.representedObject.return_value = 'p:a'
        ctl.handle_choice(item)
        assert inserted == [('/p/x', 'p:a')], inserted
        item.representedObject.return_value = None
        ctl.handle_choice(item)
        assert len(inserted) == 1 and 'missing_choice' in logs[-1][1], (inserted, logs)
    return 'no cwd -> FAILED and no menu; menu popped at the button bottom-left with the controller as target; choice inserts for the clicked row; missing choice -> FAILED'

def _case_isolation() -> str:
    home = Path(os.environ['HOME'])
    log_mod = _imp('menubar_log')
    sd = _imp('skill_discovery')
    assert str(log_mod.MENUBAR_LOG).startswith(str(home)), log_mod.MENUBAR_LOG
    assert str(sd.CLAUDE_DIR).startswith(str(home)), sd.CLAUDE_DIR
    sd.discover_skills_workflow('/nonexistent/project')
    text = log_mod.MENUBAR_LOG.read_text() if log_mod.MENUBAR_LOG.exists() else ''
    assert 'settings_unreadable' in text, f'log {text!r}'
    return f'CLAUDE_DIR={sd.CLAUDE_DIR} and MENUBAR_LOG under the isolated home; discovery log line landed there'

_CASES = {
    'discovery_plugins': _case_discovery_plugins,
    'discovery_tripwires': _case_discovery_tripwires,
    'discovery_names': _case_discovery_names,
    'discovery_project_personal': _case_discovery_project_personal,
    'insert_text': _case_insert_text,
    'applescript': _case_applescript,
    'insert_paths': _case_insert_paths,
    'menu': _case_menu,
    'grid': _case_grid,
    'controller': _case_controller,
    'isolation': _case_isolation,
}

def _build_report(results) -> str:
    lines = ['# t1_skill_picker report', '', f'- time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
             '- every case ran in its own subprocess with an isolated HOME, all cases in parallel',
             '- nothing in this test types into a terminal or opens a menu', '',
             '| case | result | detail |', '|---|---|---|']
    for r in results:
        lines.append(f'| {r["name"]} | {"PASS" if r["ok"] else "FAIL"} | {r["detail"]} |')
    lines.append('')
    lines.append(f'RESULT: {"PASS" if all(r["ok"] for r in results) else "FAIL"}')
    return '\n'.join(lines)

if __name__ == '__main__':
    main()
