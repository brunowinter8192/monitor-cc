# INFRASTRUCTURE
from typing import Optional
import os

from src.jsonl.jsonl_reader import read_json_records

_WORKER_CONTEXT_WINDOW = 1000000

# FUNCTIONS

def get_worker_project_name(project_path: str) -> str:
    if '/.claude/worktrees/' in project_path:
        base = project_path.split('/.claude/worktrees/')[0]
        return os.path.basename(base)
    return os.path.basename(os.path.normpath(project_path))

def parse_worker_stats_delta(jsonl_path, last_position: int, running_output: int,
                              running_context_pct: Optional[int]) -> tuple:
    messages, new_position = read_json_records(jsonl_path, last_position)
    if new_position == last_position:
        return running_output, running_context_pct, last_position
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
    return total_output, context_pct, new_position
