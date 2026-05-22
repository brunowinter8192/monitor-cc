# INFRASTRUCTURE
from datetime import datetime
import time
from typing import Optional

from ..constants import (
    RESET, GREEN, YELLOW, CYAN, DIM_YELLOW_BG, WHITE, HOVER_BG,
    SEARCH_MATCH_BG, SEARCH_CURRENT_BG,
    MODE_ALL, MODE_MAIN, MAIN_EVENT_BUFFER_CAP,
)
from ..format.formatter import format_tool_call
from ..format.formatter_events import format_user_prompt, format_user_media, format_thinking, format_skill_activation, format_system_message
from ..format.strip_marker import highlight_stripped, build_tool_id_strip_lookup
from ..utils import truncate_visible, _ANSI_ESCAPE_RE, _cell_width

# Private search-bar colors (not in palette; internal to this module)
_SRCH_LABEL = '\033[38;2;108;112;134m'   # muted gray — "Search:" label
_SRCH_IDLE  = '\033[38;2;166;173;200m'   # medium gray — unfocused query text
_SRCH_BASE  = f'\033[0m{HOVER_BG}'       # RESET + hover-BG baseline between segments

INDENT = '  '

main_event_buffer: list = []
main_scroll_offset: int = 0
main_hover_row: Optional[int] = None
main_line_map: dict = {}            # phys_row → event_idx into main_event_buffer
_strip_by_tool_id: dict = {}        # tool_use_id → (pre_strip_text, removed_chunks)
_strip_prompt_ts_set: set = set()   # proxy-entry timestamps where msg[0] was stripped
_main_copy_rows: dict = {}          # phys_row → (event_idx, part)  part ∈ {'request','response'}
_main_copy_feedback_until: dict = {}  # (event_idx, part) → expiry float
_main_pane_width: int = 80          # updated each render cycle; read by click handler

# Search state
_search_query: str = ''
_search_focused: bool = False
_search_committed: bool = False      # True after Enter; False during editing → no highlights
_search_matches: list = []           # [event_idx, ...] ordered by position in buffer
_search_match_set: set = set()       # set(_search_matches) for O(1) membership
_search_current_idx: int = 0         # index into _search_matches for current match
_search_cached_query: str = ''       # query used to build current _search_matches
_search_all_line_offsets: dict = {}  # event_idx → first_line_idx in all_lines (for scroll)
_search_total_lines: int = 0         # len(all_lines) from last render (for scroll)

# FUNCTIONS

# Append structured event to buffer; trim oldest if cap exceeded
def _buffer_append(event_type: str, data: dict, call_number=None) -> None:
    global main_event_buffer
    main_event_buffer.append({'type': event_type, 'data': data, 'call_number': call_number})
    if len(main_event_buffer) > MAIN_EVENT_BUFFER_CAP:
        del main_event_buffer[:len(main_event_buffer) - MAIN_EVENT_BUFFER_CAP]

# Truncate line to max length for display (legacy helper, kept for format_warning)
def truncate_line(line: str, max_length: int) -> str:
    if len(line) <= max_length:
        return line
    return line[:max_length] + '...'

# Format WARNING header with yellow color for malformed lines
def format_warning(file_path: str, line_number: int, error_message: str, raw_line: str) -> str:
    now = datetime.now().strftime('%H:%M:%S')
    header = f"{YELLOW}[{now}] [!] WARNING - Malformed JSON{RESET}"
    truncated_line = truncate_line(raw_line, 200)
    details = [
        f"{INDENT}File: {file_path}",
        f"{INDENT}Line: {line_number}",
        f"{INDENT}Error: {error_message}",
        f"{INDENT}Content: {truncated_line}"
    ]
    return f"{header}\n" + '\n'.join(details)

# Buffer warning event
def display_warning(warning: dict) -> None:
    _buffer_append('warning', warning)

# Buffer user media event (items already grouped by caller)
def display_user_media(media_items: list) -> None:
    _buffer_append('user_media', {'items': media_items})

# Buffer skill/command activation event
def display_skill_activation(skill_item: dict) -> None:
    _buffer_append('skill_activation', skill_item)

# Buffer thinking block event
def display_thinking(thinking_item: dict) -> None:
    _buffer_append('thinking', thinking_item)

