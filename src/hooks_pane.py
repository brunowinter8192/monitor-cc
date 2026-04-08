# INFRASTRUCTURE
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import os
import time

from .constants import (
    RESET, GREEN, YELLOW, WHITE, BLUE, CYAN,
    PASTEL_BLUE, PASTEL_PURPLE, PASTEL_ORANGE,
    ORANGE, DIM,
    HOVER_BG,
    POLL_INTERVAL, INPUT_POLL_INTERVAL,
    HOOK_EVENT_CATEGORIES,
)
from .utils import format_timestamp
from .session_finder import find_active_sessions
from .hook_parser import parse_new_hook_entries, filter_by_project, filter_by_timestamp
from .click_handler import (
    read_keypress, setup_keyboard_input, restore_terminal,
    enable_mouse, disable_mouse, read_mouse_event,
)

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

hooks_display_items: List[dict] = []
hooks_hover_row: Optional[int] = None
hooks_line_map: Dict[int, int] = {}
hooks_scroll_offset: int = 0
hooks_total_lines: int = 0
session_start_ts: Optional[str] = None

# FUNCTIONS

# Return True if hook entry is universal-logger noise with no content injection
def _is_noise_entry(entry: dict) -> bool:
    return (
        entry.get('hook_script', '').endswith('universal-logger.sh')
        and entry.get('output', '').startswith('tool=')
    )

# Scan active sessions' tool-results dirs for persisted hook additionalContext files, keyed by toolUseID
def _scan_persisted_hook_files() -> Dict[str, tuple]:
    from . import monitor as _monitor
    result = {}
    sessions = find_active_sessions(_monitor.active_project_filter)
    for session_file in sessions:
        tool_results_dir = Path(session_file).with_suffix('') / "tool-results"
        if not tool_results_dir.exists():
            continue
        for p in sorted(tool_results_dir.glob("hook-*-additionalContext.txt")):
            name = p.name
            if not name.startswith('hook-') or not name.endswith('-additionalContext.txt'):
                continue
            inner = name[len('hook-'):-len('-additionalContext.txt')]
            last_dash = inner.rfind('-')
            if last_dash < 0 or not inner[last_dash + 1:].isdigit():
                continue
            tool_use_id = inner[:last_dash]
            try:
                mtime = p.stat().st_mtime
                content = p.read_text(encoding='utf-8', errors='replace')
                result[tool_use_id] = (content, mtime)
            except OSError:
                pass
    return result

# Enrich hook display items with persisted additionalContext; returns standalone items for toolu_* files
def _enrich_with_persisted(items: List[dict], persisted: Dict[str, tuple]) -> List[dict]:
    if not persisted:
        return []
    uuid_remaining = {tid: (content, mtime) for tid, (content, mtime) in persisted.items()
                      if not tid.startswith('toolu_')}
    toolu_entries = {tid: (content, mtime) for tid, (content, mtime) in persisted.items()
                     if tid.startswith('toolu_')}
    for item in items:
        if item.get('type') != 'hook':
            continue
        if item.get('content') or item.get('was_truncated'):
            continue
        if not item.get('detail'):
            continue
        ts_str = item.get('timestamp', '')
        if not ts_str or not uuid_remaining:
            continue
        try:
            hook_dt = datetime.fromisoformat(ts_str.rstrip('Z'))
        except ValueError:
            continue
        closest_tid = min(uuid_remaining.keys(),
                          key=lambda tid: abs((datetime.utcfromtimestamp(uuid_remaining[tid][1]) - hook_dt).total_seconds()))
        closest_mtime = uuid_remaining[closest_tid][1]
        if abs((datetime.utcfromtimestamp(closest_mtime) - hook_dt).total_seconds()) < 60:
            item['content'] = uuid_remaining.pop(closest_tid)[0]
            item['was_truncated'] = True
    extra = []
    for tid, (content, mtime) in toolu_entries.items():
        dt = datetime.utcfromtimestamp(mtime)
        ts = dt.isoformat() + 'Z'
        if session_start_ts and ts < session_start_ts:
            continue
        entry = {
            'timestamp': ts,
            'hook_event': 'additionalContext',
            'hook_script': f'persisted:{tid[:20]}',
            'output': f'toolUseID={tid}',
            'content': content,
        }
        extra.append(build_hook_display_item(entry))
    return extra

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

# Load historical hook entries into hooks_display_items, session-scoped
def load_historical_hooks() -> None:
    from . import monitor as _monitor
    global session_start_ts
    entries, new_pos = parse_new_hook_entries(0)
    filtered = filter_by_project(entries, _monitor.active_project_filter) if _monitor.active_project_filter else entries
    if session_start_ts:
        filtered = filter_by_timestamp(filtered, session_start_ts)
    items = [build_hook_display_item(e) for e in filtered if not _is_noise_entry(e)]
    extra = _enrich_with_persisted(items, _scan_persisted_hook_files())
    for item in items + extra:
        hooks_display_items.append(item)
    _monitor.hook_log_position = new_pos

