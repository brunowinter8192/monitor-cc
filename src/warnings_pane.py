# INFRASTRUCTURE
from typing import Dict, Optional, Set
import os
import time

from .constants import (
    YELLOW, RED, DIM, WHITE, RESET, HOVER_BG,
    INPUT_POLL_INTERVAL, WARNINGS_POLL_INTERVAL,
)
from .utils import format_timestamp

warned_unknown_types: Set[str] = set()
unknown_type_counts: Dict[str, int] = {}

tool_errors: list = []
error_expand_states: Dict[int, bool] = {}
error_line_map: Dict[int, int] = {}
error_hover_row: Optional[int] = None
error_scroll_offset: int = 0
_proxy_log_position: int = 0
_last_project_filter: Optional[str] = None
_last_refresh_ts: float = 0.0
_force_refresh: bool = False

schema_warnings: list = []  # list of {timestamp, model, warnings: list[str]}
zero_results: list = []  # list of {timestamp, tool_name, summary}

INDENT = '  '

# FUNCTIONS

# Track unknown JSONL message type for warnings pane
def track_unknown_type(unknown_entry: dict) -> None:
    global warned_unknown_types, unknown_type_counts
    msg_type = unknown_entry.get('type', '')
    if not msg_type:
        return
    count = unknown_entry.get('count', 1)
    unknown_type_counts[msg_type] = unknown_type_counts.get(msg_type, 0) + count

# Format unknown JSONL type warning for warnings pane
def format_unknown_type_warning(msg_type: str, count: int) -> str:
    return f"{INDENT}{YELLOW}[!] Unknown JSONL type: {msg_type} (seen {count}x){RESET}"

# Format warnings block for dedicated pane
def format_warnings_block() -> str:
    if not unknown_type_counts:
        return ''
    header = f"{YELLOW}FORMAT WARNINGS ({len(unknown_type_counts)} unknown types){RESET}"
    lines = [header]
    for msg_type, count in sorted(unknown_type_counts.items(), key=lambda x: x[1], reverse=True):
        warning = format_unknown_type_warning(msg_type, count)
        lines.append(warning)
    return '\n'.join(lines)

# Load historical warnings from newest main session
def load_historical_warnings() -> None:
    from . import monitor as _monitor
    main_sessions = _monitor.get_main_session_files()
    if main_sessions:
        filepath = main_sessions[0]
        _monitor.file_positions[filepath] = 0
        _monitor.tool_use_caches[filepath] = {}

# Check if a proxy message is a tool error via the structural is_error flag on tool_result blocks
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
]

# Check if a proxy message is a zero-result tool call (exit 0 but returned empty results)
def _is_zero_result(msg: dict) -> bool:
    if msg.get('type') != 'tool_result':
        return False
    for blk in msg.get('blocks', []):
        if blk.get('type') != 'tool_result':
            continue
        if blk.get('is_error') is True:
            return False
        text = (blk.get('full_text', '') or blk.get('preview', '')).lower().strip()
        for pat in _ZERO_RESULT_PATTERNS:
            if text == pat or text.startswith(pat):
                return True
    return False

# Extract tool name from preceding tool_use message in the messages list
def _extract_tool_name(messages: list, msg_idx: int) -> str:
    for i in range(msg_idx - 1, -1, -1):
        prev = messages[i]
        if prev.get('type') == 'tool_use':
            for blk in prev.get('blocks', []):
                if blk.get('type') == 'tool_use':
                    name = blk.get('preview', '')
                    if name:
                        return name
    return 'tool'

# Scan new proxy entries for tool errors and return error dicts
def _scan_proxy_entries_for_errors(entries: list) -> list:
    errors = []
    for entry in entries:
        ts_raw = entry.get('timestamp', '')
        ts = format_timestamp(ts_raw) if ts_raw else '??:??:??'
        messages = entry.get('messages', [])
        for msg_idx, msg in enumerate(messages):
            if not _is_tool_error(msg):
                continue
            tool_name = _extract_tool_name(messages, msg_idx)
            full_text = ''
            for blk in msg.get('blocks', []):
                candidate = blk.get('full_text', '') or blk.get('preview', '')
                if candidate:
                    full_text = candidate
                    break
            if not full_text:
                full_text = msg.get('content_preview', '')
            first_line = full_text.split('\n')[0] if full_text else ''
            summary = first_line[:80] + ('…' if len(first_line) > 80 else '')
            errors.append({
                'timestamp': ts,
                'tool_name': tool_name,
                'summary': summary,
                'full_text': full_text,
            })
    return errors

