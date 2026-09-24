# INFRASTRUCTURE
import os
import traceback
from datetime import datetime
from pathlib import Path

from src.monitor_root import resolve_monitor_cc_root

PROXY_ERROR_LOG_NAME = "proxy_error.log"
PROXY_ERROR_LOG_MAX_BYTES = 2_000_000
PROXY_ERROR_LOG_KEEP_BYTES = 500_000

_last_error_by_source: dict = {}

# ORCHESTRATOR

def log_proxy_error(source: str, error) -> None:
    entry = _format_entry(source, error)
    _write_entry_best_effort(entry)

# FUNCTIONS

def log_proxy_error_on_change(source: str, error) -> None:
    text = _error_text(error)
    if _last_error_by_source.get(source) == text:
        return
    _last_error_by_source[source] = text
    log_proxy_error(source, error)

def clear_proxy_error(source: str) -> None:
    _last_error_by_source.pop(source, None)

def proxy_monitor_root() -> Path:
    return resolve_monitor_cc_root(_report_root)

def _report_root(root: Path, source: str) -> None:
    _append(_log_path(root), f"[{datetime.now().isoformat()}] [monitor_root] source={source} root={root}\n")

def _error_text(error) -> str:
    if isinstance(error, BaseException):
        return f"{type(error).__name__}: {error}"
    return str(error)

def _format_entry(source: str, error) -> str:
    header = f"[{datetime.now().isoformat()}] [{source}] {_error_text(error)}\n"
    if isinstance(error, BaseException):
        return header + "".join(traceback.format_exception(type(error), error, error.__traceback__))
    return header

def _write_entry_best_effort(entry: str) -> None:
    try:
        _append(_log_path(proxy_monitor_root()), entry)
    except Exception:
        pass

def _log_path(root: Path) -> Path:
    return root / "src" / "logs" / PROXY_ERROR_LOG_NAME

def _append(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _cap_log_size(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write(text)

def _cap_log_size(path: Path) -> None:
    if not path.exists() or path.stat().st_size <= PROXY_ERROR_LOG_MAX_BYTES:
        return
    with open(path, "rb") as f:
        f.seek(-PROXY_ERROR_LOG_KEEP_BYTES, os.SEEK_END)
        tail = f.read()
    with open(path, "wb") as f:
        f.write(tail)
