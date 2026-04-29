# INFRASTRUCTURE
import os
import time
from datetime import datetime
from typing import Optional

from ..constants import DIM, RESET, ZEBRA_BG_A, ZEBRA_BG_B, POLL_INTERVAL
from ..utils import truncate_visible
from .metadata_format import _format_metadata, _format_worker_metadata
from ..ram_audit import register_ram_dump

_meta_log_position: int = 0
_meta_entries: list = []
_meta_pending_by_rid: dict = {}  # persisted across polling cycles for latency_update merge

_worker_meta_log_position: int = 0
_worker_meta_entries: list = []
_worker_meta_last_name: Optional[str] = None
_worker_meta_pending_by_rid: dict = {}  # persisted across polling cycles for latency_update merge

# FUNCTIONS

# Render list of content lines with zebra BG + truncation; returns joined string
def _render_lines(lines: list) -> str:
    try:
        pane_width = os.get_terminal_size().columns
    except OSError:
        pane_width = 80
    result = []
    for i, line in enumerate(lines):
        zebra_bg = ZEBRA_BG_B if i % 2 else ZEBRA_BG_A
        result.append(f"{zebra_bg}{truncate_visible(line, pane_width)}\033[K{RESET}")
    return '\n'.join(result)

# ORCHESTRATOR

# Run metadata pane loop — reads proxy log directly and shows API config state
def run_metadata_loop() -> None:
    from ..core import monitor as _monitor
    from . import metadata_format as _mf
    from ..proxy_display import parse_proxy_log_isolated
    global _meta_log_position, _meta_entries, _meta_pending_by_rid

    def _ram_state():
        return [
            ('_meta_entries',         _meta_entries),
            ('_meta_pending_by_rid',  _meta_pending_by_rid),
            ('_meta_log_position',    _meta_log_position),
        ]
    register_ram_dump('metadata', _ram_state)

    session_start_ts = _monitor._get_session_start_ts()
    if session_start_ts is None:
        session_start_ts = datetime.utcnow().isoformat() + 'Z'
    current_main_session = _monitor._get_newest_main_session()
    last_output = None

    while True:
        newest = _monitor._get_newest_main_session()
        if newest != current_main_session and newest is not None:
            current_main_session = newest
            session_start_ts = _monitor._get_session_start_ts()
            if session_start_ts is None:
                session_start_ts = datetime.utcnow().isoformat() + 'Z'
            _meta_entries.clear()
            _meta_log_position = 0
            _meta_pending_by_rid.clear()
            _mf._prev_values = {}

        new_entries, _meta_log_position = parse_proxy_log_isolated(_monitor.active_project_filter, _meta_log_position, _meta_pending_by_rid)
        filtered = [e for e in new_entries if e.get('timestamp', '') >= session_start_ts]
        _meta_entries.extend(filtered)
        for _e in _meta_entries[:-1]:
            _e.pop('messages', None)

        if _meta_entries:
            lines = _format_metadata(_meta_entries[-1])
        else:
            lines = [f"{DIM}Waiting for proxy data...{RESET}"]

        output = _render_lines(lines)
        if output != last_output:
            print("\033[2J\033[3J\033[H", end='', flush=True)
            print(output)
            last_output = output

        time.sleep(POLL_INTERVAL)

# Run worker-metadata pane loop — reads selected worker's proxy log and shows API config state
def run_worker_metadata_loop() -> None:
    from ..core import monitor as _monitor
    from . import metadata_format as _mf
    from ..workers.worker_pane import get_selection_file_path
    from ..proxy_display import find_worker_proxy_log, _parse_log_file_isolated
    global _worker_meta_log_position, _worker_meta_entries, _worker_meta_last_name, _worker_meta_pending_by_rid

    def _ram_state():
        return [
            ('_worker_meta_entries',         _worker_meta_entries),
            ('_worker_meta_pending_by_rid',  _worker_meta_pending_by_rid),
            ('_worker_meta_log_position',    _worker_meta_log_position),
            ('_worker_meta_last_name',       str(_worker_meta_last_name)),
        ]
    register_ram_dump('worker_metadata', _ram_state)
    last_output = None

    while True:
        sel_path = get_selection_file_path(_monitor.active_project_filter)
        worker_name: Optional[str] = None
        try:
            with open(sel_path, 'r', encoding='utf-8') as f:
                worker_name = f.read().strip() or None
        except OSError:
            worker_name = None

        if worker_name != _worker_meta_last_name:
            _worker_meta_entries.clear()
            _worker_meta_log_position = 0
            _worker_meta_pending_by_rid.clear()
            _mf._worker_prev_values = {}
            _worker_meta_last_name = worker_name

        if worker_name:
            log_path = find_worker_proxy_log(worker_name, _monitor.active_project_filter)
            if log_path:
                new_entries, _worker_meta_log_position = _parse_log_file_isolated(log_path, _worker_meta_log_position, _worker_meta_pending_by_rid)
                _worker_meta_entries.extend(new_entries)
                for _e in _worker_meta_entries[:-1]:
                    _e.pop('messages', None)

        if not worker_name:
            lines = [f"{DIM}Select a worker in the Workers pane{RESET}"]
        elif not _worker_meta_entries:
            lines = [f"{DIM}Worker: {worker_name} — no proxy data yet{RESET}"]
        else:
            lines = _format_worker_metadata(_worker_meta_entries[-1])

        output = _render_lines(lines)
        if output != last_output:
            print("\033[2J\033[3J\033[H", end='', flush=True)
            print(output)
            last_output = output

        time.sleep(POLL_INTERVAL)
