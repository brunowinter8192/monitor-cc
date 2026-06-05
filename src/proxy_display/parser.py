# INFRASTRUCTURE
import hashlib
import json
import logging
import os
import time
from collections import deque
from pathlib import Path
from typing import Optional

from ..constants import (
    KNOWN_PAYLOAD_KEYS, KNOWN_CONTENT_BLOCK_TYPES,
    KNOWN_TOOL_DEFINITION_KEYS, KNOWN_MESSAGE_ROLES,
    PROXY_MESSAGES_KEEP_LAST,
)
from ..proxy.message_summary import _summarize_message
from ..proxy.logging import _compute_diff

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

# Infer model family from model name string (matches addon.py logic)
def _infer_model_family(model: str) -> str:
    m = model.lower()
    if 'haiku' in m:
        return 'haiku'
    if 'sonnet' in m:
        return 'sonnet'
    return 'opus'

# Derive stripped/injected dual-log paths from the resolved main log path
def _find_dual_log_paths(main_log_path: Optional[Path]) -> tuple:
    if main_log_path is None:
        return None, None
    dual_dir = main_log_path.parent / 'dual_log'
    stem = main_log_path.stem  # e.g. api_requests_<log_id>
    return (
        dual_dir / f'{stem}_stripped.jsonl',
        dual_dir / f'{stem}_injected.jsonl',
    )

# Read new entries from one dual-log file (stripped or injected), accumulate per model_family.
# acc_by_family: {family -> {'system': {}, 'tools': {}, 'messages': {}, 'fields': {}}}
# Mutates acc_by_family IN-PLACE so all proxy_entries holding a reference see updates
# automatically. is_first -> .clear() + .update() on existing section dicts (preserves refs).
# Returns new file position; silently ignores missing/unreadable file.
def accumulate_dual_log(path: Optional[Path], last_pos: int, acc_by_family: dict) -> int:
    if path is None or not path.exists():
        return last_pos
    try:
        with open(path, 'r', encoding='utf-8') as f:
            f.seek(last_pos)
            while True:
                raw_line = f.readline()
                if not raw_line:
                    break
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                family = _infer_model_family(entry.get('model', ''))
                acc = acc_by_family.setdefault(
                    family,
                    {'system': {}, 'tools': {}, 'messages': {}, 'fields': {}, '_fns_by_flow_id': {}}
                )
                if entry.get('is_first', False):
                    for section in ('system', 'tools', 'messages', 'fields'):
                        acc[section].clear()
                    acc.setdefault('_fns_by_flow_id', {}).clear()
                acc['system'].update(entry.get('system_delta') or {})
                for name, val in (entry.get('tools_delta') or {}).items():
                    acc['tools'][name] = val
                for midx, blks in (entry.get('messages_delta') or {}).items():
                    if midx not in acc['messages']:
                        acc['messages'][midx] = {}
                    acc['messages'][midx].update(blks)
                acc['fields'].update(entry.get('fields_delta') or {})
                fid = entry.get('flow_id', '')
                acc.setdefault('_fns_by_flow_id', {})[fid] = set((entry.get('fn_map') or {}).values())
            return f.tell()
    except OSError:
        return last_pos

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

# Build a message summary dict with content_tail enrichment from the raw message object.
# Wraps _summarize_message (from proxy/message_summary.py) and adds content_tail for
# full-text display in the proxy pane expand view.
def _summarize_fwd_message(msg: dict) -> dict:
    s = _summarize_message(msg)
    content = msg.get('content', '')
    if isinstance(content, str):
        s['content_tail'] = content
    elif isinstance(content, list):
        s['content_tail'] = ''.join(b.get('text', '') for b in content if isinstance(b, dict))
    else:
        s['content_tail'] = ''
    return s

# Expand {idx_str: elem} delta dict into a list of exactly count elements (None-padded gaps)
def _dict_to_list_fwd(delta_dict: dict, count: int) -> list:
    lst = [None] * count
    for idx_str, elem in delta_dict.items():
        i = int(idx_str)
        if i < count:
            lst[i] = elem
    return lst

# Shallow-copy prev_list, apply delta dict overwrites, resize to count
def _apply_delta_to_list(prev_list: list, delta_dict: dict, count: int) -> list:
    lst = list(prev_list)
    for idx_str, elem in delta_dict.items():
        i = int(idx_str)
        while len(lst) <= i:
            lst.append(None)
        lst[i] = elem
    if len(lst) > count:
        lst = lst[:count]
    elif len(lst) < count:
        lst.extend([None] * (count - len(lst)))
    return lst