# Scan new proxy entries for zero-result tool calls and return zero-result dicts
def _scan_proxy_entries_for_zero_results(entries: list) -> list:
    results = []
    for entry in entries:
        ts_raw = entry.get('timestamp', '')
        ts = format_timestamp(ts_raw) if ts_raw else '??:??:??'
        messages = entry.get('messages', [])
        for msg_idx, msg in enumerate(messages):
            if not _is_zero_result(msg):
                continue
            tool_name = _extract_tool_name(messages, msg_idx)
            full_text = ''
            for blk in msg.get('blocks', []):
                candidate = blk.get('full_text', '') or blk.get('preview', '')
                if candidate:
                    full_text = candidate
                    break
            if not full_text:
                full_text = msg.get('content_preview', '')
            first_line = full_text.split('\n')[0] if full_text else ''
            summary = first_line[:80] + ('…' if len(first_line) > 80 else '')
            results.append({
                'timestamp': ts,
                'tool_name': tool_name,
                'summary': summary,
            })
    return results

# Build header line showing refresh key, last refresh time, and poll interval
def _format_warnings_header() -> str:
    if _last_refresh_ts:
        import datetime
        last_dt = datetime.datetime.fromtimestamp(_last_refresh_ts)
        last_str = last_dt.strftime('%H:%M:%S')
    else:
        last_str = '--:--:--'
    return f"{DIM}[r]efresh · last: {last_str} · polling: {int(WARNINGS_POLL_INTERVAL)}s{RESET}"

# Render both warning sections into a scrollable viewport, filling error_line_map
def _format_warnings_pane(pane_height: int, pane_width: int) -> str:
    global error_line_map
    header = _format_warnings_header()
    content_height = max(1, pane_height - 1)
    all_lines = []
    all_keys = []

    if schema_warnings:
        all_lines.append(f"{RED}SCHEMA DRIFT ({len(schema_warnings)} event(s)){RESET}")
        all_keys.append(None)
        for sw in schema_warnings:
            all_lines.append(f"{INDENT}{DIM}{sw['timestamp']}  {sw['model'][:30]}{RESET}")
            all_keys.append(None)
            for w in sw['warnings']:
                all_lines.append(f"{INDENT}  {YELLOW}[SCHEMA] {w}{RESET}")
                all_keys.append(None)
        all_lines.append('')
        all_keys.append(None)

    if unknown_type_counts:
        all_lines.append(f"{YELLOW}FORMAT WARNINGS ({len(unknown_type_counts)} unknown types){RESET}")
        all_keys.append(None)
        for msg_type, count in sorted(unknown_type_counts.items(), key=lambda x: x[1], reverse=True):
            all_lines.append(format_unknown_type_warning(msg_type, count))
            all_keys.append(None)
        all_lines.append('')
        all_keys.append(None)

    if zero_results:
        all_lines.append(f"{YELLOW}ZERO RESULTS ({len(zero_results)}){RESET}")
        all_keys.append(None)
        for zr in zero_results:
            tool_col = f"{WHITE}{zr['tool_name']:<16}{RESET}"
            all_lines.append(f"{INDENT}{DIM}{zr['timestamp']}  {tool_col}  {DIM}{zr['summary']}{RESET}")
            all_keys.append(None)
        all_lines.append('')
        all_keys.append(None)

    if tool_errors:
        all_lines.append(f"{RED}TOOL ERRORS ({len(tool_errors)}){RESET}")
        all_keys.append(None)
        wrap_width = max(20, pane_width - 6)
        for err_idx, err in enumerate(tool_errors):
            is_expanded = error_expand_states.get(err_idx, False)
            symbol = '\u25bc' if is_expanded else '\u25b6'
            tool_col = f"{WHITE}{err['tool_name']:<16}{RESET}"
            all_lines.append(f"{DIM}{symbol} {err['timestamp']}  {tool_col}  {DIM}{err['summary']}{RESET}")
            all_keys.append(err_idx)
            if is_expanded:
                for raw_line in err['full_text'].split('\n'):
                    if not raw_line:
                        all_lines.append('')
                        all_keys.append(None)
                        continue
                    for line_start in range(0, len(raw_line), wrap_width):
                        chunk = raw_line[line_start:line_start + wrap_width]
                        all_lines.append(f"    {DIM}{chunk}{RESET}")
                        all_keys.append(None)
    elif not unknown_type_counts:
        all_lines.append(f"{DIM}No warnings.{RESET}")
        all_keys.append(None)

    error_line_map = {}
    header_offset = 2  # row 1 = header, body starts at row 2
    visible_lines = all_lines[error_scroll_offset:error_scroll_offset + content_height]
    visible_keys = all_keys[error_scroll_offset:error_scroll_offset + content_height]
    rendered: list = []
    for row_offset, line in enumerate(visible_lines):
        screen_row = row_offset + header_offset
        key = visible_keys[row_offset]
        if key is not None:
            error_line_map[screen_row] = key
        if error_hover_row is not None and screen_row == error_hover_row and key is not None:
            rendered.append(f"{HOVER_BG}{line}{RESET}")
        else:
            rendered.append(line)
    return header + '\n' + '\n'.join(rendered)