# Append new hook log entries to hooks_display_items
def process_hook_log_for_display() -> None:
    from . import monitor as _monitor
    entries, new_pos = parse_new_hook_entries(_monitor.hook_log_position)
    _monitor.hook_log_position = new_pos
    filtered = filter_by_project(entries, _monitor.active_project_filter) if _monitor.active_project_filter else entries
    new_items = [build_hook_display_item(e) for e in filtered if not _is_noise_entry(e)]
    if new_items:
        extra = _enrich_with_persisted(new_items, _scan_persisted_hook_files())
        for item in new_items + extra:
            hooks_display_items.append(item)

# Runs hooks display loop with mouse scroll, click expand/collapse, hover — tokens pane pattern
def run_hooks_loop() -> None:
    from . import monitor as _monitor
    global session_start_ts, hooks_display_items, hooks_hover_row, hooks_line_map, hooks_scroll_offset, hooks_total_lines
    session_start_ts = _monitor._get_session_start_ts()
    if session_start_ts is None:
        session_start_ts = datetime.utcnow().isoformat() + 'Z'
    hooks_display_items.clear()
    load_historical_hooks()
    hooks_display_items.sort(key=lambda x: x.get('timestamp', ''))
    current_main_session = _monitor._get_newest_main_session()
    last_output = None
    last_data_refresh = 0.0
    force_initial_render = True
    setup_keyboard_input()
    enable_mouse()
    try:
        just_expanded_idx = None
        while True:
            input_changed = False
            just_expanded_idx = None
            while True:
                char = read_keypress()
                if char is None:
                    break
                if char == '\033':
                    event = read_mouse_event(char)
                    if event is not None:
                        button, _col, row = event
                        if button == 0:
                            item_idx = hooks_line_map.get(row)
                            if item_idx is not None and 0 <= item_idx < len(hooks_display_items):
                                was_expanded = hooks_display_items[item_idx].get('expanded', False)
                                hooks_display_items[item_idx]['expanded'] = not was_expanded
                                input_changed = True
                                if not was_expanded:
                                    just_expanded_idx = item_idx
                        elif button == 64:
                            hooks_scroll_offset += 3
                            input_changed = True
                        elif button == 65:
                            hooks_scroll_offset = max(0, hooks_scroll_offset - 3)
                            input_changed = True
                        elif button >= 32:
                            hooks_hover_row = row
                            input_changed = True
                else:
                    if char == 'a':
                        for item in hooks_display_items:
                            item['expanded'] = True
                        input_changed = True
                    elif char == 'A':
                        for item in hooks_display_items:
                            item['expanded'] = False
                        input_changed = True
            now = time.time()
            if now - last_data_refresh >= POLL_INTERVAL:
                newest = _monitor._get_newest_main_session()
                if newest != current_main_session and newest is not None:
                    current_main_session = newest
                    session_start_ts = _monitor._get_session_start_ts()
                    if session_start_ts is None:
                        session_start_ts = datetime.utcnow().isoformat() + 'Z'
                    hooks_display_items.clear()
                    hooks_scroll_offset = 0
                    hooks_hover_row = None
                    load_historical_hooks()
                    hooks_display_items.sort(key=lambda x: x.get('timestamp', ''))
                    input_changed = True
                else:
                    old_count = len(hooks_display_items)
                    process_hook_log_for_display()
                    if len(hooks_display_items) != old_count:
                        input_changed = True
                last_data_refresh = now
            if force_initial_render and hooks_display_items:
                input_changed = True
                force_initial_render = False
            if input_changed:
                try:
                    term = os.get_terminal_size()
                    pane_height = term.lines - 1
                    pane_width = term.columns
                except OSError:
                    pane_height = 50
                    pane_width = 80
                item_positions: dict = {}
                output, hooks_total_lines = format_hooks_block(hooks_display_items, hooks_line_map, hooks_hover_row, hooks_scroll_offset, pane_height, pane_width, item_positions)
                if just_expanded_idx is not None and just_expanded_idx in item_positions:
                    item_line = item_positions[just_expanded_idx]
                    viewport_lines = pane_height - 1
                    max_scroll = max(0, hooks_total_lines - viewport_lines)
                    clamped = min(hooks_scroll_offset, max_scroll)
                    start = max(0, hooks_total_lines - viewport_lines - clamped)
                    if item_line < start or item_line >= start + viewport_lines:
                        hooks_scroll_offset = max(0, hooks_total_lines - viewport_lines - item_line)
                        output, hooks_total_lines = format_hooks_block(hooks_display_items, hooks_line_map, hooks_hover_row, hooks_scroll_offset, pane_height, pane_width)
                if output != last_output:
                    print("\033[2J\033[3J\033[H", end='', flush=True)
                    if output:
                        print(output)
                    last_output = output
            time.sleep(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()