# Build a proxy-display entry dict from a forwarded_delta header + reconstructed section data.
# message_summaries: list of summary dicts (for messages_total_chars; messages key NOT set here —
# assigned from the deque window after parse completes).
def _extract_forwarded_fields(fwd_entry: dict, system: list, tools: list, message_summaries: list) -> dict:
    entry: dict = {}
    entry['timestamp'] = fwd_entry.get('timestamp', '')
    entry['request_id'] = fwd_entry.get('request_id', '')
    entry['model'] = fwd_entry.get('model', '')
    entry['max_tokens'] = fwd_entry.get('max_tokens') or 0
    entry['output_config'] = fwd_entry.get('output_config') or {}
    entry['effort_value'] = (fwd_entry.get('output_config') or {}).get('effort')
    entry['is_first'] = fwd_entry.get('is_first', False)
    entry['message_count'] = fwd_entry.get('counts', {}).get('messages', 0)
    entry['messages_total_chars'] = sum(s.get('chars', 0) for s in message_summaries)

    sys_list = system if isinstance(system, list) else []
    entry['system_blocks'] = [
        {
            'idx': i,
            'chars': len(b.get('text', '')),
            'has_cc': bool(b.get('cache_control')),
            'preview': b.get('text', ''),
        }
        for i, b in enumerate(sys_list) if isinstance(b, dict)
    ]
    entry['system_total_chars'] = sum(b['chars'] for b in entry['system_blocks'])

    tools_list = [t for t in (tools if isinstance(tools, list) else []) if isinstance(t, dict)]
    entry['tools_total_chars'] = sum(len(json.dumps(t)) for t in tools_list)
    entry['tools_count'] = len(tools_list)
    entry['tools_hash'] = hashlib.md5(
        json.dumps(sorted(t.get('name', '') for t in tools_list)).encode()
    ).hexdigest()[:8]
    entry['tools_names'] = [t.get('name', '') for t in tools_list]
    entry['tools_defs'] = [
        {
            'name': t.get('name', ''),
            'description': t.get('description', ''),
            'input_schema': t.get('input_schema', {}),
            'stripped_original': None,
        }
        for t in tools_list
    ]

    # Placeholders for main-log-only fields; use_dual overlay path handles display when
    # _stripped_spans/_injected_spans are attached by the pane's accumulate_dual_log calls.
    entry['modifications'] = []
    entry['stripped_unused_tools_names'] = []
    entry['deferred_tools_names'] = []
    entry['stripped_msg_indices'] = []
    entry['schema_warnings'] = []
    entry['cache_breakpoints'] = []   # always empty; BP:N removed from display
    entry['messages'] = None           # assigned by caller from deque window

    return entry

