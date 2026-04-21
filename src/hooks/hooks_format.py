# INFRASTRUCTURE
from typing import Dict, List, Optional

from ..constants import (
    GREEN, YELLOW, WHITE, BLUE, CYAN, PASTEL_BLUE, PASTEL_PURPLE, PASTEL_ORANGE,
    ORANGE, DIM, SOFT_RESET, HOOK_EVENT_CATEGORIES,
)
from ..utils import format_timestamp

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
    header = f"{color}{toggle} [{time_str}] {hook_event} | {hook_script}{filename_suffix}{SOFT_RESET}"
    lines = [header]
    if item.get('expanded'):
        content = item.get('content', '')
        text = content if content else item.get('detail', '')
        if text:
            for line in text.split('\n'):
                line = line.expandtabs(8)
                if line.strip():
                    lines.append(f"    {color}{line}{SOFT_RESET}")
    return lines

# Build (visible_lines, visible_keys, sticky_header, viewport_start, total_lines) for hooks pane
def format_hooks_block(items: list, scroll_offset: int, pane_height: int = 50, pane_width: int = 80, item_positions_out: Optional[dict] = None) -> tuple:
    if not items:
        return ([], [], None, 0, 0, None, 0)
    all_lines: List[str] = []
    all_keys: List = []
    item_idx_at: Dict[int, int] = {}
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
        header = f"{color}{toggle} [{time_str}] {hook_event} | {hook_script}{filename_suffix}{SOFT_RESET}"
        line_idx = len(all_lines)
        all_lines.append(header)
        all_keys.append(item_idx)
        item_idx_at[line_idx] = item_idx
        if item_positions_out is not None:
            item_positions_out[item_idx] = line_idx
        if item.get('expanded'):
            content = item.get('content', '')
            text = content if content else item.get('detail', '')
            if text:
                if content and len(content) > 10_000:
                    warn = f"    {YELLOW}[content {len(content):,} chars — exceeds 10K limit, Claude Code may have persisted additionalContext to disk]{SOFT_RESET}"
                    all_lines.append(warn)
                    all_keys.append(None)
                for line in text.split('\n'):
                    line = line.expandtabs(8)
                    stripped = line.strip()
                    if stripped:
                        if not content and stripped.startswith(('source=', 'injected:', 'tool=')):
                            all_lines.append(f"    {GREEN}{stripped}{SOFT_RESET}")
                        else:
                            all_lines.append(f"    {color}{stripped}{SOFT_RESET}")
                        all_keys.append(None)
    total_lines = len(all_lines)
    viewport_lines = pane_height - 1
    max_scroll = max(0, total_lines - viewport_lines)
    clamped_offset = min(scroll_offset, max_scroll)
    start = max(0, total_lines - viewport_lines - clamped_offset)
    end = start + viewport_lines
    visible_lines = all_lines[start:end]
    visible_keys = all_keys[start:end]
    sticky_header = None
    sticky_item_idx = None
    if start > 0:
        for line_idx in range(start - 1, -1, -1):
            if line_idx in item_idx_at:
                idx = item_idx_at[line_idx]
                if items[idx].get('expanded'):
                    sticky_item_idx = idx
                    item = items[idx]
                    c = item.get('color', PASTEL_PURPLE)
                    ts = item.get('time_str', '')
                    if item['type'] == 'hook':
                        sticky_header = f"{c}[-] [{ts}] {item.get('hook_event', '')} | {item.get('hook_script', '')}{SOFT_RESET}"
                    else:
                        sticky_header = f"{PASTEL_PURPLE}[-] [{ts}] SYSTEM REMINDER \u2190 {item.get('tool_name', '')}{SOFT_RESET}"
                break
    parent_count_before = sum(1 for k in all_keys[:start] if k is not None)
    return (visible_lines, visible_keys, sticky_header, start, total_lines, sticky_item_idx, parent_count_before)
