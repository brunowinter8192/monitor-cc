# INFRASTRUCTURE
from pathlib import Path
from typing import Optional

from src.pane_error_log import log_pane_error
from src.jsonl.jsonl_reader import JsonlReader
from src.proxy_display.forwarded_parser import _monitor_root

# FUNCTIONS

def read_response_log(path: Optional[Path], last_pos: int) -> tuple:
    if path is None or not path.exists():
        return {}, last_pos
    rid_map: dict = {}
    reader = JsonlReader(path, last_pos)
    try:
        for entry in reader:
            rid = entry.get('request_id', '')
            if rid:
                rid_map[rid] = entry
        return rid_map, reader.position
    except OSError:
        log_pane_error('side_logs')
        return {}, last_pos

def scan_worker_errors_logs(last_positions: dict, project_session_id: str, min_mtime: float) -> tuple:
    dual_dir = _monitor_root() / 'src' / 'logs' / 'dual_log'
    if not dual_dir.exists():
        return [], dict(last_positions)
    new_positions = dict(last_positions)
    records: list = []
    pattern = f'api_requests_worker_{project_session_id}_*_errors.jsonl'
    for fpath in sorted(dual_dir.glob(pattern)):
        try:
            if fpath.stat().st_mtime < min_mtime:
                continue
        except OSError:
            log_pane_error('side_logs')
            continue
        last_pos = last_positions.get(str(fpath), 0)
        reader = JsonlReader(fpath, last_pos)
        try:
            for rec in reader:
                stem = fpath.stem
                remaining = stem.replace('api_requests_worker_', '')
                if remaining.endswith('_errors'):
                    remaining = remaining[:-len('_errors')]
                if remaining.startswith(project_session_id + '_'):
                    remaining = remaining[len(project_session_id) + 1:]
                rec['_worker_name_from_file'] = remaining.rsplit('_', 1)[0]
                records.append(rec)
            new_positions[str(fpath)] = reader.position
        except OSError:
            log_pane_error('side_logs')
            continue
    return records, new_positions
