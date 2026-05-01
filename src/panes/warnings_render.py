# INFRASTRUCTURE
import datetime
import json

from ..constants import (
    YELLOW, RED, DIM, WHITE, RESET, HOVER_BG, ZEBRA_BG_A, ZEBRA_BG_B, SOFT_RESET,
    DIM_YELLOW_BG, WARNINGS_POLL_INTERVAL,
)
from ..utils import truncate_visible, first_word_of_call, format_worker_prefix
from ..format.strip_marker import highlight_stripped
from .warnings_parse import unknown_type_counts, format_unknown_type_warning

INDENT = '  '

# FUNCTIONS

# Build header line showing refresh key, last refresh time, and poll interval
def _format_warnings_header(last_refresh_ts: float) -> str:
    if last_refresh_ts:
        last_dt = datetime.datetime.fromtimestamp(last_refresh_ts)
        last_str = last_dt.strftime('%H:%M:%S')
    else:
        last_str = '--:--:--'
    return f"{DIM}[r]efresh · last: {last_str} · polling: {int(WARNINGS_POLL_INTERVAL)}s{RESET}"


# Render all warning sections; returns (rendered_str, new_error_line_map, new_zero_result_line_map)
def _format_warnings_pane(
    tool_errors: list,
    error_expand_states: dict,
    error_hover_row,
    error_scroll_offset: int,
    schema_warnings: list,
    zero_results: list,
    zero_result_expand_states: dict,
    pane_height: int,
    pane_width: int,
    last_refresh_ts: float,
) -> tuple:
    header = _format_warnings_header(last_refresh_ts)
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

    new_error_line_map = {}
    new_zero_result_line_map = {}
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
                new_error_line_map[phys_row] = key_idx
            elif key_type == 'zero':
                new_zero_result_line_map[phys_row] = key_idx
        rendered.append(f"{chosen_bg}{truncate_visible(line, pane_width)}\033[K{RESET}")
        phys_row += 1
    return header + '\n' + '\n'.join(rendered), new_error_line_map, new_zero_result_line_map


# Serialize a warnings-pane entry to full untruncated text for clipboard
def _serialize_warnings(key, tool_errors: list, zero_results: list) -> str:
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
