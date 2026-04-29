# INFRASTRUCTURE
from pathlib import Path
from typing import Dict, Optional, Set
import os
import time

from ..constants import (
    YELLOW, RED, DIM, WHITE, RESET, HOVER_BG, ZEBRA_BG_A, ZEBRA_BG_B, SOFT_RESET,
    DIM_YELLOW_BG, INPUT_POLL_INTERVAL, WARNINGS_POLL_INTERVAL, WARNINGS_INITIAL_TAIL_BYTES,
)
from ..utils import format_timestamp, truncate_visible, first_word_of_call, format_worker_prefix
from ..format.strip_marker import highlight_stripped, get_stripped_data
from .warnings_parse import (
    unknown_type_counts,
    _iso_to_float,
    format_unknown_type_warning,
    _is_tool_error, _is_zero_result_block,
    _build_tool_use_id_map, _resolve_tool_call,
)
from ..ram_audit import register_ram_dump

tool_errors: list = []
error_expand_states: Dict[int, bool] = {}
error_line_map: Dict[int, int] = {}
error_hover_row: Optional[int] = None
error_scroll_offset: int = 0
_proxy_log_position: int = 0
_last_project_filter: Optional[str] = None
_last_log_path: Optional[Path] = None
_last_refresh_ts: float = 0.0
_force_refresh: bool = False
_monitor_start_ts: float = 0.0
_worker_log_positions: Dict[str, int] = {}

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
_proxy_pending_by_rid: dict = {}  # persisted across polling cycles for latency_update merge

INDENT = '  '

# FUNCTIONS

# Load historical warnings from newest main session
def load_historical_warnings() -> None:
    from ..core import monitor as _monitor
    main_sessions = _monitor.get_main_session_files()
    if main_sessions:
        filepath = main_sessions[0]
        _monitor.file_positions[filepath] = 0
        _monitor.tool_use_caches[filepath] = {}

# Scan new proxy entries for tool errors; one dict per is_error block (not per message)
def _scan_proxy_entries_for_errors(entries: list) -> list:
    errors = []
    for entry in entries:
        ts_raw = entry.get('timestamp', '')
        if ts_raw and _iso_to_float(ts_raw) < _monitor_start_ts:
            continue
        ts = format_timestamp(ts_raw) if ts_raw else '??:??:??'
        worker_name = entry.get('_worker_name', '')
        messages = entry.get('messages', [])
        for msg_idx, msg in enumerate(messages):
            if not _is_tool_error(msg):
                continue
            tu_id_map = _build_tool_use_id_map(messages, msg_idx)
            preceding_tu = None
            for i in range(msg_idx - 1, -1, -1):
                if messages[i].get('type') == 'tool_use':
                    preceding_tu = messages[i]
                    break
            tu_blocks_positional = [
                b for b in (preceding_tu.get('blocks', []) if preceding_tu else [])
                if b.get('type') == 'tool_use'
            ]
            for blk_idx, blk in enumerate(msg.get('blocks', [])):
                if blk.get('type') != 'tool_result' or not blk.get('is_error'):
                    continue
                full_text = blk.get('full_text', '') or blk.get('preview', '') or msg.get('content_preview', '')
                dedup_key = (worker_name, msg_idx, full_text[:200])
                if dedup_key in _seen_error_keys:
                    continue
                _seen_error_keys.add(dedup_key)
                tool_name, tool_call_input = _resolve_tool_call(blk, tu_id_map, tu_blocks_positional, blk_idx)
                first_line = full_text.split('\n')[0] if full_text else ''
                summary = first_line[:80] + ('…' if len(first_line) > 80 else '')
                pre_strip_text, stripped_chunks = get_stripped_data(entry, msg_idx)
                errors.append({
                    'timestamp': ts,
                    'tool_name': tool_name,
                    'summary': summary,
                    'full_text': full_text,
                    'tool_call_input': tool_call_input,
                    'worker_name': worker_name,
                    '_pre_strip_text': pre_strip_text,
                    '_stripped_chunks': stripped_chunks,
                })
    return errors