# Parse new forwarded_delta entries from fwd_path starting at last_pos.
# acc_by_family: persisted across calls {family: {system: [...], tools: [...], messages: [summaries]}}.
#   is_first resets the family state; subsequent entries apply deltas onto the accumulated lists.
#   Unchanged message dicts are SHARED across consecutive summary lists (shallow copy) — O(M) total
#   unique summary objects, not O(N^2).
# Deque bound: only the last PROXY_MESSAGES_KEEP_LAST entries have entry['messages'] populated;
#   earlier entries carry messages=None (lazy-loadable via _lazy_load_messages_forwarded).
# _fwd_req_idx: 0-based within this call; pane adds session-level offset for lazy-reload targeting.
def _parse_forwarded_log(fwd_path: Path, last_pos: int, acc_by_family: dict) -> tuple:
    entries: list = []
    recent_window: deque = deque()
    try:
        with open(fwd_path, 'r', encoding='utf-8') as f:
            f.seek(last_pos)
            req_idx = 0
            while True:
                raw_line = f.readline()
                if not raw_line:
                    break
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    fwd_e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if fwd_e.get('type') != 'forwarded_delta':
                    continue
                family = _infer_model_family(fwd_e.get('model', ''))
                is_first = fwd_e.get('is_first', False)
                counts = fwd_e.get('counts', {})
                sys_cnt = counts.get('system', 0)
                tools_cnt = counts.get('tools', 0)
                msg_cnt = counts.get('messages', 0)
                # Capture prev summaries for diff_from_prev BEFORE updating accumulator.
                # is_first=True means proxy session reset → treat as first-ever request for this family.
                prev_acc = acc_by_family.get(family)
                prev_messages_for_diff = None if is_first else (prev_acc['messages'] if prev_acc else None)
                if is_first:
                    new_system = _dict_to_list_fwd(fwd_e.get('system_delta') or {}, sys_cnt)
                    new_tools = _dict_to_list_fwd(fwd_e.get('tools_delta') or {}, tools_cnt)
                    raw_msgs = _dict_to_list_fwd(fwd_e.get('messages_delta') or {}, msg_cnt)
                    new_summaries = [
                        _summarize_fwd_message(m) if isinstance(m, dict) else {}
                        for m in raw_msgs
                    ]
                else:
                    prev = prev_acc if prev_acc else {'system': [], 'tools': [], 'messages': []}
                    new_system = _apply_delta_to_list(prev['system'], fwd_e.get('system_delta') or {}, sys_cnt)
                    new_tools = _apply_delta_to_list(prev['tools'], fwd_e.get('tools_delta') or {}, tools_cnt)
                    new_summaries = list(prev['messages'])
                    for idx_str, raw_msg in (fwd_e.get('messages_delta') or {}).items():
                        i = int(idx_str)
                        while len(new_summaries) <= i:
                            new_summaries.append({})
                        new_summaries[i] = (
                            _summarize_fwd_message(raw_msg) if isinstance(raw_msg, dict) else {}
                        )
                    if len(new_summaries) > msg_cnt:
                        new_summaries = new_summaries[:msg_cnt]
                    elif len(new_summaries) < msg_cnt:
                        new_summaries.extend([{}] * (msg_cnt - len(new_summaries)))
                acc_by_family[family] = {
                    'system': new_system,
                    'tools': new_tools,
                    'messages': new_summaries,
                }
                entry = _extract_forwarded_fields(fwd_e, new_system, new_tools, new_summaries)
                entry['_fwd_req_idx'] = req_idx
                entry['flow_id'] = fwd_e.get('flow_id', '')
                entry['diff_from_prev'] = _compute_diff(prev_messages_for_diff, new_summaries)
                entries.append(entry)
                recent_window.append((entry, new_summaries))
                if len(recent_window) > PROXY_MESSAGES_KEEP_LAST:
                    recent_window.popleft()
                req_idx += 1
            new_pos = f.tell()
    except OSError:
        return [], last_pos
    for win_entry, summaries in recent_window:
        win_entry['messages'] = list(summaries)
        win_entry['messages_total_chars'] = sum(s.get('chars', 0) for s in summaries)
    return entries, new_pos

# Replay _forwarded log from byte 0 to reconstruct messages for a stripped entry.
# entry['_fwd_req_idx'] identifies the target position in the forwarded stream.
# Returns True if entry['messages'] was populated; False on any failure.
# Cost: O(fwd_file_size) — acceptable for the small delta log.
def _lazy_load_messages_forwarded(entry: dict, fwd_path: Path) -> bool:
    target_idx = entry.get('_fwd_req_idx')
    if target_idx is None or fwd_path is None or not fwd_path.exists():
        return False
    family = _infer_model_family(entry.get('model', ''))
    temp_acc: dict = {}
    try:
        with open(fwd_path, 'r', encoding='utf-8') as f:
            req_idx = 0
            while True:
                raw_line = f.readline()
                if not raw_line:
                    break
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    fwd_e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if fwd_e.get('type') != 'forwarded_delta':
                    continue
                e_family = _infer_model_family(fwd_e.get('model', ''))
                is_first = fwd_e.get('is_first', False)
                counts = fwd_e.get('counts', {})
                msg_cnt = counts.get('messages', 0)
                if is_first:
                    raw_msgs = _dict_to_list_fwd(fwd_e.get('messages_delta') or {}, msg_cnt)
                    summaries = [
                        _summarize_fwd_message(m) if isinstance(m, dict) else {}
                        for m in raw_msgs
                    ]
                    temp_acc[e_family] = summaries
                else:
                    prev_summaries = temp_acc.get(e_family, [])
                    summaries = list(prev_summaries)
                    for idx_str, raw_msg in (fwd_e.get('messages_delta') or {}).items():
                        i = int(idx_str)
                        while len(summaries) <= i:
                            summaries.append({})
                        summaries[i] = (
                            _summarize_fwd_message(raw_msg) if isinstance(raw_msg, dict) else {}
                        )
                    if len(summaries) > msg_cnt:
                        summaries = summaries[:msg_cnt]
                    elif len(summaries) < msg_cnt:
                        summaries.extend([{}] * (msg_cnt - len(summaries)))
                    temp_acc[e_family] = summaries
                if req_idx == target_idx:
                    reconstructed = temp_acc.get(family, [])
                    entry['messages'] = list(reconstructed)
                    entry['messages_total_chars'] = sum(s.get('chars', 0) for s in reconstructed)
                    return True
                req_idx += 1
    except OSError:
        return False
    return False

