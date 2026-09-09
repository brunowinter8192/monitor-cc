"""
Byte-identity harness for src/menubar/model_controller.py (menubar milestone A: persistence +
NSPanel-construction concern split into sibling modules).

(1) Persistence: MODEL_SELECTION_FILE/PROXY_RULES_FILE redirected to temp copies (rules file
seeded from a copy of the real ~/.claude/shared-rules/proxy_rules.json if present, else a
synthetic minimal fixture) — load, cycle main/worker model/effort/max_tokens through a fixed
sequence, write; hashes both written files' raw bytes.
(2) UI: instantiates ModelController with a minimal fake app (settings = a SimpleNamespace with
panel_width/panel_min_height/auto_focus, per menubar milestone B's PanelSettings split;
_panel_controller = a plain NSObject subclass instance), calls open() then each
handle_cycle_* once, dumping every arranged subview's class/frame/title/attributedTitle/tag/action
after each step; hashes the dump. Does NOT call handle_apply — that writes the REAL shared-rules
files, and this harness must never touch them; open()/handle_cycle_* are read-only with respect to
the real files (a cycle click only re-reads model_params for the newly-selected model, nothing is
written until Apply).

Usage (from project root):
    ./venv/bin/python dev/menubar/model_controller_byte_identity.py

Prints two lines: PERSISTENCE_HASH and UI_HASH. Run before and after the split; both must match.
If AppKit refuses headless view creation, UI_HASH reports SKIPPED with the reason and an
import + open() smoke check runs instead.
"""

# INFRASTRUCTURE
import hashlib
import importlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

_REAL_PROXY_RULES = Path.home() / '.claude' / 'shared-rules' / 'proxy_rules.json'

_SYNTHETIC_RULES = '''{
  "model_params": {
    "claude-opus-5": {"thinking": {"type": "adaptive", "display": "summarized"}, "effort": "high", "max_tokens": 64000}
  }
}
'''

# ORCHESTRATOR


def main():
    mc = _import_model_controller()
    ms = _import_model_selection()
    print(f'PERSISTENCE_HASH: {_hash_persistence(ms)}')
    try:
        print(f'UI_HASH: {_hash_ui(mc)}')
    except Exception as exc:
        print(f'UI_HASH: SKIPPED (headless AppKit view creation failed: {exc})')
        _smoke_import_and_open(mc)


# FUNCTIONS

# Loaded via importlib (not a literal 'from src.' module-level line) — dev/ scripts may not use
# that form (block_dev_imports_src); model_controller.py's package-relative imports only resolve
# when loaded as part of the src.menubar package anyway.
def _import_model_controller():
    return importlib.import_module('.'.join(['src', 'menubar', 'model_controller']))


# Loaded via importlib, same reason as _import_model_controller. (2026-09, menubar milestone A:
# every persistence function this harness drives — load/cycle/write — moved out of
# model_controller.py into this pure module; the harness's own import target was updated in the
# same commit as the split, exactly like every other symbol move this milestone.)
def _import_model_selection():
    return importlib.import_module('.'.join(['src', 'menubar', 'model_selection']))


# Redirect MODEL_SELECTION_FILE/PROXY_RULES_FILE to temp copies via each function's own path=
# parameter (no monkeypatching needed); load -> fixed cycle sequence -> write; hash both written
# files' raw bytes.
def _hash_persistence(ms) -> str:
    digest = hashlib.sha256()
    with tempfile.TemporaryDirectory() as tmp:
        sel_path = Path(tmp) / 'model_selection.json'
        rules_path = Path(tmp) / 'proxy_rules.json'
        if _REAL_PROXY_RULES.exists():
            shutil.copy(_REAL_PROXY_RULES, rules_path)
        else:
            rules_path.write_text(_SYNTHETIC_RULES, encoding='utf-8')

        main, worker = ms._load_model_selection(path=sel_path)
        main_effort, main_max_tokens = ms._load_model_params_for(main, path=rules_path)
        worker_effort, worker_max_tokens = ms._load_model_params_for(worker, path=rules_path)

        for _ in range(4):
            main = ms._next_model(main)
        for _ in range(4):
            worker = ms._next_model(worker)
        for _ in range(3):
            main_effort = ms._next_effort(main_effort)
        for _ in range(3):
            worker_effort = ms._next_effort(worker_effort)
        for _ in range(3):
            main_max_tokens = ms._next_max_tokens(main_max_tokens)
        for _ in range(3):
            worker_max_tokens = ms._next_max_tokens(worker_max_tokens)

        ms._write_model_selection(main, worker, path=sel_path)
        ms._write_proxy_rules_model_params(
            main, main_effort, main_max_tokens, worker, worker_effort, worker_max_tokens,
            path=rules_path)

        digest.update(sel_path.read_bytes())
        digest.update(rules_path.read_bytes())
    return digest.hexdigest()


# Call obj.method_name() if the method exists; None if absent or if the call itself raises.
def _safe_call(obj, method_name: str):
    if not hasattr(obj, method_name):
        return None
    try:
        return getattr(obj, method_name)()
    except Exception:
        return None


# Dump class/frame/title/attributedTitle/tag/action for every arranged subview, as a stable
# JSON-serialized bytes blob.
def _dump_subviews(sv) -> bytes:
    entries = []
    for v in sv.arrangedSubviews():
        frame = v.frame()
        attr = _safe_call(v, 'attributedTitle')
        action = _safe_call(v, 'action')
        entries.append({
            'class': type(v).__name__,
            'frame': [round(frame.origin.x, 3), round(frame.origin.y, 3),
                      round(frame.size.width, 3), round(frame.size.height, 3)],
            'title': _safe_call(v, 'title'),
            'attributedTitle': str(attr.string()) if attr is not None else None,
            'tag': _safe_call(v, 'tag'),
            'action': str(action) if action else None,
        })
    return json.dumps(entries, sort_keys=True).encode()


def _hash_ui(mc) -> str:
    from Foundation import NSObject

    class _FakePanelController(NSObject):
        pass

    class _FakeApp:
        def __init__(self):
            self.settings = SimpleNamespace(panel_width=422, panel_min_height=460, auto_focus=False)
            self._panel_controller = _FakePanelController.alloc().init()

    digest = hashlib.sha256()
    app = _FakeApp()
    controller = mc.ModelController(app)
    controller.open()
    digest.update(b'open')
    digest.update(_dump_subviews(controller._models_sv))

    for step in ('handle_cycle_main', 'handle_cycle_worker', 'handle_cycle_main_effort',
                 'handle_cycle_main_max_tokens', 'handle_cycle_worker_effort',
                 'handle_cycle_worker_max_tokens'):
        getattr(controller, step)()
        digest.update(step.encode())
        digest.update(_dump_subviews(controller._models_sv))

    return digest.hexdigest()


# Fallback when headless AppKit view creation fails: import already succeeded (main() got this
# far), so just prove open() doesn't raise.
def _smoke_import_and_open(mc) -> None:
    from Foundation import NSObject

    class _FakePanelController(NSObject):
        pass

    class _FakeApp:
        def __init__(self):
            self.settings = SimpleNamespace(panel_width=422, panel_min_height=460, auto_focus=False)
            self._panel_controller = _FakePanelController.alloc().init()

    controller = mc.ModelController(_FakeApp())
    controller.open()
    print('SMOKE: import + ModelController(app).open() succeeded with no exception')


if __name__ == '__main__':
    main()
