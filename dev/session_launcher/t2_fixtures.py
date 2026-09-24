# INFRASTRUCTURE
import importlib
from types import SimpleNamespace

_EXPECTED_PROJECTS = [
    '/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/gh-cli',
    '/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/reddit-cli',
    '/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/websearch',
    '/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/rag-cli',
    '/Users/brunowinter2000/Documents/ai/Meta/iterative-dev',
    '/Users/brunowinter2000/Documents/ai/trading',
    '/Users/brunowinter2000/Documents/ai/trading_ai',
    '/Users/brunowinter2000/Documents/ai/monitor-cc',
    '/Users/brunowinter2000/Documents/general',
    '/Users/brunowinter2000/Documents/wise2627',
]
_ROOT_DIR = '/Users/brunowinter2000/Documents/ai/monitor-cc'

# FUNCTIONS

def _imp(name: str):
    return importlib.import_module(f'src.menubar.{name}')

def _session(name: str, desktop, worker: bool = False):
    S = _imp('discover').SessionInfo
    return S(name=name, status='idle', has_bg=False, encoded_dir=f'-{name}', project_name=name,
             is_worker=worker, cwd='' if worker else f'/tmp/{name}', session_id=f'sid-{name}',
             tmux_session_name='', desktop_no=desktop)

class _FakeSessions:
    def __init__(self, items):
        self.items = items

    def refresh(self):
        return self.items

    @property
    def bg_by_project(self):
        return {}

class _FakeApp:
    def __init__(self, sessions):
        self.settings = SimpleNamespace(panel_width=380, panel_min_height=460)
        self._panel_controller = None
        self.sessions = _FakeSessions(sessions)

def _title(btn) -> str:
    return str(btn.attributedTitle().string())

def _header_text(strip) -> str:
    parts = []
    for v in strip.subviews()[0].subviews():
        text = v.attributedTitle().string() if hasattr(v, 'attributedTitle') else v.attributedStringValue().string()
        parts.append((v.frame().origin.x, str(text)))
    return ''.join(t for _, t in sorted(parts))

class _SyncThread:
    def __init__(self, target, args=(), daemon=None):
        self._t, self._a = target, args

    def start(self):
        self._t(*self._a)
