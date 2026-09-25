# INFRASTRUCTURE
import os
from pathlib import Path
from typing import Callable

_reported: set = set()

# ORCHESTRATOR

def resolve_monitor_cc_root(report: Callable[[Path, str], None], env_var: str = "MONITOR_CC_ROOT") -> Path:
    root = _pick_root(env_var)
    _require_directory(root, env_var)
    _report_once(report, env_var, root)
    return root

# FUNCTIONS

def _pick_root(env_var: str) -> Path:
    if root_source(env_var) == "env":
        return Path(os.environ[env_var])
    return Path(__file__).resolve().parent.parent

def root_source(env_var: str = "MONITOR_CC_ROOT") -> str:
    return "env" if os.environ.get(env_var) else "computed"

def _require_directory(root: Path, env_var: str) -> None:
    if not root.is_dir():
        raise FileNotFoundError(f"{env_var} resolved via {root_source(env_var)} to a missing directory: {root}")

def _report_once(report: Callable[[Path, str], None], env_var: str, root: Path) -> None:
    source = root_source(env_var)
    key = (env_var, str(root), source)
    if key in _reported:
        return
    _reported.add(key)
    report(root, source)
