# INFRASTRUCTURE
from typing import Dict, Optional, Set
import json
import os
import time

from .constants import (
    YELLOW, RED, DIM, WHITE, RESET, HOVER_BG,
    INPUT_POLL_INTERVAL, WARNINGS_POLL_INTERVAL,
)
from .utils import format_timestamp, visual_line_count

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
zero_results: list = []  # list of {timestamp, tool_name, reason, tool_call_input}
zero_result_expand_states: Dict[int, bool] = {}
zero_result_line_map: Dict[int, int] = {}

# Dedup sets: proxy entries carry cumulative message history, so the same tool_result
# block reappears in every subsequent entry. Keys prevent re-counting historic results.
# Key format: (msg_idx, blk_idx, text_key) for zero-results; (msg_idx, text_key) for errors.
# Note: msg_idx is stable as long as messages are only appended. Context-trimming (rare)
# may cause a deduped item to appear at a shifted index — acceptable edge-case for v1.
_seen_zero_keys: Set = set()
_seen_error_keys: Set = set()

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
    "no files found",
]

# Check if a single tool_result block is a zero-result; returns matched reason string or empty
def _is_zero_result_block(blk: dict) -> str:
    if blk.get('type') != 'tool_result':
        return ''
    if blk.get('is_error') is True:
        return ''
    text = (blk.get('full_text', '') or blk.get('preview', '')).lower().strip()
    for pat in _ZERO_RESULT_PATTERNS:
        if text == pat or text.startswith(pat):
            return pat
    return ''

# Extract tool name and input dict from a tool_use block's full_text
def _extract_tool_call_details(tu_blk: dict) -> tuple:
    full_text = tu_blk.get('full_text', '') or ''
    if not full_text:
        return (tu_blk.get('preview', 'tool'), {})
    lines = full_text.split('\n', 1)
    tool_name = lines[0].strip() if lines else ''
    input_dict = {}
    if len(lines) > 1:
        try:
            input_dict = json.loads(lines[1].strip())
        except Exception:
            pass
    return (tool_name or 'tool', input_dict)

# Build id -> (tool_name, tool_call_input) map from all tool_use blocks before msg_idx
def _build_tool_use_id_map(messages: list, msg_idx: int) -> dict:
    id_map = {}
    for i in range(msg_idx):
        msg = messages[i]
        if msg.get('type') != 'tool_use':
            continue
        for blk in msg.get('blocks', []):
            if blk.get('type') != 'tool_use':
                continue
            bid = blk.get('id', '')
            if bid:
                id_map[bid] = _extract_tool_call_details(blk)
    return id_map


# Resolve tool name + input for a result block: id-based with positional fallback
def _resolve_tool_call(blk: dict, tu_id_map: dict, tu_blocks_positional: list, blk_idx: int) -> tuple:
    tool_use_id = blk.get('tool_use_id', '')
    if tool_use_id and tool_use_id in tu_id_map:
        return tu_id_map[tool_use_id]
    # Fallback: positional match for old proxy log entries without tool_use_id
    if blk_idx < len(tu_blocks_positional):
        return _extract_tool_call_details(tu_blocks_positional[blk_idx])
    if tu_blocks_positional:
        return _extract_tool_call_details(tu_blocks_positional[0])
    return ('tool', {})

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
            full_text = ''
            error_blk = None
            for blk in msg.get('blocks', []):
                if blk.get('type') == 'tool_result' and blk.get('is_error'):
                    candidate = blk.get('full_text', '') or blk.get('preview', '')
                    if candidate:
                        full_text = candidate
                        error_blk = blk
                        break
            if not full_text:
                full_text = msg.get('content_preview', '')
            dedup_key = (msg_idx, full_text[:200])
            if dedup_key in _seen_error_keys:
                continue
            _seen_error_keys.add(dedup_key)
            tu_id_map = _build_tool_use_id_map(messages, msg_idx)
            preceding_tu = None
            for i in range(msg_idx - 1, -1, -1):
                if messages[i].get('type') == 'tool_use':
                    preceding_tu = messages[i]
                    break
            tu_blocks_positional = [b for b in (preceding_tu.get('blocks', []) if preceding_tu else []) if b.get('type') == 'tool_use']
            if error_blk is not None:
                tool_name, _ = _resolve_tool_call(error_blk, tu_id_map, tu_blocks_positional, 0)
            elif tu_blocks_positional:
                tool_name, _ = _extract_tool_call_details(tu_blocks_positional[0])
            else:
                tool_name = 'tool'
            first_line = full_text.split('\n')[0] if full_text else ''
            summary = first_line[:80] + ('…' if len(first_line) > 80 else '')
            errors.append({
                'timestamp': ts,
                'tool_name': tool_name,
                'summary': summary,
                'full_text': full_text,
            })
    return errors

