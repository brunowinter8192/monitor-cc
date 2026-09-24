# INFRASTRUCTURE
import ast
from unittest import mock

from p5_common import load, root, tmpdir, check, point_log, log_text

# ORCHESTRATOR

def main() -> None:
    d = tmpdir()
    mlog = point_log(d)
    status_item_wiring(mlog)
    tick_and_hotkey_source(mlog)
    restart_route(mlog)
    panel_cycle_errors(mlog)
    hotkey_status_and_handlers(mlog)

# FUNCTIONS

class _Obj:
    pass

def status_item_wiring(mlog) -> None:
    app = load('app')
    cls = app.CCMenuBarApp
    fake = _Obj()
    fake._nsapp = _Obj()
    r1 = cls._status_item_button(fake)
    r2 = cls._status_item_button(fake)
    check('g3.status_item.not_ready_returns_none_logs_once', r1 is None and r2 is None and log_text(mlog).count('[wiring] status item not ready') == 1)
    wired = _Obj()
    wired.panel = mock.MagicMock()
    wired.panel._initialized = False
    wired.rag = mock.MagicMock()
    wired.models = mock.MagicMock()
    wired.launch = mock.MagicMock()
    wired._panel_controller = object()
    wired._nsapp = mock.MagicMock()
    wired._status_item_button = lambda: wired._nsapp.nsstatusitem.button()
    ok = cls._ensure_wired(wired)
    check('g3.ensure_wired.success', ok is True and wired.panel._initialized is True)
    broken = _Obj()
    broken.panel = mock.MagicMock()
    broken.panel._initialized = False
    broken.panel._widgets.quit_btn.setTarget_.side_effect = AttributeError('quit_btn renamed')
    broken._panel_controller = object()
    broken._status_item_button = lambda: mock.MagicMock()
    try:
        cls._ensure_wired(broken)
        propagated = False
    except AttributeError:
        propagated = True
    check('g3.ensure_wired.wiring_attribute_error_propagates', propagated)

def tick_and_hotkey_source(mlog) -> None:
    tree = ast.parse((root() / 'src' / 'menubar' / 'app.py').read_text())
    tick = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == '_tick'][0]
    check('g3.tick.no_try_around_snapshot', not any(isinstance(n, ast.Try) for n in ast.walk(tick)))
    bare = [n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler) and all(isinstance(b, ast.Pass) for b in n.body)]
    check('g3.app.no_silent_except_pass', not bare)

def restart_route(mlog) -> None:
    app = load('app')
    calls = []
    with mock.patch.object(app, 'write_plist', lambda: calls.append('source')), \
         mock.patch.object(app, 'write_plist_py2app', lambda: calls.append('py2app')):
        app._write_launch_plist(False)
        app._write_launch_plist(True)
    text = log_text(mlog)
    check('g3.restart.route_logged_and_dispatched', calls == ['source', 'py2app'] and 'route=source' in text and 'route=py2app' in text)

def panel_cycle_errors(mlog) -> None:
    pl = load('panel_lifecycle')
    with mock.patch.object(pl, '_panel_of', side_effect=RuntimeError('boom')):
        pl._deferred_close_open(mock.MagicMock(), 'main', 'rag')
    with mock.patch.object(pl, '_open_tab_name', side_effect=RuntimeError('boom2')):
        pl._background_panel(mock.MagicMock())
    text = log_text(mlog)
    check('g3.panel_lifecycle.errors_in_menubar_log', 'cycling main->rag error' in text and 'Cmd+K deferred-block error' in text)

class _FakeCarbon:
    def __init__(self, install=0, register=0, get_param=0, raise_get=False):
        self.install, self.register, self.get_param, self.raise_get = install, register, get_param, raise_get
        self.callbacks = []
    def GetApplicationEventTarget(self):
        return 1
    def GetCurrentEventTime(self):
        return 0.0
    def GetEventTime(self, event):
        return 0.0
    def InstallEventHandler(self, target, cb, n, spec, data, ref):
        self.callbacks.append(cb)
        return self.install
    def RegisterEventHotKey(self, *args):
        return self.register
    def GetEventParameter(self, *args):
        if self.raise_get:
            raise RuntimeError('carbon failure')
        return self.get_param

def hotkey_status_and_handlers(mlog) -> None:
    hc = load('hotkey_controller')
    hd = load('hotkey_digits')
    ha = load('hotkey_arrows')
    fake = _FakeCarbon(install=-9868, register=-9878)
    with mock.patch.object(hc, '_load_carbon', lambda: fake):
        hc.register_cmd_l(lambda: None)
    text = log_text(mlog)
    check('g3.hotkey.cmd_l_status_logged', 'InstallEventHandler failed status=-9868 cmd+l' in text and 'RegisterEventHotKey failed status=-9878 cmd+l' in text)
    ok_fake = _FakeCarbon(raise_get=True)
    with mock.patch.object(hc, '_load_carbon', lambda: ok_fake):
        hc.register_cmd_k(lambda: None)
    result = ok_fake.callbacks[-1](None, None, None)
    check('g3.hotkey.handler_exception_logged_returns_zero', result == 0 and 'handler failed cmd+k err=RuntimeError' in log_text(mlog))
    param_fake = _FakeCarbon(get_param=-50)
    with mock.patch.object(hc, '_load_carbon', lambda: param_fake):
        hc.register_cmd_l(lambda: None)
    param_fake.callbacks[-1](None, None, None)
    check('g3.hotkey.get_event_parameter_status_logged', 'GetEventParameter failed status=-50' in log_text(mlog))
    dig = _FakeCarbon(register=-1)
    hd._DIGIT_HANDLER_CB = None
    with mock.patch.object(hd, '_load_carbon', lambda: dig):
        hd.register_cmd_digits({1: lambda: None})
    hd._DIGIT_HANDLER_CB = None
    hd._DIGIT_CALLBACKS.clear()
    check('g3.hotkey.digits_register_status_logged', 'RegisterEventHotKey failed status=-1 slot=1' in log_text(mlog))
    arr = _FakeCarbon(register=-2)
    ha._ARROW_HANDLER_CB = None
    with mock.patch.object(ha, '_load_carbon', lambda: arr):
        ha.register_cmd_arrow_right(lambda: None)
    ha._ARROW_HANDLER_CB = None
    ha._ARROW_CALLBACKS.clear()
    check('g3.hotkey.arrow_register_status_logged', 'RegisterEventHotKey failed status=-2 cmd+right' in log_text(mlog))


if __name__ == '__main__':
    main()
