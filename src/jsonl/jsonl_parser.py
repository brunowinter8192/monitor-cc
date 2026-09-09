# INFRASTRUCTURE
import json
from pathlib import Path
from typing import List, Tuple

# FUNCTIONS

def read_new_lines(filepath: Path, last_position: int) -> List[str]:
    if not filepath.exists():
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        f.seek(last_position)
        content = f.read()
        if not content:
            return []
        lines = content.split('\n')
        if lines and not lines[-1]:
            lines = lines[:-1]
        return lines

def get_current_position(filepath: Path) -> int:
    return filepath.stat().st_size

def parse_jsonl_lines(lines: List[str]) -> Tuple[List[dict], List[dict]]:
    messages = []
    malformed_lines = []
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            messages.append(message)
        except json.JSONDecodeError as e:
            malformed_lines.append({
                'line_number': line_number,
                'error_message': str(e),
                'raw_line': line
            })
    return messages, malformed_lines

def get_message_content(message: dict) -> List[dict]:
    if 'message' in message and isinstance(message['message'], dict):
        content = message['message'].get('content', [])
    else:
        content = message.get('content', [])
    if isinstance(content, list):
        return content
    return []

def is_tool_use(block: dict) -> bool:
    return block.get('type') == 'tool_use'