# Scan new proxy entries for zero-result tool calls; one entry per zero-result block
def _scan_proxy_entries_for_zero_results(entries: list) -> list:
    results = []
    for entry in entries:
        ts_raw = entry.get('timestamp', '')
        ts = format_timestamp(ts_raw) if ts_raw else '??:??:??'
        messages = entry.get('messages', [])
        for msg_idx, msg in enumerate(messages):
            if msg.get('type') != 'tool_result':
                continue
            blocks = msg.get('blocks', [])
            tu_id_map = _build_tool_use_id_map(messages, msg_idx)
            # Positional fallback: only tool_use-typed blocks from the preceding tool_use message
            preceding_tu = None
            for i in range(msg_idx - 1, -1, -1):
                if messages[i].get('type') == 'tool_use':
                    preceding_tu = messages[i]
                    break
            tu_blocks_positional = [b for b in (preceding_tu.get('blocks', []) if preceding_tu else []) if b.get('type') == 'tool_use']
            for blk_idx, blk in enumerate(blocks):
                reason = _is_zero_result_block(blk)
                if not reason:
                    continue
                text_key = blk.get('full_text', '') or blk.get('preview', '')
                dedup_key = (msg_idx, blk_idx, text_key)
                if dedup_key in _seen_zero_keys:
                    continue
                _seen_zero_keys.add(dedup_key)
                tool_name, tool_call_input = _resolve_tool_call(blk, tu_id_map, tu_blocks_positional, blk_idx)
                results.append({
                    'timestamp': ts,
                    'tool_name': tool_name,
                    'reason': reason.capitalize(),
                    'tool_call_input': tool_call_input,
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

# Render all warning sections into a scrollable viewport, filling error_line_map and zero_result_line_map
def _format_warnings_pane(pane_height: int, pane_width: int) -> str:
    global error_line_map, zero_result_line_map
    header = _format_warnings_header()
    content_height = max(1, pane_height - 1)
    all_lines = []
    # each key is None, ('error', idx), or ('zero', idx)
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
        wrap_width = max(20, pane_width - 6)
        for zr_idx, zr in enumerate(zero_results):
            is_expanded = zero_result_expand_states.get(zr_idx, False)
            symbol = '\u25bc' if is_expanded else '\u25b6'
            tool_col = f"{WHITE}{zr['tool_name']:<16}{RESET}"
            reason_col = f"{DIM}{zr['reason']}{RESET}"
            all_lines.append(f"{DIM}{symbol} {zr['timestamp']}  {tool_col}  {reason_col}")
            all_keys.append(('zero', zr_idx))
            if is_expanded:
                for k, v in zr.get('tool_call_input', {}).items():
                    val_str = str(v)[:wrap_width - len(k) - 4]
                    all_lines.append(f"    {DIM}{k}: {val_str}{RESET}")
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
            all_keys.append(('error', err_idx))
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

    if not schema_warnings and not unknown_type_counts and not zero_results and not tool_errors:
        all_lines.append(f"{DIM}No warnings.{RESET}")
        all_keys.append(None)

    error_line_map = {}
    zero_result_line_map = {}
    header_offset = 2  # row 1 = header, body starts at row 2
    visible_lines = all_lines[error_scroll_offset:error_scroll_offset + content_height]
    visible_keys = all_keys[error_scroll_offset:error_scroll_offset + content_height]
    rendered: list = []
    screen_row = header_offset
    for row_offset, line in enumerate(visible_lines):
        key = visible_keys[row_offset]
        span = visual_line_count(line, pane_width)
        if key is not None:
            key_type, key_idx = key
            for r in range(screen_row, screen_row + span):
                if key_type == 'error':
                    error_line_map[r] = key_idx
                elif key_type == 'zero':
                    zero_result_line_map[r] = key_idx
        hover_active = (error_hover_row is not None and
                        screen_row <= error_hover_row < screen_row + span and
                        key is not None)
        rendered.append(f"{HOVER_BG}{line}{RESET}" if hover_active else line)
        screen_row += span
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
    global schema_warnings, zero_results, zero_result_expand_states, zero_result_line_map

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
                            ekey = error_line_map.get(row)
                            if ekey is not None:
                                error_expand_states[ekey] = not error_expand_states.get(ekey, False)
                                input_changed = True
                            else:
                                zkey = zero_result_line_map.get(row)
                                if zkey is not None:
                                    zero_result_expand_states[zkey] = not zero_result_expand_states.get(zkey, False)
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
                    zero_result_expand_states.clear()
                    _seen_zero_keys.clear()
                    _seen_error_keys.clear()
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
