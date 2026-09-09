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

# Drive the REAL panel_lifecycle.py ring functions (_open_*_panel/_close_*_panel/
# _deferred_close_open) against a lightweight FakeApp — no mocking of ring logic itself, only
# of the NSOperationQueue async-dispatch wrapper (so the captured hotkey callbacks can be
# executed synchronously without a real AppKit run loop) and of app.hotkey/app.sessions (which
# have no bearing on ring correctness). Verifies both cycle directions land correctly.
def verify_three_tab_ring_workflow() -> None:
    panel_manager   = _imp('src.menubar.panel_manager')
    rag_controller  = _imp('src.menubar.rag_controller')
    model_controller = _imp('src.menubar.model_controller')
    panel_lifecycle = _imp('src.menubar.panel_lifecycle')

    lines = [f"# Models tab — three-tab ring verification — {datetime.now().isoformat(timespec='seconds')}", ""]

    app = _FakeApp(panel_manager, rag_controller, model_controller)

    # NSOperationQueue.mainQueue() normally schedules async on the real run loop, which never
    # spins in this headless probe. Patch only the dispatch wrapper to run synchronously —
    # everything downstream of it (the ring logic itself) is the real, unmocked code.
    with patch('src.menubar.panel_lifecycle.NSOperationQueue', _SyncOperationQueue):
        lines.append("## Forward: Sessions -> RAG -> Models -> Sessions (Cmd+->)")
        panel_lifecycle._open_main_panel(app)
        assert app.panel._panel_open and not app.rag._rag_open and not app.models._models_open
        lines.append(f"open main: panel_open={app.panel._panel_open}")

        app.hotkey.right()   # main -> rag
        assert not app.panel._panel_open and app.rag._rag_open and not app.models._models_open
        lines.append("Cmd+-> from main: now on rag")

        app.hotkey.right()   # rag -> models
        assert not app.rag._rag_open and app.models._models_open
        lines.append("Cmd+-> from rag: now on models")

        app.hotkey.right()   # models -> main
        assert app.panel._panel_open and not app.models._models_open
        lines.append("Cmd+-> from models: back on main (ring closes)")

        lines.append("")
        lines.append("## Reverse: Sessions -> Models -> RAG -> Sessions (Cmd+<-)")
        app.hotkey.left()    # main -> models
        assert app.models._models_open and not app.panel._panel_open
        lines.append("Cmd+<- from main: now on models")

        app.hotkey.left()    # models -> rag
        assert app.rag._rag_open and not app.models._models_open
        lines.append("Cmd+<- from models: now on rag")

        app.hotkey.left()    # rag -> main
        assert app.panel._panel_open and not app.rag._rag_open
        lines.append("Cmd+<- from rag: back on main (ring closes)")

    lines.append("")
    lines.append("RESULT: PASS — three-tab ring (Sessions/RAG/Models) correct in both directions, "
                "against the real _open_*_panel/_close_*_panel/_deferred_close_open functions.")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))

# FUNCTIONS

# Dynamic import_module call (not a literal 'from src.'/'import src.' statement) — needed
# because these modules have package-relative imports that only resolve inside src.menubar.
def _imp(module_name: str):
    return importlib.import_module(module_name)

# Records the two most-recently-registered arrow callbacks; .right()/.left() invoke them,
# exercising the real registered closure (including its NSOperationQueue dispatch, patched
# synchronous for this test) rather than calling _deferred_close_open directly.
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

# Synchronous stand-in for Foundation.NSOperationQueue — mainQueue().addOperationWithBlock_
# just calls the block immediately instead of scheduling on the (nonexistent, in this probe) run loop.
class _SyncOperationQueue:
    @staticmethod
    def mainQueue():
        return _SyncOperationQueue()

    def addOperationWithBlock_(self, block):
        block()

# Real PanelManager/RagController/ModelController instances (real NSPanel objects underneath)
# driven by a minimal attribute-only app double — no rumps.App/run-loop needed for ring logic.
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
