# INFRASTRUCTURE
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

from ..constants import (
    KNOWN_PAYLOAD_KEYS, KNOWN_CONTENT_BLOCK_TYPES,
    KNOWN_TOOL_DEFINITION_KEYS, KNOWN_MESSAGE_ROLES,
)

# FUNCTIONS

# Estimate token count from char count (chars/3.5 heuristic, ~±15%)
def _chars_to_tokens(chars: int) -> int:
    return int(chars / 3.5)

# Derive proxy session_id from project path — matches claude_proxy_start.sh md5 hash logic
def _proxy_session_id_for_project(project_path: str) -> str:
    return hashlib.md5(project_path.encode()).hexdigest()[:8]

# Public wrapper — used by panes to build project-scoped worker log globs
def proxy_session_id_for_project(project_path: str) -> str:
    return _proxy_session_id_for_project(project_path)

# Populate content_tail on stored_msgs from corresponding raw_payload messages content
def _enrich_content_tails(stored_msgs: list, raw_msgs: list) -> None:
    for i, raw_msg in enumerate(raw_msgs):
        if i >= len(stored_msgs):
            break
        content = raw_msg.get('content', '')
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = ''.join(b.get('text', '') for b in content if isinstance(b, dict))
        else:
            text = ''
        stored_msgs[i]['content_tail'] = text

# Re-populate messages on a stripped entry by seeking to its _byte_offset in the log file
def _lazy_load_messages(entry: dict, log_path: Path) -> bool:
    offset = entry.get('_byte_offset')
    if offset is None or not log_path.exists():
        return False
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            f.seek(offset)
            raw_line = f.readline().strip()
        if not raw_line:
            return False
        raw_entry = json.loads(raw_line)
    except (OSError, json.JSONDecodeError):
        return False
    stored_msgs = raw_entry.get('messages', [])
    raw_payload = raw_entry.get('raw_payload') or {}
    raw_msgs = raw_payload.get('messages', [])
    _enrich_content_tails(stored_msgs, raw_msgs)
    entry['messages'] = stored_msgs
    return True

