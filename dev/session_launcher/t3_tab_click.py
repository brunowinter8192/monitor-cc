# INFRASTRUCTURE
import argparse
import importlib
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from dev.session_launcher.space_lib import write_report
from dev.session_launcher.test_env import isolate_home

_LABELS = ('Sessions', 'RAG', 'Models', 'Launch')
_KEYS = ('main', 'rag', 'models', 'launch')
_EXPECTED_TEXT = {
    'Sessions': '[Sessions] · RAG · Models · Launch',
    'RAG': 'Sessions · [RAG] · Models · Launch',
    'Models': 'Sessions · RAG · [Models] · Launch',
    'Launch': 'Sessions · RAG · Models · [Launch]',
}
_PIXEL_DIFF_LIMIT = 0.08


# ORCHESTRATOR

def main() -> None:
    args = _parse_args()
    if args.case:
        _run_case_in_child(args.case)
        return
    names = sorted(cases())
    with ThreadPoolExecutor(max_workers=len(names)) as pool:
        results = list(pool.map(_spawn_case, names))
    text = _build_report(results)
    path = write_report(__file__, text)
    print(text)
    print(f'report: {path}')
    if any(not r['ok'] for r in results):
        sys.exit(1)


# FUNCTIONS

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument('--case')
    return p.parse_args()


def _run_case_in_child(name: str) -> None:
    try:
        isolate_home()
        detail = cases()[name]()
        print(json.dumps({'ok': True, 'detail': detail}))
    except AssertionError as exc:
        print(json.dumps({'ok': False, 'detail': f'ASSERT {exc}'}))
    except Exception as exc:
        print(json.dumps({'ok': False, 'detail': f'ERROR {exc!r}'}))


def cases():
    return {
        'pieces_and_keys': _case_pieces_and_keys,
        'header_structure': _case_header_structure,
        'visual_equivalence': _case_visual_equivalence,
        'wiring': _case_wiring,
        'click_routing': _case_click_routing,
        'header_recentering': _case_header_recentering,
    }


def _case_pieces_and_keys() -> str:
    pt = _imp('panel_tabs')
    assert pt.TABS == _LABELS and pt.TAB_KEYS == _KEYS, (pt.TABS, pt.TAB_KEYS)
    for label in _LABELS:
        assert pt.TAB_SEPARATOR.join(pt.header_pieces(label)) == _EXPECTED_TEXT[label], label
        pieces = pt.header_pieces(label)
        assert len(pieces) == 4 and sum(p.startswith('[') for p in pieces) == 1, pieces
        assert pt.TAB_SEPARATOR.join(pieces) == _EXPECTED_TEXT[label]
    assert tuple(_imp('panel_lifecycle')._RING) == _KEYS, 'ring is not derived from TAB_KEYS'
    return f'header text exact for all 4 active tabs, TAB_KEYS {pt.TAB_KEYS}, ring == TAB_KEYS'


def _imp(name: str):
    return importlib.import_module(f'src.menubar.{name}')


def _case_header_structure() -> str:
    app, pm, rag, models, launch, headers = _build_headers()
    pt = _imp('panel_tabs')
    panel = _imp('panel')
    out = []
    for label, strip in zip(_LABELS, headers):
        parts = _parts(strip)
        assert len(parts) == 7, f'{label}: {len(parts)} parts'
        buttons = [p for p in parts if hasattr(p, 'attributedTitle')]
        seps = [p for p in parts if not hasattr(p, 'attributedTitle')]
        assert [str(b.attributedTitle().string()) for b in buttons] == pt.header_pieces(label), label
        assert [b.tag() for b in buttons] == [0, 1, 2, 3], [b.tag() for b in buttons]
        assert [_text_of(s) for s in seps] == [pt.TAB_SEPARATOR] * 3
        assert ''.join(_text_of(p) for p in parts) == _EXPECTED_TEXT[label]
        assert [p for p in parts if p in buttons] == buttons and parts[0] is buttons[0] and parts[-1] is buttons[-1]
        assert all(b.isBordered() is False for b in buttons)
        out.append(f'{label}: 4 buttons tags 0-3 + 3 separators, text {_text_of(parts[0])}...')
    return ' | '.join(out)