# Buffer tool call event
def display_tool_call(tool_call: dict, call_number: int) -> None:
    _buffer_append('tool_call', tool_call, call_number)

# Buffer user prompt event
def display_user_prompt_from_jsonl(prompt_item: dict) -> None:
    _buffer_append('user_prompt', prompt_item)

# Buffer system message event
def display_system_message(sys_msg: dict) -> None:
    _buffer_append('system_message', sys_msg)

# Ingest new proxy entries to populate strip caches (call from main loop after monitor_sessions)
def ingest_proxy_strip_data(entries: list) -> None:
    global _strip_by_tool_id, _strip_prompt_ts_set
    new_tool_lookup = build_tool_id_strip_lookup(entries)
    _strip_by_tool_id.update(new_tool_lookup)
    for entry in entries:
        if entry.get('stripped_msg_indices'):
            ts = entry.get('timestamp', '')
            if ts:
                _strip_prompt_ts_set.add(ts[:19])  # second-precision bucket

# Format buffered event to list of display strings (split by newline)
def _format_event_to_lines(event: dict) -> list:
    t = event['type']
    d = event['data']
    if t == 'tool_call':
        tool_use_id = d['tool_use_id']
        strip_info = _strip_by_tool_id.get(tool_use_id)
        if strip_info:
            pre_strip_text, stripped_chunks = strip_info
            output_data = pre_strip_text or d['output'] or ''
        else:
            output_data = d['output'] or ''
        formatted = format_tool_call(
            tool_name=d['tool_name'],
            input_data=d['input'],
            output_data=output_data,
            tool_use_id=tool_use_id,
            timestamp=d['timestamp'],
            call_number=event['call_number'],
            is_subagent=d.get('is_subagent', False),
            system_reminders=d.get('system_reminders', []),
            is_error=d.get('is_error', False),
        )
        if strip_info and stripped_chunks:
            formatted = highlight_stripped(formatted, stripped_chunks)
    elif t == 'user_prompt':
        ts = d.get('timestamp', '')
        has_strip = bool(ts and ts[:19] in _strip_prompt_ts_set)
        formatted = format_user_prompt(ts, strip_badge=has_strip)
    elif t == 'user_media':
        formatted = format_user_media(d.get('items', []))
    elif t == 'thinking':
        formatted = format_thinking(d)
    elif t == 'skill_activation':
        formatted = format_skill_activation(d)
    elif t == 'system_message':
        formatted = format_system_message(d.get('timestamp', ''), d.get('text', ''))
    elif t == 'warning':
        formatted = format_warning(d['file_path'], d['line_number'], d['error_message'], d['raw_line'])
    elif t == 'session_banner':
        formatted = f"{CYAN}--- New session detected ---{RESET}"
    else:
        return []
    return formatted.split('\n')

# Inject match_bg around each occurrence of query in line (case-insensitive, ANSI-safe)
# Strategy: strip ANSI to find literal matched substrings → split ANSI-bearing line on each chunk
# → join with bg+chunk+\033[49m. Silently skips when query straddles an ANSI code boundary.
def _highlight_query_in_line(line: str, query: str, match_bg: str) -> str:
    if not query or not line:
        return line
    stripped = _ANSI_ESCAPE_RE.sub('', line)
    q_lower = query.lower()
    s_lower = stripped.lower()
    if q_lower not in s_lower:
        return line
    # Collect distinct literal chunks (preserving original case) from stripped text
    seen: set = set()
    pos = 0
    while True:
        p = s_lower.find(q_lower, pos)
        if p == -1:
            break
        seen.add(stripped[p:p + len(query)])
        pos = p + 1
    result = line
    for chunk in seen:
        parts = result.split(chunk)
        if len(parts) < 2:
            continue  # chunk not found in ANSI-bearing string (straddled escape code)
        result = f"{match_bg}{chunk}\033[49m".join(parts)
    return result


# Case-insensitive substring match against serialized event text; returns (matches, match_set)
def _compute_search_matches(query: str) -> tuple:
    if not query:
        return [], set()
    q = query.lower()
    matches = []
    for event_idx in range(len(main_event_buffer)):
        if q in serialize_main_event(event_idx, 'all').lower():
            matches.append(event_idx)
    return matches, set(matches)