# Extract analysis fields from raw_payload; returns new dict with fields added, raw_payload/request_headers excluded
def _extract_raw_payload_fields(entry: dict) -> dict:
    new_entry = dict(entry)
    raw = new_entry.get('raw_payload', {})
    if raw:
        system = raw.get('system', [])
        new_entry['system_blocks'] = [
            {'idx': i, 'chars': len(b.get('text', '')), 'has_cc': bool(b.get('cache_control')), 'preview': b.get('text', '')}
            for i, b in enumerate(system) if isinstance(b, dict)
        ] if isinstance(system, list) else []
        new_entry['system_total_chars'] = sum(b['chars'] for b in new_entry['system_blocks'])

        if new_entry.get('original_system2_text'):
            for sb in new_entry['system_blocks']:
                if sb['idx'] == 2:
                    sb['original_text'] = new_entry['original_system2_text']
                    break

        if new_entry.get('stripped_sys3_original'):
            for sb in new_entry['system_blocks']:
                if sb['idx'] == 3:
                    sb['original_text'] = new_entry['stripped_sys3_original']
                    break

        tools = raw.get('tools', [])
        new_entry['tools_total_chars'] = sum(len(json.dumps(t)) for t in tools)
        new_entry['tools_count'] = len(tools)
        new_entry['tools_hash'] = hashlib.md5(json.dumps(sorted([t.get('name', '') for t in tools])).encode()).hexdigest()[:8]
        new_entry['tools_names'] = [t.get('name', '') for t in tools]
        _tool_originals = new_entry.get('stripped_tool_descs_originals', {})
        new_entry['tools_defs'] = [
            {
                'name': t.get('name', ''),
                'description': t.get('description', ''),
                'input_schema': t.get('input_schema', {}),
                'stripped_original': _tool_originals.get(t.get('name', '')),
            }
            for t in tools
        ]
        new_entry.setdefault('stripped_unused_tools_names', [])
        new_entry.setdefault('deferred_tools_names', [])

        new_entry['thinking_config'] = raw.get('thinking', {})
        new_entry['thinking_budget_tokens'] = raw.get('thinking', {}).get('budget_tokens')
        new_entry['output_config'] = raw.get('output_config', {})
        new_entry['effort_value'] = (raw.get('output_config') or {}).get('effort')
        new_entry['max_tokens'] = raw.get('max_tokens', 0)
        new_entry['temperature'] = raw.get('temperature', None)
        new_entry['top_p'] = raw.get('top_p', None)
        new_entry['top_k'] = raw.get('top_k', None)
        new_entry['tool_choice'] = raw.get('tool_choice', {})

        stored_msgs = new_entry.get('messages', [])
        new_entry['messages_total_chars'] = sum(m.get('chars', 0) for m in stored_msgs)

        msgs = raw.get('messages', [])
        schema_warnings = []
        unknown_keys = set(raw.keys()) - KNOWN_PAYLOAD_KEYS
        for k in sorted(unknown_keys):
            schema_warnings.append(f"unknown payload key: {k}")
        for msg in msgs:
            role = msg.get('role', '')
            if role and role not in KNOWN_MESSAGE_ROLES:
                schema_warnings.append(f"unknown message role: {role}")
            content = msg.get('content', [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        btype = block.get('type', '')
                        if btype and btype not in KNOWN_CONTENT_BLOCK_TYPES:
                            schema_warnings.append(f"unknown block type: {btype}")
        for tool in tools:
            if isinstance(tool, dict):
                unknown_tool_keys = set(tool.keys()) - KNOWN_TOOL_DEFINITION_KEYS
                for k in sorted(unknown_tool_keys):
                    schema_warnings.append(f"unknown tool key: {k}")
        new_entry['schema_warnings'] = schema_warnings

        enriched_msgs = [dict(m) for m in new_entry.get('messages', [])]
        if enriched_msgs and isinstance(msgs, list):
            _enrich_content_tails(enriched_msgs, msgs)
            new_entry['messages'] = enriched_msgs

        new_entry.pop('raw_payload', None)

    new_entry.pop('request_headers', None)
    return new_entry

# Read new proxy log entries from a specific log file, returning (entries, new_position).
# pending_by_rid: caller-owned dict {request_id -> entry} persisted across calls so that
# latency_update and sent_meta records can be merged even when the matching request entry
# was emitted in a previous polling cycle (cross-call boundary fix) or when two requests
# interleave within the same call (within-call fix).
def _parse_log_file(log_path: Path, last_position: int, pending_by_rid: Optional[dict] = None) -> tuple:
    if not log_path.exists():
        return [], last_position
    entries = []
    with open(log_path, "r", encoding="utf-8") as f:
        f.seek(last_position)
        while True:
            line_start = f.tell()
            raw_line = f.readline()
            if not raw_line:
                break
            line = raw_line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get('type') == 'sent_meta':
                    if pending_by_rid is not None:
                        rid = entry.get('request_id')
                        target = pending_by_rid.get(rid)
                        if target is not None:
                            target['tools_count'] = entry.get('sent_tools_count', target.get('tools_count'))
                            target['tools_hash'] = entry.get('sent_tools_hash', target.get('tools_hash'))
                            target['sent_cache_breakpoints'] = entry.get('sent_cache_breakpoints', {})
                    continue
                if entry.get('type') == 'latency_update':
                    if pending_by_rid is not None:
                        rid = entry.get('request_id')
                        target = pending_by_rid.get(rid)
                        if target is not None:
                            target['ttfb_ms'] = entry.get('ttfb_ms')
                            target['stream_duration_ms'] = entry.get('stream_duration_ms')
                            target['output_tokens_per_sec'] = entry.get('output_tokens_per_sec')
                            target['n_stalls'] = entry.get('n_stalls', 0)
                            target['max_stall_ms'] = entry.get('max_stall_ms')
                            target['total_stall_ms'] = entry.get('total_stall_ms')
                            pending_by_rid.pop(rid, None)  # response complete; release reference
                    continue
                entry['_byte_offset'] = line_start
                entry = _extract_raw_payload_fields(entry)
                entries.append(entry)
                if pending_by_rid is not None:
                    rid = entry.get('request_id')
                    if rid:
                        pending_by_rid[rid] = entry
            except json.JSONDecodeError:
                pass
        new_position = f.tell()
    return entries, new_position

# Read new proxy log entries for the monitored project, returning (entries, new_position)
def parse_proxy_log(project_filter: Optional[str], last_position: int, pending_by_rid: Optional[dict] = None) -> tuple:
    root = os.environ.get("MONITOR_CC_ROOT", "")
    if not root:
        root = str(Path(__file__).parent.parent.parent)
    if not project_filter:
        return [], last_position
    session_id = _proxy_session_id_for_project(project_filter)
    marker_file = Path(root) / "src" / "logs" / f".proxy_session_{session_id}"
    log_id = session_id
    if marker_file.exists():
        lines = marker_file.read_text(encoding="utf-8").splitlines()
        if len(lines) >= 2 and lines[1].strip():
            log_id = lines[1].strip()
    log_file = Path(root) / "src" / "logs" / f"api_requests_{log_id}.jsonl"
    entries, new_pos = _parse_log_file(log_file, last_position, pending_by_rid)
    for entry in entries:
        entry['_source_file'] = log_file.name
    return entries, new_pos

# Find the most recent worker proxy log for the given worker name
def find_worker_proxy_log(worker_name: str, project_filter: Optional[str] = None) -> Optional[Path]:
    root = os.environ.get("MONITOR_CC_ROOT", "")
    if not root:
        root = str(Path(__file__).parent.parent.parent)
    logs_dir = Path(root) / "src" / "logs"
    if not logs_dir.exists():
        return None
    # Try prefixed pattern first (current naming: api_requests_worker_{hash}_{name}_*.jsonl)
    if project_filter:
        project_session_id = _proxy_session_id_for_project(project_filter)
        matches = list(logs_dir.glob(f"api_requests_worker_{project_session_id}_{worker_name}_*.jsonl"))
        if matches:
            return max(matches, key=lambda f: f.stat().st_mtime)
    # Fall back to unprefixed pattern (older naming or no project_filter provided)
    matches = list(logs_dir.glob(f"api_requests_worker_{worker_name}_*.jsonl"))
    if not matches:
        return None
    return max(matches, key=lambda f: f.stat().st_mtime)

# Return epoch float of proxy session start (marker file mtime); falls back silently to time.time()
def get_proxy_session_start_ts(project_filter: str) -> float:
    root = os.environ.get("MONITOR_CC_ROOT", "")
    if not root:
        root = str(Path(__file__).parent.parent.parent)
    session_id = _proxy_session_id_for_project(project_filter)
    marker_file = Path(root) / "src" / "logs" / f".proxy_session_{session_id}"
    if marker_file.exists():
        try:
            mtime = marker_file.stat().st_mtime
            if time.time() - mtime < 86400:  # stale guard: >24h → fallback
                return mtime
        except OSError:
            pass
    return time.time()

# Locate current proxy JSONL via marker file; returns Path or None
def find_proxy_log_path(project_filter: Optional[str]) -> Optional[Path]:
    if not project_filter:
        return None
    root = os.environ.get("MONITOR_CC_ROOT", "")
    if not root:
        root = str(Path(__file__).parent.parent.parent)
    session_id = _proxy_session_id_for_project(project_filter)
    marker_file = Path(root) / "src" / "logs" / f".proxy_session_{session_id}"
    log_id = session_id
    if marker_file.exists():
        try:
            lines = marker_file.read_text(encoding="utf-8").splitlines()
            if len(lines) >= 2 and lines[1].strip():
                log_id = lines[1].strip()
        except OSError:
            pass
    return Path(root) / "src" / "logs" / f"api_requests_{log_id}.jsonl"

# Scan worker proxy logs for active project (project_session_id scopes the glob); all logs if empty.
# tail_bytes: if >0, first-time-seen logs seek to (fsize - tail_bytes) to bound initial alloc.
# min_mtime: if >0, logs with mtime < min_mtime are skipped entirely (old sessions).
def scan_worker_logs(last_positions: dict, project_session_id: str = '',
                     tail_bytes: int = 0, min_mtime: float = 0) -> tuple:
    root = os.environ.get("MONITOR_CC_ROOT", "")
    if not root:
        root = str(Path(__file__).parent.parent.parent)
    logs_dir = Path(root) / "src" / "logs"
    if not logs_dir.exists():
        return [], last_positions
    all_entries: list = []
    updated_positions = dict(last_positions)
    pattern = f"api_requests_worker_{project_session_id}_*.jsonl" if project_session_id else "api_requests_worker_*.jsonl"
    for log_path in logs_dir.glob(pattern):
        try:
            stat = log_path.stat()
        except OSError:
            continue
        if min_mtime > 0 and stat.st_mtime < min_mtime:
            continue
        stem = log_path.stem  # api_requests_worker_[{hash}_]{name}_{ts}
        remaining = stem.replace('api_requests_worker_', '')
        # Strip project_session_id prefix if present (8-char hex + '_')
        if project_session_id and remaining.startswith(project_session_id + '_'):
            remaining = remaining[len(project_session_id) + 1:]
        worker_name = remaining.rsplit('_', 1)[0]
        stored_pos = last_positions.get(str(log_path))
        if stored_pos is None:
            # First time seeing this log — apply tail-bytes to bound initial allocation
            if tail_bytes > 0 and stat.st_size > tail_bytes:
                pos = stat.st_size - tail_bytes
            else:
                pos = 0
        else:
            pos = stored_pos
        entries, new_pos = _parse_log_file(log_path, pos)
        for entry in entries:
            entry['_worker_name'] = worker_name
            entry['_source_file'] = log_path.name
        all_entries.extend(entries)
        updated_positions[str(log_path)] = new_pos
    return all_entries, updated_positions

# Top-level subprocess worker (must be importable by name for multiprocessing 'spawn').
# Parses log file in a child process, drops messages pre-IPC, returns entries via Queue.
# SUBPROCESS_PARSE_FAIL=1 / SUBPROCESS_PARSE_SLOW=1 env vars activate test hooks.
def _subprocess_worker(log_path_str: str, start_pos: int, root_dir: str, q) -> None:
    import sys
    if root_dir and root_dir not in sys.path:
        sys.path.insert(0, root_dir)
    try:
        if os.environ.get('SUBPROCESS_PARSE_FAIL') == '1':
            raise RuntimeError('forced failure for testing')
        if os.environ.get('SUBPROCESS_PARSE_SLOW') == '1':
            time.sleep(10)
        pending: dict = {}
        entries, new_pos = _parse_log_file(Path(log_path_str), start_pos, pending)
        for e in entries:
            e.pop('messages', None)
        pending_rids = list(pending.keys())
        q.put(('ok', entries, new_pos, pending_rids))
    except Exception as exc:
        q.put(('error', str(exc)))

# _parse_log_file variant that offloads initial parse (last_position==0) to a subprocess.
# Subprocess peak allocation (~3 GB for large logs) is discarded when child exits;
# parent receives only scalar entry fields (~10–20 MB).  messages are stripped pre-IPC;
# lazy-reload via _byte_offset handles on-demand reload when user expands an entry.
# Falls back to in-parent parse on subprocess failure, timeout, or IPC error.
# Test hooks: SUBPROCESS_PARSE_TIMEOUT env (override 60s default), SUBPROCESS_PARSE_FAIL=1,
# SUBPROCESS_PARSE_SLOW=1 (child sleeps 10s to exercise timeout path).
def _parse_log_file_isolated(log_path: Path, last_position: int, pending_by_rid: Optional[dict] = None) -> tuple:
    if last_position != 0:
        return _parse_log_file(log_path, last_position, pending_by_rid)
    import multiprocessing as _mp
    import queue as _queue
    root = os.environ.get('MONITOR_CC_ROOT', '') or str(Path(__file__).parent.parent.parent)
    timeout = int(os.environ.get('SUBPROCESS_PARSE_TIMEOUT', '60'))
    ctx = _mp.get_context('spawn')
    q = ctx.Queue()
    p = ctx.Process(target=_subprocess_worker, args=(str(log_path), 0, root, q), daemon=True)
    p.start()
    result = None
    try:
        result = q.get(timeout=timeout)
    except _queue.Empty:
        logging.warning('subprocess parse timed out after %ss — falling back to in-parent', timeout)
    except Exception as exc:
        logging.warning('subprocess parse IPC error: %s — falling back to in-parent', exc)
    finally:
        if p.is_alive():
            p.terminate()
        p.join(timeout=5)
    if result is None or result[0] == 'error':
        if result is not None:
            logging.warning('subprocess parse worker error: %s — falling back to in-parent', result[1])
        return _parse_log_file(log_path, last_position, pending_by_rid)
    _, entries, new_pos, pending_rids = result
    if pending_by_rid is not None and pending_rids:
        pending_set = set(pending_rids)
        for e in entries:
            rid = e.get('request_id')
            if rid and rid in pending_set:
                pending_by_rid[rid] = e
    return entries, new_pos

# parse_proxy_log variant that uses _parse_log_file_isolated for the initial parse.
# Marker-file lookup identical to parse_proxy_log; subprocess decision delegated to
# _parse_log_file_isolated based on last_position.
def parse_proxy_log_isolated(project_filter: Optional[str], last_position: int, pending_by_rid: Optional[dict] = None) -> tuple:
    root = os.environ.get('MONITOR_CC_ROOT', '') or str(Path(__file__).parent.parent.parent)
    if not project_filter:
        return [], last_position
    session_id = _proxy_session_id_for_project(project_filter)
    marker_file = Path(root) / 'src' / 'logs' / f'.proxy_session_{session_id}'
    log_id = session_id
    if marker_file.exists():
        lines = marker_file.read_text(encoding='utf-8').splitlines()
        if len(lines) >= 2 and lines[1].strip():
            log_id = lines[1].strip()
    log_file = Path(root) / 'src' / 'logs' / f'api_requests_{log_id}.jsonl'
    return _parse_log_file_isolated(log_file, last_position, pending_by_rid)
