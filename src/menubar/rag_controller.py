# INFRASTRUCTURE
import errno
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from AppKit import NSAttributedString, NSFontAttributeName

from .menubar_log import log_menubar_change
from .panel import (_TOP_BAR_H, _LABEL_H, _MENLO,
                    _make_tab_nspanel, _resize_panel_keep_top,
                    _make_line_separator, _make_header_label)

_RAG_LOCK    = Path.home() / '.rag-locks' / 'rag.lock'
_NO_INDEXING = 'no indexing currently running'

# FUNCTIONS

def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError as e:
        return e.errno != errno.ESRCH

def _read_rag_status(lock_path: Path = _RAG_LOCK) -> str:
    try:
        status = _rag_status_from_lock(lock_path)
    except FileNotFoundError:
        status = _NO_INDEXING
    except Exception as exc:
        log_menubar_change('rag', 'rag_status', f'status read failed path={lock_path} err={exc!r}')
        return _NO_INDEXING
    log_menubar_change('rag', 'rag_status', None)
    return status

def _rag_status_from_lock(lock_path: Path) -> str:
    data       = json.loads(lock_path.read_text())
    pid        = data.get('pid')
    if pid is None or not _pid_alive(pid):
        return _NO_INDEXING
    command    = data.get('command', '')
    kind       = data.get('kind')
    if kind is not None:
        if kind != 'index':
            return _NO_INDEXING
    else:
        if not command.startswith('index'):
            return _NO_INDEXING
    args         = data.get('args') or {}
    progress     = data.get('progress') or {}
    collection   = (args.get('collection')
                    or progress.get('collection')
                    or Path(args.get('input', '')).name
                    or 'unknown')
    done         = progress.get('done', 0)
    total        = progress.get('total', 0)
    chunks_done  = progress.get('chunks_done')
    chunks_total = progress.get('chunks_total')
    elapsed      = _format_elapsed(data.get('started_at', ''))
    if chunks_done is not None and chunks_total:
        return (f'{collection} \u00b7 {done + 1}/{total} docs'
                f' \u00b7 {chunks_done}/{chunks_total} chunks'
                f' \u00b7 {elapsed}')
    elif total > 0:
        return f'{collection} \u00b7 {done}/{total} docs \u00b7 {elapsed}'
    else:
        return f'{collection} \u00b7 {elapsed}'

def _format_elapsed(started_at: str) -> str:
    try:
        start = datetime.fromisoformat(started_at)
        now   = datetime.now(timezone.utc)
        secs  = max(0, int((now - start).total_seconds()))
    except Exception as exc:
        log_menubar_change('rag', 'rag_elapsed', f'elapsed parse failed started_at={started_at!r} err={exc!r}')
        return '?'
    log_menubar_change('rag', 'rag_elapsed', None)
    mins, s = divmod(secs, 60)
    if mins > 0:
        return f'{mins}m{s:02d}s'
    return f'{s}s'

class RagController:
    def __init__(self, app) -> None:
        self.app = app
        self._rag_open: bool = False
        self._rag_panel, self._rag_sv, self._rag_header = _make_tab_nspanel('RAG')
        self._rag_status_label = None

    def tick(self, sessions) -> None:
        if self._rag_status_label is None:
            return
        status = _read_rag_status()
        self._rag_status_label.setAttributedStringValue_(
            NSAttributedString.alloc().initWithString_attributes_(
                status, {NSFontAttributeName: _MENLO()}))

    def rebuild(self) -> None:
        app = self.app
        for sv in list(self._rag_sv.arrangedSubviews()):
            self._rag_sv.removeView_(sv)
            sv.removeFromSuperview()
        pw = app.settings.panel_width
        required_h = _TOP_BAR_H + _LABEL_H + _LABEL_H
        _resize_panel_keep_top(self._rag_panel, app.settings.panel_width, max(app.settings.panel_min_height, required_h))
        self._rag_sv.addView_inGravity_(_make_line_separator(pw), 1)
        status = _read_rag_status()
        label  = _make_header_label(status, pw)
        self._rag_sv.addView_inGravity_(label, 1)
        self._rag_status_label = label