# Render the always-visible search bar (row 1); returns ANSI string ≤ pane_width visible cells
def _render_search_bar(pane_width: int) -> str:
    cursor = '_' if _search_focused else ''
    left_plain = f"Search: {_search_query}{cursor}"
    left_vis = sum(_cell_width(ch) for ch in left_plain)

    m = len(_search_matches)
    has_matches = bool(_search_query and m > 0)

    if has_matches:
        counter_plain = f"{_search_current_idx + 1}/{m}"
        cnt_color = CYAN
        arrow_color = GREEN
    elif _search_query:
        counter_plain = "0/0"
        cnt_color = _SRCH_LABEL
        arrow_color = _SRCH_LABEL
    else:
        counter_plain = ""
        cnt_color = _SRCH_LABEL
        arrow_color = _SRCH_LABEL

    right_plain = (f" {counter_plain} [←] [→]" if counter_plain else " [←] [→]")
    right_vis = sum(_cell_width(ch) for ch in right_plain)
    gap = max(0, pane_width - left_vis - right_vis)

    query_color = WHITE if _search_focused else _SRCH_IDLE
    cursor_part = f"{CYAN}_" if _search_focused else ""
    counter_part = (f" {cnt_color}{counter_plain}{_SRCH_BASE}" if counter_plain else "")

    bar = (
        f"{_SRCH_BASE}"
        f"{_SRCH_LABEL}Search: {_SRCH_BASE}"
        f"{query_color}{_search_query}{_SRCH_BASE}"
        f"{cursor_part}{_SRCH_BASE}"
        f"{' ' * gap}"
        f"{counter_part}"
        f" {arrow_color}[←]{_SRCH_BASE}"
        f" {arrow_color}[→]{_SRCH_BASE}"
    )
    return truncate_visible(bar, pane_width)

# Adjust main_scroll_offset so the current match's first line is visible in the buffer area
def ensure_match_visible() -> None:
    import os
    global main_scroll_offset
    if not _search_matches or _search_current_idx >= len(_search_matches):
        return
    target_eidx = _search_matches[_search_current_idx]
    target_line = _search_all_line_offsets.get(target_eidx)
    if target_line is None:
        return
    try:
        term = os.get_terminal_size()
        buffer_height = term.lines - 2  # terminal -1 for safety, -1 for search bar row
    except OSError:
        buffer_height = 48
    new_start = max(0, target_line - 2)  # 2 lines context above match
    main_scroll_offset = max(0, _search_total_lines - buffer_height - new_start)

