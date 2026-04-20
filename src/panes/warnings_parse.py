import json
from datetime import datetime
from typing import Dict, Set

from ..constants import YELLOW, RESET

warned_unknown_types: Set[str] = set()
unknown_type_counts: Dict[str, int] = {}

INDENT = '  '


def _iso_to_float(ts: str) -> float:
    try:
        return datetime.fromisoformat(ts.replace('Z', '+00:00')).timestamp()
    except Exception:
        return 0.0


def track_unknown_type(unknown_entry: dict) -> None:
    global warned_unknown_types, unknown_type_counts
    msg_type = unknown_entry.get('type', '')
    if not msg_type:
        return
    count = unknown_entry.get('count', 1)
    unknown_type_counts[msg_type] = unknown_type_counts.get(msg_type, 0) + count


def format_unknown_type_warning(msg_type: str, count: int) -> str:
    return f"{INDENT}{YELLOW}[!] Unknown JSONL type: {msg_type} (seen {count}x){RESET}"


def format_warnings_block() -> str:
    if not unknown_type_counts:
        return ''
    header = f"{YELLOW}FORMAT WARNINGS ({len(unknown_type_counts)} unknown types){RESET}"
    lines = [header]
    for msg_type, count in sorted(unknown_type_counts.items(), key=lambda x: x[1], reverse=True):
        lines.append(format_unknown_type_warning(msg_type, count))
    return '\n'.join(lines)


def _is_tool_error(msg: dict) -> bool:
    if msg.get('type') != 'tool_result':
        return False
    for blk in msg.get('blocks', []):
        if blk.get('type') == 'tool_result' and blk.get('is_error') is True:
            return True
    return False


_ZERO_RESULT_PATTERNS = [
    "no matches found",
    "no matches found in any file.",
    "no results found",
    "no files found",
]


def _is_zero_result_block(blk: dict) -> str:
    if blk.get('type') != 'tool_result':
        return ''
    if blk.get('is_error') is True:
        return ''
    text = (blk.get('full_text', '') or blk.get('preview', '')).lower().strip()
    for pat in _ZERO_RESULT_PATTERNS:
        if text == pat or text.startswith(pat):
            return pat
    return ''


def _extract_tool_call_details(tu_blk: dict) -> tuple:
    full_text = tu_blk.get('full_text', '') or ''
    if not full_text:
        return (tu_blk.get('preview', 'tool'), {})
    lines = full_text.split('\n', 1)
    tool_name = lines[0].strip() if lines else ''
    input_dict = {}
    if len(lines) > 1:
        try:
            input_dict = json.loads(lines[1].strip())
        except Exception:
            pass
    return (tool_name or 'tool', input_dict)


def _build_tool_use_id_map(messages: list, msg_idx: int) -> dict:
    id_map = {}
    for i in range(msg_idx):
        msg = messages[i]
        if msg.get('type') != 'tool_use':
            continue
        for blk in msg.get('blocks', []):
            if blk.get('type') != 'tool_use':
                continue
            bid = blk.get('id', '')
            if bid:
                id_map[bid] = _extract_tool_call_details(blk)
    return id_map


def _resolve_tool_call(blk: dict, tu_id_map: dict, tu_blocks_positional: list, blk_idx: int) -> tuple:
    tool_use_id = blk.get('tool_use_id', '')
    if tool_use_id and tool_use_id in tu_id_map:
        return tu_id_map[tool_use_id]
    if blk_idx < len(tu_blocks_positional):
        return _extract_tool_call_details(tu_blocks_positional[blk_idx])
    if tu_blocks_positional:
        return _extract_tool_call_details(tu_blocks_positional[0])
    return ('tool', {})
