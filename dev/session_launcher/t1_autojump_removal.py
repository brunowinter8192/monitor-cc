# INFRASTRUCTURE
import importlib
import json
import re
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from dev.session_launcher.space_lib import write_report
from dev.session_launcher.test_env import isolate_home

_SCAN_DIRS = ('src', 'dev')
_FORBIDDEN = re.compile('|'.join(['auto' + '_focus', 'Auto' + '-Jump', 'toggle' + 'AutoJump', 'auto' + '_jump']))


# ORCHESTRATOR

def main() -> None:
    isolate_home()
    checks = [
        ('menubar log and settings resolve under the isolated home', _check_isolation),
        ('no auto-jump identifiers in any .py under src/ and dev/', _check_no_identifiers_left),
        ('old settings.json with the removed key still loads', _check_old_settings_load),
        ('settings without a file fall back to panel defaults', _check_settings_defaults),
        ('save writes only panel_width and panel_min_height', _check_save_drops_key),
        ('FocusController keeps status tracking, has no tick', _check_focus_controller),
        ('PanelSettings has two fields, controller has no toggle action', _check_app_surface),
    ]
    results = compute_results(checks)
    path = write_report(__file__, _build_report(results))
    print(_build_report(results))
    print_report(path)
    if any_case_failed(results):
        sys.exit(1)


# FUNCTIONS

def _check_isolation() -> str:
    home = Path(sys.modules['os'].environ['HOME'])
    paths = importlib.import_module('src.menubar.paths')
    log_mod = importlib.import_module('src.menubar.menubar_log')
    assert str(log_mod.MENUBAR_LOG).startswith(str(home)), f'log path {log_mod.MENUBAR_LOG}'
    assert str(paths.SETTINGS_FILE).startswith(str(home)), f'settings path {paths.SETTINGS_FILE}'
    return f'MENUBAR_LOG=<home>/{log_mod.MENUBAR_LOG.relative_to(home)}'


def _check_no_identifiers_left() -> str:
    hits = []
    for d in _SCAN_DIRS:
        for path in (_ROOT / d).rglob('*.py'):
            if 'venv' in path.parts or path.name == Path(__file__).name:
                continue
            for i, line in enumerate(path.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
                if _FORBIDDEN.search(line):
                    hits.append(f'{path.relative_to(_ROOT)}:{i}')
    assert not hits, f'hits: {hits}'
    return 'scanned src/ and dev/, 0 hits'


def _check_old_settings_load() -> str:
    mod = _settings_module()
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / 'settings.json'
        p.write_text(json.dumps({'auto_focus': True, 'panel_width': 500, 'panel_min_height': 480}))
        with patch.object(mod, '_SETTINGS_PATH', p):
            got = mod._load_settings()
    assert got == (500, 480), f'got {got}'
    return f'loaded {got}'


def _settings_module():
    return importlib.import_module('src.menubar.app_settings')


def _check_settings_defaults() -> str:
    mod = _settings_module()
    with tempfile.TemporaryDirectory() as tmp:
        with patch.object(mod, '_SETTINGS_PATH', Path(tmp) / 'missing.json'):
            got = mod._load_settings()
    assert got == (mod.PANEL_WIDTH, mod.PANEL_HEIGHT), f'got {got}'
    return f'defaults {got}'


def _check_save_drops_key() -> str:
    mod = _settings_module()
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / 'settings.json'
        p.write_text(json.dumps({'auto_focus': True, 'panel_width': 500, 'panel_min_height': 480}))
        with patch.object(mod, '_SETTINGS_PATH', p):
            mod._save_settings(510, 470)
        data = json.loads(p.read_text())
    assert data == {'panel_width': 510, 'panel_min_height': 470}, f'data {data}'
    return f'file after save: {data}'


def _check_focus_controller() -> str:
    mod = importlib.import_module('src.menubar.focus_controller')
    fc = mod.FocusController(object())
    assert not hasattr(fc, 'tick'), 'tick still present'
    assert not hasattr(fc, '_idle_since_ts'), '_idle_since_ts still present'
    S = importlib.import_module('src.menubar.discover').SessionInfo
    a = S('a', 'working', False, 'e', 'p', False, '/x', 'sid', '')
    assert fc.statuses_changed([a]) is True
    fc.update_statuses([a])
    assert fc.statuses_changed([a]) is False
    return 'statuses_changed True then False after update_statuses'


def _check_app_surface() -> str:
    mod = importlib.import_module('src.menubar.app')
    fields = sorted(vars(mod.PanelSettings(400, 300)))
    assert fields == ['panel_min_height', 'panel_width'], f'fields {fields}'
    assert not hasattr(mod._PanelController, 'toggle' + 'AutoJump_'), 'toggle action still present'
    return f'PanelSettings fields {fields}'


def compute_results(checks):
    return [_run_check(name, fn) for name, fn in checks]


def _run_check(name: str, fn):
    try:
        detail = fn()
        return name, True, detail
    except AssertionError as exc:
        return name, False, f'ASSERT {exc}'
    except Exception as exc:
        return name, False, f'ERROR {exc!r}'


def _build_report(results) -> str:
    lines = ['# t1_autojump_removal report', '',
             '| check | result | detail |', '|---|---|---|']
    for name, ok, detail in results:
        lines.append(f'| {name} | {"PASS" if ok else "FAIL"} | {detail} |')
    lines.append('')
    lines.append(f'RESULT: {"PASS" if all(ok for _, ok, _ in results) else "FAIL"}')
    return '\n'.join(lines)


def print_report(path):
    print(f'report: {path}')


def any_case_failed(results):
    return any(not ok for _, ok, _ in results)


if __name__ == '__main__':
    main()