# Runs warnings-only display loop (for dedicated warnings tmux pane)
def run_warnings_loop() -> None:
    from . import monitor as _monitor
    from .proxy_display.parser import parse_proxy_log
    from .click_handler import (
        read_keypress, setup_keyboard_input, restore_terminal,
        enable_mouse, disable_mouse, read_mouse_event,
    )
    global tool_errors, error_expand_states, error_line_map, error_hover_row
    global error_scroll_offset, _proxy_log_position, _last_project_filter
    global _last_refresh_ts, _force_refresh
    global schema_warnings, zero_results

    load_historical_warnings()
    last_output = None
    last_data_refresh = 0.0
    setup_keyboard_input()
    enable_mouse()
    try:
        while True:
            input_changed = False
            while True:
                char = read_keypress()
                if char is None:
                    break
                if char == '\033':
                    event = read_mouse_event(char)
                    if event is not None:
                        button, col, row = event
                        if button == 0:
                            key = error_line_map.get(row)
                            if key is not None:
                                error_expand_states[key] = not error_expand_states.get(key, False)
                                input_changed = True
                        elif button == 64:
                            # tmux.h: MOUSE_WHEEL_UP=64 → scroll viewport up → offset decreases.
                            # NOTE: token_pane uses offset+3 for button 64 because it renders
                            # bottom-to-top (start = len-height-offset). warnings_pane renders
                            # top-to-bottom (visible = lines[offset:offset+height]), so directions
                            # are opposite: wheel-up must decrease offset here.
                            error_scroll_offset = max(0, error_scroll_offset - 3)
                            input_changed = True
                        elif button == 65:
                            # tmux.h: MOUSE_WHEEL_DOWN=65 → scroll viewport down → offset increases
                            error_scroll_offset = error_scroll_offset + 3
                            input_changed = True
                        elif button >= 32:
                            error_hover_row = row
                            input_changed = True
                else:
                    if char in ('r', 'R'):
                        _force_refresh = True
                        input_changed = True

            now = time.time()
            if _force_refresh or now - last_data_refresh >= WARNINGS_POLL_INTERVAL:
                _force_refresh = False
                _monitor.monitor_sessions()

                project_filter = _monitor.active_project_filter
                if project_filter != _last_project_filter:
                    _proxy_log_position = 0
                    tool_errors = []
                    zero_results = []
                    schema_warnings = []
                    error_expand_states.clear()
                    error_scroll_offset = 0
                    error_hover_row = None
                    _last_project_filter = project_filter

                new_entries, _proxy_log_position = parse_proxy_log(project_filter, _proxy_log_position)
                new_errors = _scan_proxy_entries_for_errors(new_entries)
                tool_errors.extend(new_errors)
                new_zero = _scan_proxy_entries_for_zero_results(new_entries)
                zero_results.extend(new_zero)

                for entry in new_entries:
                    if entry.get('type') == 'schema_warning':
                        ts_raw = entry.get('timestamp', '')
                        ts = format_timestamp(ts_raw) if ts_raw else '??:??:??'
                        schema_warnings.append({
                            'timestamp': ts,
                            'model': entry.get('model', ''),
                            'warnings': entry.get('warnings', []),
                        })

                last_data_refresh = now
                _last_refresh_ts = now
                input_changed = True

            if input_changed:
                try:
                    term = os.get_terminal_size()
                    pane_height = term.lines - 1
                    pane_width = term.columns
                except OSError:
                    pane_height = 50
                    pane_width = 80
                output = _format_warnings_pane(pane_height, pane_width)
                if output != last_output:
                    print("\033[2J\033[3J\033[H", end='', flush=True)
                    if output:
                        print(output, end='', flush=True)
                        print(f"\033[H{_format_warnings_header()}\033[K", end='', flush=True)
                    last_output = output
            time.sleep(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()