def _build_headers():
    app = _FakeApp()
    pm = _imp('panel_manager').PanelManager(app)
    rag = _imp('rag_controller').RagController(app)
    models = _imp('model_controller').ModelController(app)
    launch = _imp('launch_controller').LaunchController(app)
    headers = [pm._widgets.header_view, rag._rag_header, models._models_header, launch._launch_header]
    return app, pm, rag, models, launch, headers


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


def _parts(strip):
    header = strip.subviews()[0]
    return sorted(header.subviews(), key=lambda v: v.frame().origin.x)


def _text_of(view) -> str:
    return str(view.attributedTitle().string() if hasattr(view, 'attributedTitle') else view.attributedStringValue().string())


def _case_visual_equivalence() -> str:
    out = []
    for label in _LABELS:
        (o0, o1), (n0, n1), ratio, size = _pixel_stats(label)
        assert abs(o0 - n0) <= 1 and abs(o1 - n1) <= 1, f'{label}: ink old {(o0, o1)} new {(n0, n1)}'
        assert ratio < _PIXEL_DIFF_LIMIT, f'{label}: {ratio:.3f} of pixels differ'
        out.append(f'{label}: ink px old {o0}-{o1} new {n0}-{n1} of {size[0]}, {ratio * 100:.1f}% pixels differ')
    return ' | '.join(out)


def _pixel_stats(active: str):
    from AppKit import NSAttributedString, NSFontAttributeName, NSPanel
    from Foundation import NSMakeRect
    panel = _imp('panel')
    pt = _imp('panel_tabs')
    width, height = 422 - 22, panel._TOP_BAR_H - 1
    old = panel._CursorlessButton.alloc().initWithFrame_(NSMakeRect(0, 0, width, height))
    old.setBordered_(False)
    old.setButtonType_(7)
    old.setAttributedTitle_(NSAttributedString.alloc().initWithString_attributes_(
        pt.TAB_SEPARATOR.join(pt.header_pieces(active)), {NSFontAttributeName: panel._MENLO()}))
    new = panel._make_tab_header(active, 422)
    reps = []
    for view in (old, new):
        host = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(NSMakeRect(0, 0, width, height), 0, 2, True)
        host.contentView().addSubview_(view)
        rep = view.bitmapImageRepForCachingDisplayInRect_(view.bounds())
        view.cacheDisplayInRect_toBitmapImageRep_(view.bounds(), rep)
        reps.append(rep)
    a, b = reps
    w, h = int(a.pixelsWide()), int(a.pixelsHigh())
    def ink(rep):
        cols = [x for x in range(w) if any(rep.colorAtX_y_(x, y).alphaComponent() > 0.05 for y in range(h))]
        return cols[0], cols[-1]
    diff = 0
    for x in range(w):
        for y in range(h):
            ca, cb = a.colorAtX_y_(x, y), b.colorAtX_y_(x, y)
            if max(abs(ca.redComponent() - cb.redComponent()), abs(ca.alphaComponent() - cb.alphaComponent())) > 0.02:
                diff += 1
    return ink(a), ink(b), diff / float(w * h), (w, h)


def _case_wiring() -> str:
    app_mod = _imp('app')
    panel = _imp('panel')
    app, pm, rag, models, launch, headers = _build_headers()
    controller = app_mod._PanelController.alloc().initWithApp_(app)
    for strip in headers:
        buttons = panel._header_buttons(strip)
        assert len(buttons) == 4, len(buttons)
        assert all(b.target() is None and b.action() is None for b in buttons), 'wired before wiring'
    fake = SimpleNamespace(
        _panel_controller=controller,
        _nsapp=SimpleNamespace(nsstatusitem=_AnyAttr()),
        panel=SimpleNamespace(_initialized=False, _widgets=SimpleNamespace(
            quit_btn=_AnyAttr(), kill_btn=_AnyAttr(), header_view=headers[0], panel=_AnyAttr())),
        rag=SimpleNamespace(_rag_panel=_AnyAttr(), _rag_header=headers[1]),
        models=SimpleNamespace(_models_panel=_AnyAttr(), _models_header=headers[2]),
        launch=SimpleNamespace(_launch_panel=_AnyAttr(), _launch_header=headers[3]),
    )
    with patch.object(app_mod, '_set_bar_icon', lambda *a, **k: None):
        assert app_mod.CCMenuBarApp._ensure_wired(fake) is True
    for strip in headers:
        for b in panel._header_buttons(strip):
            assert b.target() is controller, 'target is not the panel controller'
            assert str(b.action()).strip("b'") == 'selectTab:', b.action()
    return '_ensure_wired left all 16 header buttons (4 headers x 4) with the panel controller as target and action selectTab:'


