from typing import Dict, Set

from ..constants import YELLOW, RESET

warned_unknown_types: Set[str] = set()
unknown_type_counts: Dict[str, int] = {}

INDENT = '  '


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
