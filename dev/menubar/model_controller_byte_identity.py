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
from dev.refactoring.live_log_isolation import isolate_home

_REAL_PROXY_RULES = Path.home() / '.claude' / 'shared-rules' / 'proxy_rules.json'
_HOME_SANDBOX = isolate_home("model_controller_byte_id_", (".claude/shared-rules/model_selection.json", ".claude/shared-rules/proxy_rules.json"))

from Foundation import NSObject

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
    print_persistence_hash(ms)
    guarded_print(mc)


# FUNCTIONS

def _import_model_controller():
    return importlib.import_module('.'.join(['src', 'menubar', 'model_controller']))


def _import_model_selection():
    return importlib.import_module('.'.join(['src', 'menubar', 'model_selection']))


def print_persistence_hash(ms):
    print(f'PERSISTENCE_HASH: {_hash_persistence(ms)}')


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
        main_effort, main_max_tokens, main_thinking = ms._load_model_params_for(main, path=rules_path)
        worker_effort, worker_max_tokens, worker_thinking = ms._load_model_params_for(worker, path=rules_path)

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
        for _ in range(1):
            main_thinking = ms._next_thinking(main_thinking)
        for _ in range(2):
            worker_thinking = ms._next_thinking(worker_thinking)

        ms._write_model_selection(main, worker, path=sel_path)
        ms._write_proxy_rules_model_params(
            main, main_effort, main_max_tokens, main_thinking,
            worker, worker_effort, worker_max_tokens, worker_thinking,
            path=rules_path)

        digest.update(sel_path.read_bytes())
        digest.update(rules_path.read_bytes())
    return digest.hexdigest()


def guarded_print(mc):
    try:
        print(f'UI_HASH: {_hash_ui(mc)}')
    except Exception as exc:
        print(f'UI_HASH: SKIPPED (headless AppKit view creation failed: {exc})')
        _smoke_import_and_open(mc)


def _hash_ui(mc) -> str:

    class _FakePanelController(NSObject):
        pass

    class _FakeApp:
        def __init__(self):
            self.settings = SimpleNamespace(panel_width=422, panel_min_height=460)
            self._panel_controller = _FakePanelController.alloc().init()

    digest = hashlib.sha256()
    app = _FakeApp()
    controller = mc.ModelController(app)
    controller.open()
    digest.update(b'open')
    digest.update(_dump_subviews(controller._models_sv))

    for step in ('handle_cycle_main', 'handle_cycle_worker', 'handle_cycle_main_effort',
                 'handle_cycle_main_max_tokens', 'handle_cycle_worker_effort',
                 'handle_cycle_worker_max_tokens', 'handle_cycle_main_thinking',
                 'handle_cycle_worker_thinking'):
        getattr(controller, step)()
        digest.update(step.encode())
        digest.update(_dump_subviews(controller._models_sv))

    return digest.hexdigest()


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


def _safe_call(obj, method_name: str):
    if not hasattr(obj, method_name):
        return None
    try:
        return getattr(obj, method_name)()
    except Exception:
        return None


def _smoke_import_and_open(mc) -> None:

    class _FakePanelController(NSObject):
        pass

    class _FakeApp:
        def __init__(self):
            self.settings = SimpleNamespace(panel_width=422, panel_min_height=460)
            self._panel_controller = _FakePanelController.alloc().init()

    controller = mc.ModelController(_FakeApp())
    controller.open()
    print('SMOKE: import + ModelController(app).open() succeeded with no exception')


if __name__ == '__main__':
    main()
