# INFRASTRUCTURE
from typing import List, Optional
import os

from ..jsonl import read_new_lines, parse_jsonl_lines, get_message_content, is_tool_use

_WORKER_CONTEXT_WINDOW = 1000000

# FUNCTIONS

def get_worker_project_name(project_path: str) -> str:
    if '/.claude/worktrees/' in project_path:
        base = project_path.split('/.claude/worktrees/')[0]
        return os.path.basename(base)
    return os.path.basename(os.path.normpath(project_path))

def extract_worker_tokens(jsonl_path) -> dict:
    lines = read_new_lines(jsonl_path, 0)
    messages, _ = parse_jsonl_lines(lines)
    total_output = 0
    for message in messages:
        if message.get('type') != 'assistant':
            continue
        usage = message.get('message', {}).get('usage', {})
        total_output += usage.get('output_tokens', 0)
    return {'output': total_output}

def extract_worker_context_pct(jsonl_path) -> Optional[int]:
    lines = read_new_lines(jsonl_path, 0)
    messages, _ = parse_jsonl_lines(lines)
    cr = None
    for message in messages:
        if message.get('type') != 'assistant':
            continue
        val = message.get('message', {}).get('usage', {}).get('cache_read_input_tokens')
        if val is not None:
            cr = val
    if cr is None:
        return None
    return (100 * (_WORKER_CONTEXT_WINDOW - cr)) // _WORKER_CONTEXT_WINDOW

def extract_worker_tool_calls(jsonl_path) -> List[dict]:
    lines = read_new_lines(jsonl_path, 0)
    messages, _ = parse_jsonl_lines(lines)
    calls = []
    call_number = 0
    for message in messages:
        content_blocks = get_message_content(message)
        timestamp = message.get('timestamp', '')
        for block in content_blocks:
            if is_tool_use(block):
                call_number += 1
                calls.append({
                    'tool_name': block.get('name', 'Unknown'),
                    'input': block.get('input', {}),
                    'timestamp': timestamp,
                    'call_number': call_number,
                })
    return calls
