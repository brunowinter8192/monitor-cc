# INFRASTRUCTURE
import contextlib
import hashlib
import importlib
import io
import os
import sys
import tempfile
from pathlib import Path

_DEFAULT_ROOT = Path(__file__).resolve().parents[2]

# FUNCTIONS

def root() -> Path:
    return Path(os.environ.get('P5_ROOT', str(_DEFAULT_ROOT)))

def load(module: str):
    r = str(root())
    if r not in sys.path:
        sys.path.insert(0, r)
    return importlib.import_module('.'.join(['src', 'menubar', module]))

def tmpdir() -> Path:
    return Path(tempfile.mkdtemp(prefix='p5_menubar_'))

def capture_stderr(fn):
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        result = fn()
    return result, buf.getvalue()

def digest(obj) -> str:
    return hashlib.sha256(repr(obj).encode()).hexdigest()[:16]

def check(name: str, ok: bool, detail: str = '') -> None:
    print(f'{name}: {"PASS" if ok else "FAIL"} {detail}'.rstrip())
    if not ok:
        sys.exit(1)

def point_log(tmp: Path):
    mlog = load('menubar_log')
    mlog.MENUBAR_LOG = tmp / 'menubar.log'
    if hasattr(mlog, '_last_by_key'):
        mlog._last_by_key.clear()
    return mlog

def log_text(mlog) -> str:
    return mlog.MENUBAR_LOG.read_text() if mlog.MENUBAR_LOG.exists() else ''