class _AnyAttr:
    def __getattr__(self, name):
        return lambda *a, **k: _AnyAttr()


def _case_click_routing() -> str:
    app_mod = _imp('app')
    panel = _imp('panel')
    app, pm, rag, models, launch, headers = _build_headers()
    controller = app_mod._PanelController.alloc().initWithApp_(app)
    for strip in headers:
        panel._wire_header_buttons(strip, controller)
    app.panel = pm
    app.rag = rag
    app.models = models
    app.launch = launch
    flags = {
        'main': lambda on: setattr(pm, '_panel_open', on),
        'rag': lambda on: setattr(rag, '_rag_open', on),
        'models': lambda on: setattr(models, '_models_open', on),
        'launch': lambda on: setattr(launch, '_launch_open', on),
    }
    calls = []
    checked = 0
    with patch.object(app_mod, 'NSOperationQueue', _SyncQueue), \
         patch.object(app_mod, '_deferred_close_open', lambda a, src, dst: calls.append((a, src, dst))):
        for current_index, current in enumerate(_KEYS):
            for key in _KEYS:
                flags[key](key == current)
            for target_index, target in enumerate(_KEYS):
                calls.clear()
                button = panel._header_buttons(headers[current_index])[target_index]
                assert button.tag() == target_index
                button.performClick_(None)
                if target == current:
                    assert calls == [], f'click on active tab {current} routed: {calls}'
                else:
                    assert calls == [(app, current, target)], f'{current}->{target}: {calls}'
                checked += 1
        for key in _KEYS:
            flags[key](False)
        calls.clear()
        panel._header_buttons(headers[0])[1].performClick_(None)
        assert calls == [], f'click with no open tab routed: {calls}'
    return f'{checked} clicks (4 open tabs x 4 buttons): 12 switch to (current, target) exactly once, 4 active-tab clicks do nothing; no open tab -> nothing'


class _SyncQueue:
    @staticmethod
    def mainQueue():
        return _SyncQueue()

    def addOperationWithBlock_(self, block):
        block()


def _case_header_recentering() -> str:
    from Foundation import NSMakeSize
    panel = _imp('panel')
    out = []
    for label in _LABELS:
        strip = panel._make_tab_header(label, 422)
        header = strip.subviews()[0]
        fixed_width = header.frame().size.width
        for new_width in (422 - 22, 522 - 22, 322 - 22):
            strip.setFrameSize_(NSMakeSize(new_width, strip.frame().size.height))
            center = header.frame().origin.x + header.frame().size.width / 2.0
            assert abs(center - new_width / 2.0) <= 0.75, f'{label}: width {new_width} header center {center}'
            assert abs(header.frame().size.width - fixed_width) < 1.0, f'{label}: header width changed to {header.frame().size.width}'
        out.append(label)
    return f'header stays centered in the top-bar strip when the panel width changes (422, 522, 322): {out}'


def _spawn_case(name: str) -> dict:
    r = subprocess.run([sys.executable, '-m', 'dev.session_launcher.t3_tab_click', '--case', name],
                       capture_output=True, text=True, cwd=str(_ROOT), timeout=180)
    lines = [l for l in r.stdout.splitlines() if l.startswith('{')]
    if r.returncode != 0 or not lines:
        return {'name': name, 'ok': False, 'detail': f'rc={r.returncode} stderr={r.stderr.strip()[-400:]}'}
    out = json.loads(lines[-1])
    out['name'] = name
    return out


def _build_report(results) -> str:
    lines = ['# t3_tab_click report', '',
             '- every case ran in its own subprocess with an isolated HOME, all cases in parallel',
             '- no panel is shown and no real mouse event is sent; clicks use NSButton.performClick_ on unshown panels', '',
             '| case | result | detail |', '|---|---|---|']
    for r in results:
        lines.append(f'| {r["name"]} | {"PASS" if r["ok"] else "FAIL"} | {r["detail"]} |')
    lines.append('')
    lines.append(f'RESULT: {"PASS" if all(r["ok"] for r in results) else "FAIL"}')
    return '\n'.join(lines)


if __name__ == '__main__':
    main()
