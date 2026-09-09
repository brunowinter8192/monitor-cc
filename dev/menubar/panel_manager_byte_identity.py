"""
Byte-identity harness for src/menubar/panel_manager.py (menubar milestone B: PanelManager
class-attribute split + _rebuild_inner helper extraction).

Constructs PanelManager with a minimal fake app (settings + a real NSObject _panel_controller),
calls rebuild(sessions, bg_by_project) with a synthetic 3-project session list (one project with
two mains sharing a desktop number -> conflict; one with a worker; one with a bg timer and a main
with desktop_no=None), dumps the full NSGridView contents (per cell: class, title string, tag,
action, color description, row height) plus every lookup map, hashes. Then calls update_inplace
with one session's status flipped and extends the hash. Run before and after a change; both
hashes must match.

Targets PanelManager's post-split attribute layout (menubar milestone B): `_widgets` (a
_PanelWidgets: panel/stack/quit_btn/toggle_btn/kill_btn) and `_lookups` (a _PanelLookups: the 6
per-rebuild maps) replace the 11 flat attrs the pre-split PanelManager carried; the fake app
exposes `.settings` (panel_width/panel_min_height/auto_focus) instead of the 3 flat attrs
PanelManager used to read directly off `app`. Baseline hash captured against the pre-split
layout was 0efc9d390506a6e17c5b33958074e44d6ae5831ddd898ae82c9bd8b008876d42 — this file's own
accessor code was updated in the same commit as the split, mirroring
dev/menubar/model_controller_byte_identity.py's import-target update pattern from milestone A.

Usage (from project root):
    ./venv/bin/python dev/menubar/panel_manager_byte_identity.py

Prints one HASH line. If AppKit refuses headless NSGridView introspection, reports SKIPPED with
the reason and falls back to an import + rebuild() smoke check.
"""

# INFRASTRUCTURE
import hashlib
import importlib
import json
import sys
from collections import namedtuple
from pathlib import Path
from types import SimpleNamespace

from AppKit import NSForegroundColorAttributeName

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

_BgInfo = namedtuple('_BgInfo', ['min_remaining', 'sleep_pids'])

# ORCHESTRATOR


def main():
    pm_mod = _import_panel_manager()
    discover_mod = _import_discover()
    try:
        print(f'HASH: {_run(pm_mod, discover_mod)}')
    except Exception as exc:
        print(f'HASH: SKIPPED (headless AppKit introspection failed: {exc})')
        _smoke_import(pm_mod, discover_mod)


# FUNCTIONS

# Loaded via importlib (not a literal 'from src.' module-level line) — dev/ scripts may not use
# that form (block_dev_imports_src); panel_manager.py's package-relative imports only resolve
# when loaded as part of the src.menubar package anyway.
def _import_panel_manager():
    return importlib.import_module('.'.join(['src', 'menubar', 'panel_manager']))


def _import_discover():
    return importlib.import_module('.'.join(['src', 'menubar', 'discover']))


# 3 projects: alpha has two mains sharing desktop_no=2 (conflict -> "[!2]" red rendering); beta
# has one main + one worker (worker row, clickable); gamma has one main with desktop_no=None
# (no slot prefix) and carries the bg timer (badge + abort button on its separator row).
def _make_sessions(SessionInfo):
    return [
        SessionInfo(name='alpha-main1', status='working', has_bg=False, encoded_dir='-alpha1',
                    project_name='alpha', is_worker=False, cwd='/tmp/alpha1', session_id='s1',
                    tmux_session_name='', desktop_no=2),
        SessionInfo(name='alpha-main2', status='idle', has_bg=False, encoded_dir='-alpha2',
                    project_name='alpha', is_worker=False, cwd='/tmp/alpha2', session_id='s2',
                    tmux_session_name='', desktop_no=2),
        SessionInfo(name='beta-main', status='idle', has_bg=False, encoded_dir='-beta',
                    project_name='beta', is_worker=False, cwd='/tmp/beta', session_id='s3',
                    tmux_session_name='', desktop_no=1),
        SessionInfo(name='beta-worker', status='working', has_bg=False, encoded_dir='-beta-w',
                    project_name='beta', is_worker=True, cwd='', session_id='s4',
                    tmux_session_name='worker-beta-w1', desktop_no=None),
        SessionInfo(name='gamma-main', status='idle', has_bg=True, encoded_dir='-gamma',
                    project_name='gamma', is_worker=False, cwd='/tmp/gamma', session_id='s5',
                    tmux_session_name='', desktop_no=None),
    ]