# Resolve the _errors dual-log path for the current proxy session of project_filter.
# Returns None if project_filter is empty; path may not exist (callers check .exists()).
def find_errors_log_path(project_filter: Optional[str]) -> Optional[Path]:
    if not project_filter:
        return None
    root = os.environ.get('MONITOR_CC_ROOT', '') or str(Path(__file__).parent.parent.parent)
    session_id = _proxy_session_id_for_project(project_filter)
    marker_file = Path(root) / 'src' / 'logs' / f'.proxy_session_{session_id}'
    log_id = session_id
    if marker_file.exists():
        lines = marker_file.read_text(encoding='utf-8').splitlines()
        if len(lines) >= 2 and lines[1].strip():
            log_id = lines[1].strip()
    return Path(root) / 'src' / 'logs' / 'dual_log' / f'api_requests_{log_id}_errors.jsonl'

# Glob dual_log/api_requests_worker_{project_session_id}_*_errors.jsonl, read new records per
# file by byte-pos. worker_name extracted from filename (mirrors scan_worker_logs naming logic).
# Unprefixed fallback when project_session_id is empty. Returns (records, new_positions).
def scan_worker_errors_logs(last_positions: dict, project_session_id: str = '',
                            min_mtime: float = 0) -> tuple:
    root = os.environ.get('MONITOR_CC_ROOT', '') or str(Path(__file__).parent.parent.parent)
    dual_dir = Path(root) / 'src' / 'logs' / 'dual_log'
    if not dual_dir.exists():
        return [], dict(last_positions)
    new_positions = dict(last_positions)
    records: list = []
    pattern = (
        f'api_requests_worker_{project_session_id}_*_errors.jsonl'
        if project_session_id else
        'api_requests_worker_*_errors.jsonl'
    )
    for fpath in sorted(dual_dir.glob(pattern)):
        try:
            if min_mtime and fpath.stat().st_mtime < min_mtime:
                continue
        except OSError:
            continue
        last_pos = last_positions.get(str(fpath), 0)
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                f.seek(last_pos)
                while True:
                    raw_line = f.readline()
                    if not raw_line:
                        break
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    # Extract worker_name: stem = api_requests_worker_[{hash}_]{name}_{ts}_errors
                    stem = fpath.stem
                    remaining = stem.replace('api_requests_worker_', '')
                    if remaining.endswith('_errors'):
                        remaining = remaining[:-len('_errors')]
                    if project_session_id and remaining.startswith(project_session_id + '_'):
                        remaining = remaining[len(project_session_id) + 1:]
                    rec['_worker_name_from_file'] = remaining.rsplit('_', 1)[0]
                    records.append(rec)
                new_positions[str(fpath)] = f.tell()
        except OSError:
            continue
    return records, new_positions

# Read new proxy-log entries for the monitored project from the _forwarded dual-log.
# acc_by_family: persisted at caller (pane) across polling cycles for delta reconstruction.
# Returns (entries, new_fwd_pos); graceful empty return if _forwarded file is absent.
def parse_proxy_log_forwarded(project_filter: Optional[str], last_pos: int, acc_by_family: dict) -> tuple:
    root = os.environ.get('MONITOR_CC_ROOT', '') or str(Path(__file__).parent.parent.parent)
    if not project_filter:
        return [], last_pos
    session_id = _proxy_session_id_for_project(project_filter)
    marker_file = Path(root) / 'src' / 'logs' / f'.proxy_session_{session_id}'
    log_id = session_id
    if marker_file.exists():
        lines = marker_file.read_text(encoding='utf-8').splitlines()
        if len(lines) >= 2 and lines[1].strip():
            log_id = lines[1].strip()
    fwd_path = Path(root) / 'src' / 'logs' / 'dual_log' / f'api_requests_{log_id}_forwarded.jsonl'
    entries, new_pos = _parse_forwarded_log(fwd_path, last_pos, acc_by_family)
    for entry in entries:
        entry['_source_file'] = fwd_path.name
    return entries, new_pos
