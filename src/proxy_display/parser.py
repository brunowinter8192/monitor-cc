# INFRASTRUCTURE
import hashlib
import json
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

# Extract analysis fields from raw_payload into entry dict, then delete raw_payload to save memory
def _extract_raw_payload_fields(entry: dict) -> None:
    raw = entry.get('raw_payload', {})
    if raw:
        system = raw.get('system', [])
        entry['system_blocks'] = [
            {'idx': i, 'chars': len(b.get('text', '')), 'has_cc': bool(b.get('cache_control')), 'preview': b.get('text', '')}
            for i, b in enumerate(system) if isinstance(b, dict)
        ] if isinstance(system, list) else []
        entry['system_total_chars'] = sum(b['chars'] for b in entry['system_blocks'])

        if entry.get('original_system2_text'):
            for sb in entry['system_blocks']:
                if sb['idx'] == 2:
                    sb['original_text'] = entry['original_system2_text']
                    break

        if entry.get('stripped_sys3_original'):
            for sb in entry['system_blocks']:
                if sb['idx'] == 3:
                    sb['original_text'] = entry['stripped_sys3_original']
                    break

        tools = raw.get('tools', [])
        entry['tools_total_chars'] = sum(len(json.dumps(t)) for t in tools)
        entry['tools_count'] = len(tools)
        entry['tools_hash'] = hashlib.md5(json.dumps(sorted([t.get('name', '') for t in tools])).encode()).hexdigest()[:8]
        entry['tools_names'] = [t.get('name', '') for t in tools]
        _tool_originals = entry.get('stripped_tool_descs_originals', {})
        entry['tools_defs'] = [
            {
                'name': t.get('name', ''),
                'description': t.get('description', ''),
                'input_schema': t.get('input_schema', {}),
                'stripped_original': _tool_originals.get(t.get('name', '')),
            }
            for t in tools
        ]

        entry['thinking_config'] = raw.get('thinking', {})
        entry['output_config'] = raw.get('output_config', {})
        entry['max_tokens'] = raw.get('max_tokens', 0)
        entry['temperature'] = raw.get('temperature', None)
        entry['top_p'] = raw.get('top_p', None)
        entry['top_k'] = raw.get('top_k', None)
        entry['tool_choice'] = raw.get('tool_choice', {})

        stored_msgs = entry.get('messages', [])
        entry['messages_total_chars'] = sum(m.get('chars', 0) for m in stored_msgs)

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
        entry['schema_warnings'] = schema_warnings

        stored_msgs = entry.get('messages', [])
        if stored_msgs and isinstance(msgs, list):
            for i, raw_msg in enumerate(msgs):
                if i < len(stored_msgs):
                    content = raw_msg.get('content', '')
                    if isinstance(content, str):
                        text = content
                    elif isinstance(content, list):
                        text = ''.join(b.get('text', '') for b in content if isinstance(b, dict))
                    else:
                        text = ''
                    stored_msgs[i]['content_tail'] = text

        persisted_originals = entry.get('stripped_persisted_output_originals', {})
        if persisted_originals and stored_msgs:
            for msg_idx_str, blocks_dict in persisted_originals.items():
                msg_idx = int(msg_idx_str)
                if msg_idx < len(stored_msgs):
                    msg_blocks = stored_msgs[msg_idx].get('blocks', [])
                    for block_idx_str, original_content in blocks_dict.items():
                        block_idx = int(block_idx_str)
                        if block_idx < len(msg_blocks):
                            msg_blocks[block_idx]['original_persisted'] = original_content

        del entry['raw_payload']

    if 'request_headers' in entry:
        del entry['request_headers']

# Read new proxy log entries from a specific log file, returning (entries, new_position)
def _parse_log_file(log_path: Path, last_position: int) -> tuple:
    if not log_path.exists():
        return [], last_position
    with open(log_path, "r", encoding="utf-8") as f:
        f.seek(last_position)
        content = f.read()
    if not content:
        return [], last_position
    lines = [ln for ln in content.split("\n") if ln.strip()]
    entries = []
    for line in lines:
        try:
            entry = json.loads(line)
            if entry.get('type') == 'sent_meta':
                if entries and entries[-1].get('request_id') == entry.get('request_id'):
                    last = entries[-1]
                    last['tools_count'] = entry.get('sent_tools_count', last.get('tools_count'))
                    last['tools_hash'] = entry.get('sent_tools_hash', last.get('tools_hash'))
                    last['sent_cache_breakpoints'] = entry.get('sent_cache_breakpoints', {})
                continue
            _extract_raw_payload_fields(entry)
            entries.append(entry)
        except json.JSONDecodeError:
            pass
    return entries, log_path.stat().st_size

# Read new proxy log entries for the monitored project, returning (entries, new_position)
def parse_proxy_log(project_filter: Optional[str], last_position: int) -> tuple:
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
    return _parse_log_file(log_file, last_position)

# Find the most recent worker proxy log for the given worker name
def find_worker_proxy_log(worker_name: str) -> Optional[Path]:
    root = os.environ.get("MONITOR_CC_ROOT", "")
    if not root:
        root = str(Path(__file__).parent.parent.parent)
    logs_dir = Path(root) / "src" / "logs"
    if not logs_dir.exists():
        return None
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

# Scan all worker proxy logs incrementally, tagging each entry with _worker_name
def scan_worker_logs(last_positions: dict) -> tuple:
    root = os.environ.get("MONITOR_CC_ROOT", "")
    if not root:
        root = str(Path(__file__).parent.parent.parent)
    logs_dir = Path(root) / "src" / "logs"
    if not logs_dir.exists():
        return [], last_positions
    all_entries: list = []
    updated_positions = dict(last_positions)
    for log_path in logs_dir.glob("api_requests_worker_*.jsonl"):
        stem = log_path.stem  # api_requests_worker_{name}_{ts}
        worker_name = stem.replace('api_requests_worker_', '').rsplit('_', 1)[0]
        pos = last_positions.get(str(log_path), 0)
        entries, new_pos = _parse_log_file(log_path, pos)
        for entry in entries:
            entry['_worker_name'] = worker_name
        all_entries.extend(entries)
        updated_positions[str(log_path)] = new_pos
    return all_entries, updated_positions
