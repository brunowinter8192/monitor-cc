# INFRASTRUCTURE
from .utils import format_timestamp
from .constants import PASTEL_PURPLE, CYAN, PASTEL_ORANGE, RESET

INDENT = '  '

# FUNCTIONS

# Format USER PROMPT stamp with optional hook outputs
def format_user_prompt(timestamp: str, hook_outputs: list = None) -> str:
    time_str = format_timestamp(timestamp)
    header = f"{PASTEL_PURPLE}[{time_str}] USER PROMPT{RESET}"

    if hook_outputs:
        lines = [header]
        for output in hook_outputs:
            if output:
                lines.append(f"{INDENT}{PASTEL_PURPLE}Hook: {output}{RESET}")
        return '\n'.join(lines)
    return header

# Format hook annotation for PreToolUse hooks
def format_hook_annotation(hook_output: str, hook_script: str) -> str:
    return f"{INDENT}{PASTEL_PURPLE}Hook [{hook_script}]: {hook_output}{RESET}"

# Format system message from JSONL for display
def format_system_message(timestamp: str, text: str) -> str:
    time_str = format_timestamp(timestamp)
    header = f"{CYAN}[{time_str}] SYSTEM MESSAGE{RESET}"
    body_lines = text.split('\n')
    formatted_body = '\n'.join(f"{INDENT}{line}" for line in body_lines if line.strip())
    return f"{header}\n{formatted_body}" if formatted_body else header

# Format grouped user media items (same timestamp) as one line
def format_user_media(media_items: list) -> str:
    if not media_items:
        return ''
    time_str = format_timestamp(media_items[0].get('timestamp', ''))
    counts: dict = {}
    for item in media_items:
        media_type = item.get('type', 'unknown')
        mime_type = item.get('media_type', 'unknown')
        key = (media_type, mime_type)
        counts[key] = counts.get(key, 0) + 1
    parts = []
    for (media_type, mime_type), count in counts.items():
        if media_type == 'image':
            label = f"IMAGE: {mime_type}"
        elif media_type == 'document':
            label = f"DOC: {mime_type}"
        else:
            label = f"MEDIA: {mime_type}"
        parts.append(f"[{count}x {label}]" if count > 1 else f"[{label}]")
    return f"{PASTEL_PURPLE}[{time_str}] USER PROMPT {' '.join(parts)}{RESET}"

# Format skill/command activation with full content
def format_skill_activation(skill_item: dict) -> str:
    time_str = format_timestamp(skill_item.get('timestamp', ''))
    skill_name = skill_item.get('skill_name', 'unknown')
    content = skill_item.get('content', '')
    header = f"{CYAN}[{time_str}] SKILL LOADED: {skill_name}{RESET}"
    body_lines = content.split('\n')
    formatted_body = '\n'.join(f"{INDENT}{line}" for line in body_lines)
    return f"{header}\n{formatted_body}"

# Format thinking block from assistant
def format_thinking(thinking_item: dict) -> str:
    time_str = format_timestamp(thinking_item.get('timestamp', ''))
    thinking_text = thinking_item.get('thinking', '')
    char_count = len(thinking_text)
    preview = thinking_text[:80] + ('...' if len(thinking_text) > 80 else '')
    return f"{PASTEL_ORANGE}[{time_str}] THINKING ({char_count:,}c): {preview}{RESET}"
