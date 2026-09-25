# INFRASTRUCTURE
import argparse
import importlib
import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from dev.session_launcher.space_lib import write_report
from dev.session_launcher.test_env import isolate_home

_JSON_DIR = Path('/tmp/session_launcher_p2_panel_snapshot')
_SETTINGS_VARIANTS = ((422, 460), (500, 300), (380, 700), (600, 520))
_STATUS_ITEM_FRAMES = ((1000.0, 900.0, 22.0, 22.0), (12.5, 40.0, 30.0, 24.0))
_REPOSITION_OLD_NAMES = {'rag': '_reposition_rag_panel', 'models': '_reposition_models_panel',
                         'launch': '_reposition_launch_panel'}


# ORCHESTRATOR

def main() -> None:
    args = _parse_args()
    if args.label:
        isolate_home()
        _JSON_DIR.mkdir(parents=True, exist_ok=True)
        path = compute_path(args)
        path.write_text(json.dumps(_take_snapshot(), indent=1, sort_keys=True), encoding='utf-8')
        print(f'snapshot: {path}')
        return
    text, ok = _compare_snapshots()
    path = write_report(__file__, text)
    print(text)
    print(f'report: {path}')
    if not ok:
        sys.exit(1)


# FUNCTIONS

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument('--label')
    return p.parse_args()


def compute_path(args):
    return _JSON_DIR / f'p2_panel_snapshot_{args.label}.json'


def _take_snapshot() -> dict:
    app = _FakeApp()
    controllers = _build_controllers(app)
    panels = _panels(controllers)
    snap = {'initial': {n: _describe_panel(p) for n, p in panels.items()}}
    for width, min_height in _SETTINGS_VARIANTS:
        app.settings.panel_width = width
        app.settings.panel_min_height = min_height
        _rebuild_all(controllers)
        snap[f'rebuilt_{width}x{min_height}'] = {n: _describe_panel(p) for n, p in panels.items()}
    for index, frame in enumerate(_STATUS_ITEM_FRAMES):
        item = _FakeStatusItem(frame)
        for name, panel in panels.items():
            _reposition_function(name)(panel, item)
        snap[f'repositioned_{index}'] = {n: _rect(p.frame()) for n, p in panels.items()}
    before = {n: _rect(p.frame()) for n, p in panels.items()}
    windowless = _FakeStatusItem(None)
    for name in ('rag', 'models', 'launch'):
        _reposition_function(name)(panels[name], windowless)
    snap['reposition_without_status_window_unchanged'] = {n: _rect(panels[n].frame()) == before[n]
                                                          for n in ('rag', 'models', 'launch')}
    return snap


class _FakeApp:
    def __init__(self):
        self.settings = SimpleNamespace(panel_width=422, panel_min_height=460)
        self._panel_controller = None
        self.sessions = _FakeSessions()


class _FakeSessions:
    def refresh(self):
        return []

    @property
    def bg_by_project(self):
        return {}


def _build_controllers(app) -> dict:
    return {'sessions': _imp('panel_manager').PanelManager(app),
            'rag': _imp('rag_controller').RagController(app),
            'models': _imp('model_controller').ModelController(app),
            'launch': _imp('launch_controller').LaunchController(app)}


def _imp(name: str):
    return importlib.import_module(f'src.menubar.{name}')


def _panels(controllers: dict) -> dict:
    return {'sessions': controllers['sessions']._widgets.panel, 'rag': controllers['rag']._rag_panel,
            'models': controllers['models']._models_panel, 'launch': controllers['launch']._launch_panel}


def _describe_panel(panel) -> dict:
    size = panel.contentMinSize()
    return {'cls': type(panel).__name__, 'styleMask': int(panel.styleMask()), 'level': int(panel.level()),
            'collectionBehavior': int(panel.collectionBehavior()), 'hasShadow': bool(panel.hasShadow()),
            'opaque': bool(panel.isOpaque()), 'acceptsMouseMoved': bool(panel.acceptsMouseMovedEvents()),
            'contentMinSize': [float(size.width), float(size.height)], 'frame': _rect(panel.frame()),
            'content': _describe_view(panel.contentView())}


