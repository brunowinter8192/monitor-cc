# INFRASTRUCTURE
from typing import List, Optional
import os

from ..jsonl import read_new_lines, parse_jsonl_lines, get_current_position, get_message_content, is_tool_use

_WORKER_CONTEXT_WINDOW = 1000000

# FUNCTIONS

def get_worker_project_name(project_path: str) -> str:
    if '/.claude/worktrees/' in project_path:
        base = project_path.split('/.claude/worktrees/')[0]
        return os.path.basename(base)
    return os.path.basename(os.path.normpath(project_path))

def parse_worker_stats_delta(jsonl_path, last_position: int, running_output: int,
                              running_context_pct: Optional[int]) -> tuple:
    lines = read_new_lines(jsonl_path, last_position)
    if not lines:
        return running_output, running_context_pct, last_position
    messages, _ = parse_jsonl_lines(lines)
    total_output = running_output
    context_pct = running_context_pct
    for message in messages:
        if message.get('type') != 'assistant':
            continue
        usage = message.get('message', {}).get('usage', {})
        total_output += usage.get('output_tokens', 0)
        cr = usage.get('cache_read_input_tokens')
        if cr is not None:
            context_pct = (100 * (_WORKER_CONTEXT_WINDOW - cr)) // _WORKER_CONTEXT_WINDOW
    return total_output, context_pct, get_current_position(jsonl_path)

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