# Scan new proxy entries for zero-result tool calls; one entry per zero-result block
def _scan_proxy_entries_for_zero_results(entries: list) -> list:
    results = []
    for entry in entries:
        ts_raw = entry.get('timestamp', '')
        if ts_raw and _iso_to_float(ts_raw) < _monitor_start_ts:
            continue
        ts = format_timestamp(ts_raw) if ts_raw else '??:??:??'
        worker_name = entry.get('_worker_name', '')
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
                dedup_key = (worker_name, msg_idx, blk_idx, text_key)
                if dedup_key in _seen_zero_keys:
                    continue
                _seen_zero_keys.add(dedup_key)
                tool_name, tool_call_input = _resolve_tool_call(blk, tu_id_map, tu_blocks_positional, blk_idx)
                pre_strip_text, stripped_chunks = get_stripped_data(entry, msg_idx)
                results.append({
                    'timestamp': ts,
                    'tool_name': tool_name,
                    'reason': reason.capitalize(),
                    'tool_call_input': tool_call_input,
                    'worker_name': worker_name,
                    '_pre_strip_text': pre_strip_text,
                    '_stripped_chunks': stripped_chunks,
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
        all_lines.append(f"{RED}SCHEMA DRIFT ({len(schema_warnings)} event(s)){SOFT_RESET}")
        all_keys.append(None)
        for sw in schema_warnings:
            all_lines.append(f"{INDENT}{DIM}{sw['timestamp']}  {sw['model'][:30]}{SOFT_RESET}")
            all_keys.append(None)
            for w in sw['warnings']:
                all_lines.append(f"{INDENT}  {YELLOW}[SCHEMA] {w}{SOFT_RESET}")
                all_keys.append(None)
        all_lines.append('')
        all_keys.append(None)

    if unknown_type_counts:
        all_lines.append(f"{YELLOW}FORMAT WARNINGS ({len(unknown_type_counts)} unknown types){SOFT_RESET}")
        all_keys.append(None)
        for msg_type, count in sorted(unknown_type_counts.items(), key=lambda x: x[1], reverse=True):
            all_lines.append(format_unknown_type_warning(msg_type, count))
            all_keys.append(None)
        all_lines.append('')
        all_keys.append(None)

    if zero_results:
        all_lines.append(f"{YELLOW}ZERO RESULTS ({len(zero_results)}){SOFT_RESET}")
        all_keys.append(None)
        for zr_idx, zr in enumerate(zero_results):
            is_expanded = zero_result_expand_states.get(zr_idx, False)
            symbol = '\u25bc' if is_expanded else '\u25b6'
            tool_col = f"{WHITE}{zr['tool_name']:<16}{SOFT_RESET}"
            reason_col = f"{DIM}{zr['reason']}{SOFT_RESET}"
            w_prefix = format_worker_prefix(zr.get('worker_name', ''))
            all_lines.append(f"{DIM}{symbol} {zr['timestamp']}  {w_prefix}{tool_col}  {reason_col}")
            all_keys.append(('zero', zr_idx))
            if is_expanded:
                for k, v in zr.get('tool_call_input', {}).items():
                    val_str = str(v).replace('\n', ' ')
                    all_lines.append(f"    {DIM}{k}: {val_str}{SOFT_RESET}")
                    all_keys.append(None)
        all_lines.append('')
        all_keys.append(None)

    if tool_errors:
        all_lines.append(f"{RED}TOOL ERRORS ({len(tool_errors)}){SOFT_RESET}")
        all_keys.append(None)
        for err_idx, err in enumerate(tool_errors):
            is_expanded = error_expand_states.get(err_idx, False)
            symbol = '\u25bc' if is_expanded else '\u25b6'
            tool_col = f"{WHITE}{err['tool_name']:<16}{SOFT_RESET}"
            w_prefix = format_worker_prefix(err.get('worker_name', ''))
            inline = first_word_of_call(err['tool_name'], err.get('tool_call_input', {}))
            all_lines.append(f"{DIM}{symbol} {err['timestamp']}  {w_prefix}{tool_col}  {DIM}{inline}{SOFT_RESET}")
            all_keys.append(('error', err_idx))
            if is_expanded:
                for k, v in err.get('tool_call_input', {}).items():
                    val_str = str(v).replace('\n', ' ')
                    all_lines.append(f"    {DIM}{k}: {val_str}{SOFT_RESET}")
                    all_keys.append(None)
                pre_strip = err.get('_pre_strip_text')
                chunks = err.get('_stripped_chunks', [])
                display_text = highlight_stripped(pre_strip, chunks) if pre_strip else err['full_text']
                for raw_line in display_text.split('\n'):
                    raw_line = raw_line.expandtabs(8)
                    all_lines.append(f"    {DIM}{raw_line}{SOFT_RESET}" if raw_line else '')
                    all_keys.append(None)

    if not schema_warnings and not unknown_type_counts and not zero_results and not tool_errors:
        all_lines.append(f"{DIM}No warnings.{SOFT_RESET}")
        all_keys.append(None)

    error_line_map = {}
    zero_result_line_map = {}
    header_offset = 2  # row 1 = header, body starts at row 2
    visible_lines = all_lines[error_scroll_offset:error_scroll_offset + content_height]
    visible_keys = all_keys[error_scroll_offset:error_scroll_offset + content_height]
    rendered: list = []
    parent_count = sum(1 for k in all_keys[:error_scroll_offset] if k is not None)
    phys_row = header_offset
    for i, (line, key) in enumerate(zip(visible_lines, visible_keys)):
        if key is not None:
            zebra_bg = ZEBRA_BG_B if parent_count % 2 else ZEBRA_BG_A
            parent_count += 1
        else:
            zebra_bg = ZEBRA_BG_A
        is_hovered = (key is not None and error_hover_row is not None
                      and phys_row == error_hover_row)
        if is_hovered:
            chosen_bg = HOVER_BG
        elif DIM_YELLOW_BG in line:
            chosen_bg = DIM_YELLOW_BG
        else:
            chosen_bg = zebra_bg
        if key is not None:
            key_type, key_idx = key
            if key_type == 'error':
                error_line_map[phys_row] = key_idx
            elif key_type == 'zero':
                zero_result_line_map[phys_row] = key_idx
        rendered.append(f"{chosen_bg}{truncate_visible(line, pane_width)}\033[K{RESET}")
        phys_row += 1
    return header + '\n' + '\n'.join(rendered)

# Runs warnings-only display loop (for dedicated warnings tmux pane)
# Serialize a warnings-pane entry to full untruncated text for clipboard
def _serialize_warnings(key) -> str:
    import json
    if isinstance(key, tuple) and len(key) == 2:
        kind, idx = key
        if kind == 'error' and idx < len(tool_errors):
            err = tool_errors[idx]
            parts = [err.get('tool_name', '?')]
            inp = err.get('tool_call_input', {})
            if inp:
                parts.append(json.dumps(inp, ensure_ascii=False, indent=2))
            parts.append('')
            parts.append(err.get('full_text', ''))
            return '\n'.join(parts)
        elif kind == 'zero' and idx < len(zero_results):
            zr = zero_results[idx]
            parts = [f"{zr.get('tool_name', '?')}  reason: {zr.get('reason', '')}"]
            inp = zr.get('tool_call_input', {})
            if inp:
                parts.append(json.dumps(inp, ensure_ascii=False, indent=2))
            return '\n'.join(parts)
    return ''

def run_warnings_loop() -> None:
    from ..core import monitor as _monitor
    from ..proxy_display.parser import parse_proxy_log, scan_worker_logs, get_proxy_session_start_ts, find_proxy_log_path, proxy_session_id_for_project
    from ..input.click_handler import (
        read_keypress, setup_keyboard_input, restore_terminal,
        enable_mouse, disable_mouse, read_mouse_event,
        resolve_parent_key, copy_to_clipboard, wait_for_input,
    )
    global tool_errors, error_expand_states, error_line_map, error_hover_row
    global error_scroll_offset, _proxy_log_position, _last_project_filter
    global _last_refresh_ts, _force_refresh
    global schema_warnings, zero_results, zero_result_expand_states, zero_result_line_map
    global _monitor_start_ts, _worker_log_positions, _last_log_path
    global _proxy_pending_by_rid

    def _ram_state():
        return [
            ('tool_errors',                  tool_errors),
            ('error_expand_states',          error_expand_states),
            ('error_line_map',               error_line_map),
            ('schema_warnings',              schema_warnings),
            ('zero_results',                 zero_results),
            ('zero_result_expand_states',    zero_result_expand_states),
            ('zero_result_line_map',         zero_result_line_map),
            ('_worker_log_positions',        _worker_log_positions),
            ('_seen_zero_keys',              _seen_zero_keys),
            ('_seen_error_keys',             _seen_error_keys),
            ('_proxy_pending_by_rid',        _proxy_pending_by_rid),
            ('error_hover_row',              str(error_hover_row)),
            ('error_scroll_offset',          error_scroll_offset),
            ('_proxy_log_position',          _proxy_log_position),
            ('_last_project_filter',         str(_last_project_filter)),
            ('_last_log_path',               str(_last_log_path)),
            ('_last_refresh_ts',             _last_refresh_ts),
            ('_force_refresh',               _force_refresh),
            ('_monitor_start_ts',            _monitor_start_ts),
        ]
    register_ram_dump('warnings', _ram_state)

    _monitor_start_ts = time.time()
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
                    if char == 'y':
                        key = resolve_parent_key(error_line_map, error_hover_row)
                        if key is None:
                            key = resolve_parent_key(zero_result_line_map, error_hover_row)
                        if key is not None:
                            copy_to_clipboard(_serialize_warnings(key))
                    elif char in ('r', 'R'):
                        _force_refresh = True
                        input_changed = True

            now = time.time()
            if _force_refresh or now - last_data_refresh >= WARNINGS_POLL_INTERVAL:
                _force_refresh = False
                _monitor.monitor_sessions()

                project_filter = _monitor.active_project_filter
                log_path = find_proxy_log_path(project_filter)

                if project_filter != _last_project_filter or log_path != _last_log_path:
                    # Seek to last WARNINGS_INITIAL_TAIL_BYTES instead of position 0 to bound
                    # peak pymalloc allocation. Partial first line at seek point is silently
                    # skipped by _parse_log_file's JSONDecodeError handler.
                    _proxy_log_position = 0
                    if log_path and log_path.exists():
                        try:
                            fsize = log_path.stat().st_size
                            if fsize > WARNINGS_INITIAL_TAIL_BYTES:
                                _proxy_log_position = fsize - WARNINGS_INITIAL_TAIL_BYTES
                        except OSError:
                            pass
                    _monitor_start_ts = get_proxy_session_start_ts(project_filter) if project_filter else time.time()
                    _worker_log_positions.clear()
                    tool_errors = []
                    zero_results = []
                    schema_warnings = []
                    error_expand_states.clear()
                    zero_result_expand_states.clear()
                    _seen_zero_keys.clear()
                    _seen_error_keys.clear()
                    _proxy_pending_by_rid.clear()
                    error_scroll_offset = 0
                    error_hover_row = None
                    _last_project_filter = project_filter
                    _last_log_path = log_path

                # Detect file truncation (proxy restarted with same path)
                if log_path and log_path.exists():
                    try:
                        file_size = log_path.stat().st_size
                    except OSError:
                        file_size = None
                    if file_size is not None and file_size < _proxy_log_position:
                        _proxy_log_position = 0
                        tool_errors = []
                        zero_results = []
                        schema_warnings = []
                        error_expand_states.clear()
                        zero_result_expand_states.clear()
                        _seen_zero_keys.clear()
                        _seen_error_keys.clear()
                        _proxy_pending_by_rid.clear()
                        error_scroll_offset = 0

                new_entries, _proxy_log_position = parse_proxy_log(project_filter, _proxy_log_position, _proxy_pending_by_rid)
                _worker_sid = proxy_session_id_for_project(project_filter) if project_filter else ''
                worker_entries, _worker_log_positions = scan_worker_logs(_worker_log_positions, _worker_sid)
                all_new_entries = new_entries + worker_entries
                new_errors = _scan_proxy_entries_for_errors(all_new_entries)
                tool_errors.extend(new_errors)
                new_zero = _scan_proxy_entries_for_zero_results(all_new_entries)
                zero_results.extend(new_zero)

                for entry in new_entries:
                    if entry.get('type') == 'schema_warning':
                        ts_raw = entry.get('timestamp', '')
                        if ts_raw and _iso_to_float(ts_raw) < _monitor_start_ts:
                            continue
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
            wait_for_input(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()