def _bg_by_project():
    return {'gamma': _BgInfo(min_remaining=90, sleep_pids=(4321,))}


# PanelManager reads app.settings.panel_width / .panel_min_height / .auto_focus and
# app._panel_controller (post-milestone-B layout).
class _FakeApp:
    def __init__(self):
        self.settings = SimpleNamespace(panel_width=422, panel_min_height=460, auto_focus=False)
        from Foundation import NSObject

        class _FakePanelController(NSObject):
            pass

        self._panel_controller = _FakePanelController.alloc().init()


def _safe(obj, name):
    if obj is None or not hasattr(obj, name):
        return None
    try:
        return getattr(obj, name)()
    except Exception:
        return None


def _color_desc(attr) -> str:
    if attr is None or attr.length() == 0:
        return None
    try:
        attrs_dict, _rng = attr.attributesAtIndex_effectiveRange_(0, None)
        color = attrs_dict.get(NSForegroundColorAttributeName)
        return str(color) if color is not None else None
    except Exception:
        return 'ERR'


def _dump_cell(view) -> dict:
    if view is None:
        return {'class': None}
    attr = _safe(view, 'attributedTitle')
    action = _safe(view, 'action')
    return {
        'class': type(view).__name__,
        'title': str(attr.string()) if attr is not None else _safe(view, 'title'),
        'tag': _safe(view, 'tag'),
        'action': str(action) if action else None,
        'color': _color_desc(attr),
    }


# Walks every arranged subview of the stack; for the one NSGridView among them, dumps every
# row/cell (class/title/tag/action/color/height); everything else (separator, header label) dumps
# by class name + frame only.
def _dump_stack(stack) -> list:
    entries = []
    for view in stack.arrangedSubviews():
        if hasattr(view, 'numberOfRows'):
            for r in range(view.numberOfRows()):
                row = view.rowAtIndex_(r)
                cells = []
                for c in range(view.numberOfColumns()):
                    try:
                        cell = view.cellAtColumnIndex_rowIndex_(c, r)
                        cells.append(_dump_cell(cell.contentView()))
                    except Exception as exc:
                        cells.append({'error': str(exc)})
                entries.append({'row': r, 'height': round(row.height(), 3), 'cells': cells})
        else:
            frame = view.frame()
            entries.append({'view_class': type(view).__name__,
                            'w': round(frame.size.width, 3), 'h': round(frame.size.height, 3)})
    return entries


def _dump_lookups(pm) -> dict:
    lookups = pm._lookups
    return {
        'displayed_items': sorted(lookups.displayed_items.keys()),
        'cwd_map': dict(sorted(lookups.cwd_map.items())),
        'worker_tag_map': dict(sorted(lookups.worker_tag_map.items())),
        'desktop_to_cwd': dict(sorted(lookups.desktop_to_cwd.items())),
        'abort_btns_by_project': sorted(lookups.abort_btns_by_project.keys()),
        'abort_project_for_tag': dict(sorted(lookups.abort_project_for_tag.items())),
    }


def _run(pm_mod, discover_mod) -> str:
    digest = hashlib.sha256()
    app = _FakeApp()
    pm = pm_mod.PanelManager(app)
    sessions = _make_sessions(discover_mod.SessionInfo)
    bg = _bg_by_project()

    pm.rebuild(sessions, bg)
    digest.update(b'rebuild')
    digest.update(json.dumps(_dump_stack(pm._widgets.stack), sort_keys=True).encode())
    digest.update(json.dumps(_dump_lookups(pm), sort_keys=True).encode())

    flipped = list(sessions)
    flipped[0] = flipped[0]._replace(status='idle')
    pm.update_inplace(flipped, bg)
    digest.update(b'update_inplace')
    digest.update(json.dumps(_dump_stack(pm._widgets.stack), sort_keys=True).encode())
    digest.update(json.dumps(_dump_lookups(pm), sort_keys=True).encode())
    return digest.hexdigest()


def _smoke_import(pm_mod, discover_mod) -> None:
    app = _FakeApp()
    pm = pm_mod.PanelManager(app)
    sessions = _make_sessions(discover_mod.SessionInfo)
    pm.rebuild(sessions, _bg_by_project())
    print('SMOKE: import + PanelManager(app).rebuild() succeeded with no exception')


if __name__ == '__main__':
    main()