# Render event buffer to screen-sized string with zebra shading + truncation; fills main_line_map
# Row 1 is the persistent search bar; buffer events render from row 2 onward.
def render_main_buffer(pane_height: int, pane_width: int, scroll_offset: int) -> str:
    global main_line_map, _main_copy_rows, _main_pane_width
    global _search_current_idx
    global _search_all_line_offsets, _search_total_lines

    _main_pane_width = pane_width
    buffer_height = pane_height - 1  # row 1 reserved for search bar

    all_lines = []
    all_event_indices = []  # parallel list: event_idx per line, or -1 for blanks
    _search_all_line_offsets = {}
    for event_idx, event in enumerate(main_event_buffer):
        _search_all_line_offsets[event_idx] = len(all_lines)
        event_lines = _format_event_to_lines(event)
        for el in event_lines:
            all_lines.append(el)
            all_event_indices.append(event_idx)
        all_lines.append('')
        all_event_indices.append(-1)  # blank separator

    _search_total_lines = len(all_lines)

    # Clamp current_idx on buffer shrink (matches only populated on Enter commit)
    if _search_matches:
        _search_current_idx = min(_search_current_idx, len(_search_matches) - 1)

    current_match_eidx = (
        _search_matches[_search_current_idx]
        if _search_matches and _search_current_idx < len(_search_matches)
        else None
    )

    total = _search_total_lines
    # scroll_offset=0 → show newest (bottom); increasing offset scrolls up
    start = max(0, total - buffer_height - scroll_offset)
    visible = all_lines[start:start + buffer_height]
    visible_event_indices = all_event_indices[start:start + buffer_height]

    main_line_map.clear()
    _main_copy_rows.clear()
    result_lines = []

    for phys_idx, (line, eidx) in enumerate(zip(visible, visible_event_indices)):
        phys_row = phys_idx + 2  # row 1 is search bar; buffer starts at row 2

        # Search highlight: inject BG only around matched substring (per line, ANSI-safe)
        if eidx >= 0 and _search_match_set and _search_query:
            if eidx == current_match_eidx:
                line = _highlight_query_in_line(line, _search_query, SEARCH_CURRENT_BG)
            elif eidx in _search_match_set:
                line = _highlight_query_in_line(line, _search_query, SEARCH_MATCH_BG)

        # ⎘ copy-button injection (existing — ANSI strip accounts for prepended BG)
        if eidx >= 0 and main_event_buffer[eidx]['type'] == 'tool_call':
            stripped = _ANSI_ESCAPE_RE.sub('', line)
            if '] REQUEST #' in stripped:
                part = 'request'
            elif '] RESPONSE #' in stripped:
                part = 'response'
            else:
                part = None
            if part is not None:
                is_flash = _main_copy_feedback_until.get((eidx, part), 0) > time.time()
                copy_sym = '✓' if is_flash else '⎘'
                sym_cells = _cell_width(copy_sym)
                visible_len = sum(_cell_width(ch) for ch in stripped)
                pad = pane_width - 1 - sym_cells - visible_len  # 1 space gap + sym_cells
                if pad >= 0:
                    line = line + ' ' * pad + ' ' + copy_sym
                _main_copy_rows[phys_row] = (eidx, part)

        trunc = truncate_visible(line, pane_width)
        result_lines.append(f"{trunc}\033[K{RESET}")
        if eidx >= 0:
            main_line_map[phys_row] = eidx

    search_bar = _render_search_bar(pane_width)
    return f"{search_bar}\033[K{RESET}\n" + '\n'.join(result_lines)

# Serialize a main-pane event to full untruncated text for clipboard
# part='all' → header+INPUT+OUTPUT (y-hotkey); 'request' → header+INPUT; 'response' → header+OUTPUT
def serialize_main_event(event_idx: int, part: str = 'all') -> str:
    import json
    if event_idx < 0 or event_idx >= len(main_event_buffer):
        return ''
    event = main_event_buffer[event_idx]
    t = event['type']
    d = event['data']
    if t == 'tool_call':
        tool_name = d.get('tool_name', '?')
        inp = d.get('input', {})
        out = d.get('output', '') or ''
        header = f"{tool_name}  call#{event.get('call_number', '?')}  [{d.get('timestamp', '')}]"
        inp_text = json.dumps(inp, ensure_ascii=False, indent=2) if isinstance(inp, dict) else str(inp)
        if part == 'request':
            sections = [header, "---INPUT---", inp_text]
        elif part == 'response':
            sections = [header, "---OUTPUT---", out]
        else:
            sections = [header, "---INPUT---", inp_text, "---OUTPUT---", out]
        return '\n'.join(sections)
    elif t == 'user_prompt':
        return f"[user_prompt] {d.get('timestamp', '')}"
    elif t == 'thinking':
        return d.get('text', '') or f"[thinking {d.get('chars', 0)}c]"
    elif t == 'system_message':
        return d.get('text', '')
    else:
        return f"[{t}]"

# Print session status after initialization
def print_session_status(session_count: int, project_filter: Optional[str] = None, mode: str = MODE_ALL) -> None:
    if session_count == 0:
        print(f"{YELLOW}No sessions found.{RESET}")
        if project_filter:
            print(f"{YELLOW}Project {project_filter} has no active Claude Code sessions.{RESET}\n")
        else:
            print(f"{YELLOW}No sessions in ~/.claude/projects{RESET}\n")
    else:
        mode_label = ''
        if mode == MODE_MAIN:
            mode_label = ' (main agent only)'
        print(f"{GREEN}Monitoring {session_count} sessions{mode_label}{RESET}")
        if project_filter:
            print(f"{CYAN}Project: {project_filter}{RESET}")
        print(f"{CYAN}Waiting for new tool calls...{RESET}\n")
