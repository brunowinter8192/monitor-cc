# INFRASTRUCTURE
import importlib
import os
import sys
from pathlib import Path

from p1_shared import _PROBE_LOG_PATH

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))
os.environ.setdefault('MONITOR_CC_ROOT', str(WORKTREE_ROOT))

_ROOT_PKG = 'src'  # built at runtime, not a literal `import src...` — these modules need
                    # package-qualified loading for their `from ..constants import ...` imports

pel = importlib.import_module(f'{_ROOT_PKG}.pane_error_log')
mod_worker_tokens = importlib.import_module(f'{_ROOT_PKG}.workers.worker_tokens_pane')
mod_proxy = importlib.import_module(f'{_ROOT_PKG}.proxy_display.pane')
mod_worker_proxy = importlib.import_module(f'{_ROOT_PKG}.proxy_display.worker_proxy_pane')
mod_tokens = importlib.import_module(f'{_ROOT_PKG}.panes.token_pane')
mod_warnings = importlib.import_module(f'{_ROOT_PKG}.panes.warnings_pane')
mod_gpu = importlib.import_module(f'{_ROOT_PKG}.gpu_pane.pane')
mod_news = importlib.import_module(f'{_ROOT_PKG}.news_pane.pane')
mod_news_log = importlib.import_module(f'{_ROOT_PKG}.news_pane.log_pane')

pel.PANE_ERROR_LOG_PATH = _PROBE_LOG_PATH  # redirect the shared sink so pane tests below never
                                            # touch the real /tmp/monitor_cc_error.log
