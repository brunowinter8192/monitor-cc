# INFRASTRUCTURE
from typing import Dict, List, Optional

from .constants import (
    RESET, GREEN, YELLOW, WHITE, BLUE, CYAN,
    PASTEL_BLUE, PASTEL_PURPLE, PASTEL_ORANGE,
    ORANGE, DIM,
    HOVER_BG,
    HOOK_EVENT_CATEGORIES,
)
from .utils import format_timestamp

_HOOK_CATEGORY_COLORS = {
    'session': WHITE,
    'user_input': PASTEL_PURPLE,
    'tool': PASTEL_PURPLE,
    'agent': BLUE,
    'task': GREEN,
    'response': PASTEL_ORANGE,
    'file': DIM,
    'context': ORANGE,
    'mcp': CYAN,
    'worktree': PASTEL_BLUE,
}

# FUNCTIONS

# Return True if hook entry is universal-logger noise with no content injection
def _is_noise_entry(entry: dict) -> bool:
    return (
        entry.get('hook_script', '').endswith('universal-logger.sh')
        and entry.get('output', '').startswith('tool=')
    )

# Build hooks pane display item dict for a hook log entry
def build_hook_display_item(entry: dict) -> dict:
    time_str = format_timestamp(entry.get('timestamp', ''))
    category = HOOK_EVENT_CATEGORIES.get(entry.get('hook_event', ''), 'tool')
    color = _HOOK_CATEGORY_COLORS.get(category, PASTEL_PURPLE)
    hook_script = entry.get('hook_script', '')
    cwd = entry.get('cwd', '')
    if '.claude/worktrees/' in cwd:
        color = GREEN
    else:
        color = PASTEL_ORANGE
    return {
        'type': 'hook',
        'timestamp': entry.get('timestamp', ''),
        'time_str': time_str,
        'hook_event': entry.get('hook_event', ''),
        'hook_script': entry.get('hook_script', ''),
        'detail': entry.get('output', ''),
        'content': entry.get('content', ''),
        'color': color,
        'expanded': False,
    }

# Format a single hooks display item into output lines (header + optional detail)
def format_hooks_item_lines(item: dict) -> List[str]:
    toggle = "[-]" if item.get('expanded') else "[+]"
    color = item.get('color', PASTEL_PURPLE)
    time_str = item.get('time_str', '')
    hook_event = item.get('hook_event', '')
    hook_script = item.get('hook_script', '')
    detail = item.get('detail', '')
    filename_suffix = ''
    if detail.startswith('injected: '):
        rest = detail[len('injected: '):]
        paren_idx = rest.find(' (')
        if paren_idx != -1:
            filename_suffix = ' \u2192 ' + rest[:paren_idx]
    header = f"{color}{toggle} [{time_str}] {hook_event} | {hook_script}{filename_suffix}{RESET}"
    lines = [header]
    if item.get('expanded'):
        content = item.get('content', '')
        text = content if content else item.get('detail', '')
        if text:
            for line in text.split('\n'):
                if line.strip():
                    lines.append(f"    {color}{line}{RESET}")
    return lines

# Render hooks pane items with [+]/[-] expand/collapse, hover highlight, scrolling
def format_hooks_block(items: list, line_map: dict, hover_row: Optional[int], scroll_offset: int, pane_height: int = 50, pane_width: int = 80, item_positions_out: Optional[dict] = None) -> tuple:
    if not items:
        return ('', 0)
    all_lines = []
    item_idx_at: dict = {}
    for item_idx, item in enumerate(items):
        toggle = "[-]" if item.get('expanded') else "[+]"
        color = item.get('color', PASTEL_PURPLE)
        time_str = item.get('time_str', '')
        hook_event = item.get('hook_event', '')
        hook_script = item.get('hook_script', '')
        detail = item.get('detail', '')
        filename_suffix = ''
        if detail.startswith('injected: '):
            rest = detail[len('injected: '):]
            paren_idx = rest.find(' (')
            if paren_idx != -1:
                filename_suffix = ' \u2192 ' + rest[:paren_idx]
        header = f"{color}{toggle} [{time_str}] {hook_event} | {hook_script}{filename_suffix}{RESET}"
        line_idx = len(all_lines)
        all_lines.append(header)
        item_idx_at[line_idx] = item_idx
        if item_positions_out is not None:
            item_positions_out[item_idx] = line_idx
        if item.get('expanded'):
            content = item.get('content', '')
            text = content if content else item.get('detail', '')
            if text:
                if content and len(content) > 10_000:
                    warn = f"    {YELLOW}[content {len(content):,} chars — exceeds 10K limit, Claude Code may have persisted additionalContext to disk]{RESET}"
                    all_lines.append(warn)
                max_text = pane_width - 5
                for line in text.split('\n'):
                    stripped = line.strip()
                    if stripped:
                        truncated = line[:max_text] if len(line) > max_text else line
                        if not content and stripped.startswith(('source=', 'injected:', 'tool=')):
                            all_lines.append(f"    {GREEN}{truncated}{RESET}")
                        else:
                            all_lines.append(f"    {color}{truncated}{RESET}")
    total_lines = len(all_lines)
    viewport_lines = pane_height - 1
    max_scroll = max(0, total_lines - viewport_lines)
    clamped_offset = min(scroll_offset, max_scroll)
    start = max(0, total_lines - viewport_lines - clamped_offset)
    end = start + viewport_lines
    visible_lines = all_lines[start:end]
    visible_idx_at = {k - start: v for k, v in item_idx_at.items() if start <= k < end}
    sticky_header = None
    sticky_item_idx = None
    if start > 0:
        for line_idx in range(start - 1, -1, -1):
            if line_idx in item_idx_at:
                idx = item_idx_at[line_idx]
                if items[idx].get('expanded'):
                    sticky_item_idx = idx
                    item = items[idx]
                    toggle = "[-]"
                    color = item.get('color', PASTEL_PURPLE)
                    time_str = item.get('time_str', '')
                    if item['type'] == 'hook':
                        sticky_header = f"{color}{toggle} [{time_str}] {item.get('hook_event', '')} | {item.get('hook_script', '')}{RESET}"
                    else:
                        sticky_header = f"{PASTEL_PURPLE}{toggle} [{time_str}] SYSTEM REMINDER \u2190 {item.get('tool_name', '')}{RESET}"
                break
    if line_map is not None:
        line_map.clear()
        offset = 2 if sticky_header else 1
        if sticky_item_idx is not None:
            line_map[1] = sticky_item_idx
        for content_offset, item_idx in visible_idx_at.items():
            screen_row = content_offset + offset
            line_map[screen_row] = item_idx
    output_lines = []
    if sticky_header:
        if hover_row is not None and hover_row == 1:
            output_lines.append(f"{HOVER_BG}{sticky_header}{RESET}")
        else:
            output_lines.append(sticky_header)
    row_offset_base = 2 if sticky_header else 1
    for row_offset, line in enumerate(visible_lines):
        screen_row = row_offset + row_offset_base
        if hover_row is not None and screen_row == hover_row and (row_offset in visible_idx_at):
            line = f"{HOVER_BG}{line}{RESET}"
        output_lines.append(line)
    return ('\n'.join(output_lines), total_lines)
