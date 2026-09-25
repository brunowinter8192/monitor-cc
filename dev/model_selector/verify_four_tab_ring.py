# INFRASTRUCTURE
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from Foundation import NSMakeRect

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dev.session_launcher.test_env import isolate_home

REPORT_PATH = REPO_ROOT / "dev" / "model_selector" / "md" / "verify_four_tab_ring.md"


# ORCHESTRATOR

def verify_four_tab_ring_workflow() -> None:
    isolate_home()
    panel_manager   = _imp('src.menubar.panel_manager')
    rag_controller  = _imp('src.menubar.rag_controller')
    model_controller = _imp('src.menubar.model_controller')
    launch_controller = _imp('src.menubar.launch_controller')
    panel_lifecycle = _imp('src.menubar.panel_lifecycle')

    lines = ["# Four-tab ring verification", ""]

    app = _FakeApp(panel_manager, rag_controller, model_controller, launch_controller)

    with patch('src.menubar.panel_lifecycle.NSOperationQueue', _SyncOperationQueue):
        _verify_forward_ring(app, panel_lifecycle, lines)
        _verify_reverse_ring(app, panel_lifecycle, lines)

    lines.append("")
    lines.append("RESULT: PASS — four-tab ring (Sessions/RAG/Models/Launch) correct in both directions, "
                "against the real _open_*_panel/_close_*_panel/_deferred_close_open functions.")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


# FUNCTIONS

def _imp(module_name: str):
    return importlib.import_module(module_name)


class _FakeApp:
    def __init__(self, panel_manager, rag_controller, model_controller, launch_controller):
        self.settings = SimpleNamespace(panel_width=380, panel_min_height=460)
        self._panel_controller = None
        self._nsapp = _FakeNSApp()
        self.hotkey = _FakeHotkey()
        self.sessions = _FakeSessions()
        self.panel  = panel_manager.PanelManager(self)
        self.rag    = rag_controller.RagController(self)
        self.models = model_controller.ModelController(self)
        self.launch = launch_controller.LaunchController(self)


class _FakeStatusItem:
    def button(self): return _FakeButton()


class _FakeNSApp:
    nsstatusitem = _FakeStatusItem()


class _FakeButton:
    def window(self): return _FakeFrame()


class _FakeFrame:
    def frame(self): return NSMakeRect(0.0, 0.0, 22.0, 22.0)


class _FakeHotkey:
    def __init__(self):
        self._right = None
        self._left = None

    def register_arrow_right(self, cb): self._right = cb
    def register_arrow_left(self, cb):  self._left = cb
    def unregister_arrow_right(self):   self._right = None
    def unregister_arrow_left(self):    self._left = None
    def reregister_digits(self, desktop_to_cwd): pass
    def unregister_digits(self): pass

    def right(self): self._right()
    def left(self):  self._left()


class _FakeSessions:
    def refresh(self): return []
    @property
    def bg_by_project(self): return {}


class _SyncOperationQueue:
    @staticmethod
    def mainQueue():
        return _SyncOperationQueue()

    def addOperationWithBlock_(self, block):
        block()


def _verify_forward_ring(app, panel_lifecycle, lines) -> None:
    lines.append("## Forward: Sessions -> RAG -> Models -> Launch -> Sessions (Cmd+->)")
    panel_lifecycle._open_main_panel(app)
    assert _only_open(app, 'main')
    lines.append("open main: only main open")

    for src, dst in (('main', 'rag'), ('rag', 'models'), ('models', 'launch'), ('launch', 'main')):
        app.hotkey.right()
        assert _only_open(app, dst), f"Cmd+-> from {src} did not land on {dst}"
        lines.append(f"Cmd+-> from {src}: now on {dst}")

    lines.append("")


def _only_open(app, name) -> bool:
    flags = {'main': app.panel._panel_open, 'rag': app.rag._rag_open,
             'models': app.models._models_open, 'launch': app.launch._launch_open}
    return flags[name] and sum(flags.values()) == 1


def _verify_reverse_ring(app, panel_lifecycle, lines) -> None:
    lines.append("## Reverse: Sessions -> Launch -> Models -> RAG -> Sessions (Cmd+<-)")
    for src, dst in (('main', 'launch'), ('launch', 'models'), ('models', 'rag'), ('rag', 'main')):
        app.hotkey.left()
        assert _only_open(app, dst), f"Cmd+<- from {src} did not land on {dst}"
        lines.append(f"Cmd+<- from {src}: now on {dst}")


if __name__ == "__main__":
    verify_four_tab_ring_workflow()