def _rect(r) -> list:
    return [round(float(r.origin.x), 3), round(float(r.origin.y), 3),
            round(float(r.size.width), 3), round(float(r.size.height), 3)]


def _describe_view(view) -> dict:
    node = {'cls': type(view).__name__, 'frame': _rect(view.frame()),
            'autoresizing': int(view.autoresizingMask()), 'text': _view_text(view),
            'tag': int(view.tag()) if hasattr(view, 'tag') else None}
    children = list(view.arrangedSubviews()) if hasattr(view, 'arrangedSubviews') else []
    children += [c for c in view.subviews() if c not in children]
    node['children'] = [_describe_view(c) for c in children]
    return node


def _view_text(view):
    if hasattr(view, 'attributedTitle'):
        return str(view.attributedTitle().string())
    if hasattr(view, 'attributedStringValue'):
        return str(view.attributedStringValue().string())
    return None


def _rebuild_all(controllers: dict) -> None:
    controllers['sessions'].rebuild([])
    controllers['rag'].rebuild()
    controllers['models'].rebuild()
    controllers['launch'].open()


class _FakeStatusItem:
    def __init__(self, frame):
        self._frame = frame

    def button(self):
        return _FakeButton(self._frame)


class _FakeButton:
    def __init__(self, frame):
        self._frame = frame

    def window(self):
        return _FakeWindow(self._frame) if self._frame else None


class _FakeWindow:
    def __init__(self, frame):
        self._frame = frame

    def frame(self):
        from Foundation import NSMakeRect
        return NSMakeRect(*self._frame)


def _reposition_function(name: str):
    lifecycle = _imp('panel_lifecycle')
    if name == 'sessions':
        return lifecycle._reposition_panel
    old = getattr(lifecycle, _REPOSITION_OLD_NAMES[name], None)
    return old if old is not None else lifecycle._reposition_tab_panel


def _compare_snapshots():
    before = _require_snapshot('before')
    after = _require_snapshot('after')
    fb, fa = dict(_flatten(before)), dict(_flatten(after))
    diffs = [(k, fb.get(k, '<missing>'), fa.get(k, '<missing>')) for k in sorted(set(fb) | set(fa)) if fb.get(k, '<missing>') != fa.get(k, '<missing>')]
    ok = not diffs
    lines = ['# p2_panel_snapshot report', '', f'- time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
             f'- compared values: {len(fb)} before, {len(fa)} after',
             '- snapshots: panel class, style mask, level, collection behavior, shadow, opaque, mouse-moved, content min size, frames, full recursive subview tree (class, frame, autoresizing, tag, text)',
             f'- covered: sessions/rag/models/launch panels initially, after rebuild at {len(_SETTINGS_VARIANTS)} width/min-height settings, after reposition against {len(_STATUS_ITEM_FRAMES)} status-item frames, and reposition with no status window', '']
    if ok:
        lines.append('RESULT: PASS - before and after snapshots are identical')
    else:
        lines.append(f'RESULT: FAIL - {len(diffs)} differences')
        lines.append('')
        lines.extend(f'- {k}: before {b!r} after {a!r}' for k, b, a in diffs[:60])
    return '\n'.join(lines) + '\n', ok


def _require_snapshot(label: str) -> dict:
    path = _JSON_DIR / f'p2_panel_snapshot_{label}.json'
    if not path.is_file():
        raise SystemExit(f'missing {path}: take it first with --label {label}')
    return json.loads(path.read_text())


def _flatten(value, prefix=''):
    if isinstance(value, dict):
        for key in sorted(value):
            yield from _flatten(value[key], f'{prefix}/{key}')
    elif isinstance(value, list) and value and isinstance(value[0], dict):
        for i, item in enumerate(value):
            yield from _flatten(item, f'{prefix}[{i}]')
    else:
        yield prefix, value


if __name__ == '__main__':
    main()
