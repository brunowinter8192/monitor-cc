# INFRASTRUCTURE
import importlib
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from Foundation import NSMakeRect

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

REPORT_PATH = REPO_ROOT / "dev" / "model_selector" / "md" / "verify_three_tab_ring.md"

# ORCHESTRATOR

def verify_three_tab_ring_workflow() -> None:
    panel_manager   = _imp('src.menubar.panel_manager')
    rag_controller  = _imp('src.menubar.rag_controller')
    model_controller = _imp('src.menubar.model_controller')
    panel_lifecycle = _imp('src.menubar.panel_lifecycle')

    lines = [f"# Models tab — three-tab ring verification — {datetime.now().isoformat(timespec='seconds')}", ""]

    app = _FakeApp(panel_manager, rag_controller, model_controller)

    with patch('src.menubar.panel_lifecycle.NSOperationQueue', _SyncOperationQueue):
        _verify_forward_ring(app, panel_lifecycle, lines)
        _verify_reverse_ring(app, panel_lifecycle, lines)

    lines.append("")
    lines.append("RESULT: PASS — three-tab ring (Sessions/RAG/Models) correct in both directions, "
                "against the real _open_*_panel/_close_*_panel/_deferred_close_open functions.")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))

# FUNCTIONS

def _verify_forward_ring(app, panel_lifecycle, lines) -> None:
    lines.append("## Forward: Sessions -> RAG -> Models -> Sessions (Cmd+->)")
    panel_lifecycle._open_main_panel(app)
    assert app.panel._panel_open and not app.rag._rag_open and not app.models._models_open
    lines.append(f"open main: panel_open={app.panel._panel_open}")

    app.hotkey.right()
    assert not app.panel._panel_open and app.rag._rag_open and not app.models._models_open
    lines.append("Cmd+-> from main: now on rag")

    app.hotkey.right()
    assert not app.rag._rag_open and app.models._models_open
    lines.append("Cmd+-> from rag: now on models")

    app.hotkey.right()
    assert app.panel._panel_open and not app.models._models_open
    lines.append("Cmd+-> from models: back on main (ring closes)")

    lines.append("")

def _verify_reverse_ring(app, panel_lifecycle, lines) -> None:
    lines.append("## Reverse: Sessions -> Models -> RAG -> Sessions (Cmd+<-)")
    app.hotkey.left()
    assert app.models._models_open and not app.panel._panel_open
    lines.append("Cmd+<- from main: now on models")

    app.hotkey.left()
    assert app.rag._rag_open and not app.models._models_open
    lines.append("Cmd+<- from models: now on rag")

    app.hotkey.left()
    assert app.panel._panel_open and not app.rag._rag_open
    lines.append("Cmd+<- from rag: back on main (ring closes)")

def _imp(module_name: str):
    return importlib.import_module(module_name)

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

class _FakeFrame:
    def frame(self): return NSMakeRect(0.0, 0.0, 22.0, 22.0)

class _FakeButton:
    def window(self): return _FakeFrame()

class _FakeStatusItem:
    def button(self): return _FakeButton()

class _FakeNSApp:
    nsstatusitem = _FakeStatusItem()

class _SyncOperationQueue:
    @staticmethod
    def mainQueue():
        return _SyncOperationQueue()

    def addOperationWithBlock_(self, block):
        block()

class _FakeApp:
    def __init__(self, panel_manager, rag_controller, model_controller):
        self.settings = SimpleNamespace(panel_width=380, panel_min_height=460, auto_focus=False)
        self._panel_controller = None
        self._nsapp = _FakeNSApp()
        self.hotkey = _FakeHotkey()
        self.sessions = _FakeSessions()
        self.panel  = panel_manager.PanelManager(self)
        self.rag    = rag_controller.RagController(self)
        self.models = model_controller.ModelController(self)


if __name__ == "__main__":
    verify_three_tab_ring_workflow()
