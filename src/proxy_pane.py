# INFRASTRUCTURE
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import hashlib
import json
import os
import time

from .constants import (
    RESET, GREEN, RED, YELLOW, WHITE, CYAN, DIM,
    PASTEL_GREEN, PASTEL_PURPLE,
    HOVER_BG,
    POLL_INTERVAL, INPUT_POLL_INTERVAL,
    KNOWN_PAYLOAD_KEYS, KNOWN_CONTENT_BLOCK_TYPES, KNOWN_TOOL_DEFINITION_KEYS, KNOWN_MESSAGE_ROLES,
)
from .token_pane import _format_k
from .click_handler import (
    read_keypress, setup_keyboard_input, restore_terminal,
    enable_mouse, disable_mouse, read_mouse_event,
)

proxy_entries: List[dict] = []
proxy_expand_states: Dict[int, bool] = {}
proxy_line_map: Dict[int, int] = {}
proxy_hover_row: Optional[int] = None
proxy_scroll_offset: int = 0
proxy_log_position: int = 0

# FUNCTIONS

# Estimate token count from char count (chars/3.5 heuristic, ~±15%)
def _chars_to_tokens(chars: int) -> int:
    return int(chars / 3.5)

# Format token estimate as compact string with ~ prefix
def _format_tok_est(chars: int) -> str:
    return f"~{_format_k(_chars_to_tokens(chars))}tok"

# Shorten full model name to family label
def _shorten_model(model: str) -> str:
    m = model.lower()
    if 'haiku' in m:
        return 'haiku'
    if 'sonnet' in m:
        return 'sonnet'
    if 'opus' in m:
        return 'opus'
    return model[:8] if model else '?'

# Derive proxy session_id from project path — matches claude_proxy_start.sh md5 hash logic
def _proxy_session_id_for_project(project_path: str) -> str:
    return hashlib.md5(project_path.encode()).hexdigest()[:8]

# Count total chars in a raw message's content (string or list of content blocks)
def _raw_msg_chars(msg: dict) -> int:
    content = msg.get('content', '')
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        total = 0
        for block in content:
            if isinstance(block, dict):
                total += len(block.get('text', ''))
        return total
    return 0

# Extract analysis fields from raw_payload into entry dict, then delete raw_payload to save memory
def _extract_raw_payload_fields(entry: dict) -> None:
    raw = entry.get('raw_payload', {})
    if raw:
        system = raw.get('system', [])
        entry['system_blocks'] = [
            {'idx': i, 'chars': len(b.get('text', '')), 'has_cc': bool(b.get('cache_control'))}
            for i, b in enumerate(system) if isinstance(b, dict)
        ] if isinstance(system, list) else []
        entry['system_total_chars'] = sum(b['chars'] for b in entry['system_blocks'])

        tools = raw.get('tools', [])
        entry['tools_total_chars'] = sum(len(json.dumps(t)) for t in tools)
        entry['tools_count'] = len(tools)
        entry['tools_hash'] = hashlib.md5(json.dumps(sorted([t.get('name', '') for t in tools])).encode()).hexdigest()[:8]
        entry['tools_names'] = [t.get('name', '') for t in tools]

        entry['thinking_config'] = raw.get('thinking', {})
        entry['output_config'] = raw.get('output_config', {})

        msgs = raw.get('messages', [])
        entry['messages_total_chars'] = sum(_raw_msg_chars(m) for m in msgs)

        schema_warnings = []
        unknown_keys = set(raw.keys()) - KNOWN_PAYLOAD_KEYS
        for k in sorted(unknown_keys):
            schema_warnings.append(f"unknown payload key: {k}")
        for msg in msgs:
            role = msg.get('role', '')
            if role and role not in KNOWN_MESSAGE_ROLES:
                schema_warnings.append(f"unknown message role: {role}")
            content = msg.get('content', [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        btype = block.get('type', '')
                        if btype and btype not in KNOWN_CONTENT_BLOCK_TYPES:
                            schema_warnings.append(f"unknown block type: {btype}")
        for tool in tools:
            if isinstance(tool, dict):
                unknown_tool_keys = set(tool.keys()) - KNOWN_TOOL_DEFINITION_KEYS
                for k in sorted(unknown_tool_keys):
                    schema_warnings.append(f"unknown tool key: {k}")
        entry['schema_warnings'] = schema_warnings

        del entry['raw_payload']

    if 'request_headers' in entry:
        del entry['request_headers']

# Read new proxy log entries for the monitored project, returning (entries, new_position)
def parse_proxy_log(project_filter: Optional[str], last_position: int) -> tuple:
    root = os.environ.get("MONITOR_CC_ROOT", "")
    if not root:
        root = str(Path(__file__).parent.parent)
    if not project_filter:
        return [], last_position
    session_id = _proxy_session_id_for_project(project_filter)
    marker_file = Path(root) / "src" / "logs" / f".proxy_session_{session_id}"
    log_id = session_id
    if marker_file.exists():
        lines = marker_file.read_text(encoding="utf-8").splitlines()
        if len(lines) >= 2 and lines[1].strip():
            log_id = lines[1].strip()
    log_file = Path(root) / "src" / "logs" / f"api_requests_{log_id}.jsonl"
    if not log_file.exists():
        return [], last_position
    with open(log_file, "r", encoding="utf-8") as f:
        f.seek(last_position)
        content = f.read()
    if not content:
        return [], last_position
    lines = [ln for ln in content.split("\n") if ln.strip()]
    entries = []
    for line in lines:
        try:
            entry = json.loads(line)
            _extract_raw_payload_fields(entry)
            entries.append(entry)
        except json.JSONDecodeError:
            pass
    return entries, log_file.stat().st_size

# Format proxy pane with API request entries, expand/collapse, scroll, hover
def format_proxy_block(entries: list, expand_states: dict = None, line_map: dict = None, hover_row: Optional[int] = None, pane_height: int = 50, pane_width: int = 80, scroll_offset: int = 0) -> str:
    from .utils import format_timestamp

    LEGEND = [
        f"{DIM}▶/▼ expand  ⚠ cache break  🔧 mods  BP: breakpoints  ~tok: chars/3.5 ±15%{RESET}",
        f"{DIM}sys=system  tools=tool defs  msgs=messages{RESET}",
    ]
    LEGEND_ROWS = len(LEGEND)

    if not entries:
        return '\n'.join(LEGEND) + f"\n{YELLOW}No API requests logged yet{RESET}"

    if expand_states is None:
        expand_states = {}

    all_lines = []
    line_keys = []

    for entry_idx, entry in enumerate(entries):
        timestamp = format_timestamp(entry.get('timestamp', ''))[:5]  # HH:MM only
        model = _shorten_model(entry.get('model', '?'))
        msg_count = entry.get('message_count', 0)
        input_chars = entry.get('total_input_chars', 0)
        cache_bp = entry.get('cache_breakpoints', [])
        diff = entry.get('diff_from_prev', {})
        diff_summary = diff.get('summary', '')
        first_diff = diff.get('first_diff_index', -1)
        mods = entry.get('modifications', [])

        chars_str = _format_k(input_chars)
        bp_count = len(cache_bp)
        mods_count = len(mods)
        is_expanded = expand_states.get(entry_idx, False)
        symbol = '\u25bc' if is_expanded else '\u25b6'

        # Determine cache warnings first (for header indicator)
        model_family = "haiku" if "haiku" in entry.get('model', '').lower() else "opus"
        prev_entry = None
        for _i in range(entry_idx - 1, -1, -1):
            _prev_model = entries[_i].get('model', '')
            _prev_family = "haiku" if "haiku" in _prev_model.lower() else "opus"
            if _prev_family == model_family:
                prev_entry = entries[_i]
                break

        warn_symbols = []
        warn_details = []
        if prev_entry is not None:
            if entry.get('tools_hash') and prev_entry.get('tools_hash') and entry.get('tools_hash') != prev_entry.get('tools_hash'):
                warn_symbols.append(f"{RED}⚠T{RESET}")
                curr_names = set(entry.get('tools_names', []))
                prev_names = set(prev_entry.get('tools_names', []))
                added = sorted(curr_names - prev_names)
                removed = sorted(prev_names - curr_names)
                warn_details.append([f"    {GREEN}+{n}{RESET}" for n in added] + [f"    {RED}-{n}{RESET}" for n in removed])
            if entry.get('system_total_chars') is not None and prev_entry.get('system_total_chars') is not None and entry.get('system_total_chars') != prev_entry.get('system_total_chars'):
                warn_symbols.append(f"{RED}⚠S{RESET}")
                old_c = prev_entry['system_total_chars']
                new_c = entry['system_total_chars']
                delta = new_c - old_c
                warn_details.append([f"    {DIM}sys: {_format_k(old_c)} → {_format_k(new_c)} ({delta:+,}){RESET}"])
            msgs_modified = diff.get('messages_modified', 0)
            if msgs_modified > 0 and first_diff >= 0 and cache_bp:
                if first_diff < min(cache_bp):
                    warn_symbols.append(f"{RED}⚠M{RESET}")
                    warn_details.append([f"    {DIM}first change at msg #{first_diff}  {diff_summary}{RESET}"])

        status_str = '  '.join(warn_symbols) if warn_symbols else f"{PASTEL_GREEN}✓{RESET}"
        mods_str = f"  {YELLOW}🔧{mods_count}{RESET}" if mods_count > 0 else ''

        header = f"{WHITE}{symbol} [{timestamp}] #{entry_idx + 1}  {model}  {msg_count}msg  {chars_str}  BP:{bp_count}{mods_str}  {status_str}{RESET}"
        all_lines.append(header)
        line_keys.append(entry_idx)

        sys_chars = entry.get('system_total_chars', entry.get('system_prompt_chars', 0))
        tools_chars = entry.get('tools_total_chars', entry.get('tools_chars', 0))
        msgs_chars = entry.get('messages_total_chars', 0)
        info_parts = [
            f"sys:{_format_k(sys_chars)}({_format_tok_est(sys_chars)})",
            f"tools:{_format_k(tools_chars)}({_format_tok_est(tools_chars)})",
            f"msgs:{_format_k(msgs_chars)}({_format_tok_est(msgs_chars)})",
        ]
        all_lines.append(f"  {DIM}{'  '.join(info_parts)}{RESET}")
        line_keys.append(None)

        warn_key = (entry_idx, 'warnings')
        is_warn_expanded = expand_states.get(warn_key, False)

        if warn_symbols or diff_summary:
            warn_symbol = '\u25bc' if is_warn_expanded else '\u25b6'
            warn_str = '  '.join(warn_symbols)
            if diff_summary and warn_str:
                all_lines.append(f"  {warn_symbol} {warn_str}  {YELLOW}{diff_summary}{RESET}")
            elif warn_str:
                all_lines.append(f"  {warn_symbol} {warn_str}")
            else:
                all_lines.append(f"  {YELLOW}{diff_summary}{RESET}")
            line_keys.append(warn_key if warn_symbols else None)
            if is_warn_expanded and warn_symbols:
                for detail_lines in warn_details:
                    for dl in detail_lines:
                        all_lines.append(dl)
                        line_keys.append(None)

        schema_warnings = entry.get('schema_warnings', [])
        if schema_warnings:
            schema_key = (entry_idx, 'schema')
            is_schema_expanded = expand_states.get(schema_key, False)
            schema_symbol = '\u25bc' if is_schema_expanded else '\u25b6'
            all_lines.append(f"  {schema_symbol} {RED}⚠ SCHEMA DRIFT ({len(schema_warnings)}){RESET}")
            line_keys.append(schema_key)
            if is_schema_expanded:
                for sw in schema_warnings:
                    all_lines.append(f"    {DIM}{sw}{RESET}")
                    line_keys.append(None)

        if is_expanded:
            all_lines.append(f"  {DIM}{'─' * min(40, pane_width - 4)}{RESET}")
            line_keys.append(None)

            messages = entry.get('messages', [])
            stripped_indices = set()
            for _idx, _msg in enumerate(messages):
                if _msg.get('type', '') == 'system-reminder':
                    _preview = _msg.get('content_preview', '')
                    if 'stripped_task_tools_nag' in mods and 'task tools haven' in _preview:
                        stripped_indices.add(_idx)
                    if 'removed_plan_mode_sr' in mods and 'Plan mode is active' in _preview:
                        stripped_indices.add(_idx)

            start_idx = max(0, first_diff) if first_diff >= 0 else 0
            if start_idx > 0:
                all_lines.append(f"  {DIM}... [0-{start_idx - 1}] unchanged ({start_idx} messages){RESET}")
                line_keys.append(None)
            for msg_idx, msg in enumerate(messages[start_idx:], start=start_idx):
                role = msg.get('role', '?')[:4]
                msg_type = msg.get('type', 'text')
                chars = msg.get('chars', 0)
                has_cc = msg.get('has_cache_control', False)
                cc_marker = f"  {PASTEL_GREEN}CC ●{RESET}" if has_cc else ''

                chars_fmt = f"{chars:,}c"
                msg_key = (entry_idx, 'msg', msg_idx)
                is_msg_expanded = expand_states.get(msg_key, False)
                msg_symbol = '\u25bc' if is_msg_expanded else '\u25b6'
                is_stripped = msg_idx in stripped_indices
                if is_stripped:
                    all_lines.append(f"  {DIM}{msg_symbol} [{msg_idx:3d}] {role:<8} {msg_type:<20} {chars_fmt:>8}{RESET}{cc_marker}  {YELLOW}[STRIPPED]{RESET}")
                else:
                    color = PASTEL_GREEN if has_cc else WHITE
                    all_lines.append(f"  {color}{msg_symbol} [{msg_idx:3d}] {role:<8} {msg_type:<20} {chars_fmt:>8}{RESET}{cc_marker}")
                line_keys.append(msg_key)

                if is_msg_expanded:
                    preview = msg.get('content_preview', '')
                    wrap_width = max(20, pane_width - 6)
                    if preview:
                        for raw_line in preview.split('\n'):
                            if not raw_line:
                                all_lines.append(f"      {DIM}{RESET}")
                                line_keys.append(None)
                                continue
                            for line_start in range(0, len(raw_line), wrap_width):
                                chunk = raw_line[line_start:line_start + wrap_width]
                                all_lines.append(f"      {DIM}{chunk}{RESET}")
                                line_keys.append(None)
                    else:
                        all_lines.append(f"      {DIM}(no preview){RESET}")
                        line_keys.append(None)

        all_lines.append('')
        line_keys.append(None)

    while all_lines and all_lines[-1] == '':
        all_lines.pop()
        line_keys.pop()

    # Reserve LEGEND_ROWS lines at top — content viewport is smaller
    viewport_lines = max(1, pane_height - 1 - LEGEND_ROWS)
    max_scroll = max(0, len(all_lines) - viewport_lines)
    clamped_offset = min(scroll_offset, max_scroll)
    start = max(0, len(all_lines) - viewport_lines - clamped_offset)
    end = start + viewport_lines

    visible_lines = all_lines[start:end]
    visible_keys = line_keys[start:end]

    # line_map rows start after legend (rows 1..LEGEND_ROWS are legend)
    if line_map is not None:
        line_map.clear()
        for row_idx, key in enumerate(visible_keys):
            if key is not None:
                line_map[row_idx + 1 + LEGEND_ROWS] = key

    result_lines = list(LEGEND)
    for row_offset, line in enumerate(visible_lines):
        row = row_offset + 1 + LEGEND_ROWS
        key = visible_keys[row_offset]
        if key is not None and hover_row is not None and row == hover_row:
            result_lines.append(f"{HOVER_BG}{line}{RESET}")
        else:
            result_lines.append(line)

    return '\n'.join(result_lines)

# Runs proxy pane display loop — reads api_requests.jsonl, shows expandable entries
def run_proxy_loop() -> None:
    from . import monitor as _monitor
    global proxy_entries, proxy_expand_states, proxy_line_map, proxy_hover_row, proxy_scroll_offset, proxy_log_position
    session_start_ts = _monitor._get_session_start_ts()
    if session_start_ts is None:
        session_start_ts = datetime.utcnow().isoformat() + 'Z'
    current_main_session = _monitor._get_newest_main_session()
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
                            key = proxy_line_map.get(row)
                            if key is not None:
                                proxy_expand_states[key] = not proxy_expand_states.get(key, False)
                                input_changed = True
                        elif button == 64:
                            proxy_scroll_offset += 3
                            input_changed = True
                        elif button == 65:
                            proxy_scroll_offset = max(0, proxy_scroll_offset - 3)
                            input_changed = True
                        elif button >= 32:
                            proxy_hover_row = row
                            input_changed = True

            now = time.time()
            if now - last_data_refresh >= POLL_INTERVAL:
                newest = _monitor._get_newest_main_session()
                if newest != current_main_session and newest is not None:
                    current_main_session = newest
                    session_start_ts = _monitor._get_session_start_ts()
                    if session_start_ts is None:
                        session_start_ts = datetime.utcnow().isoformat() + 'Z'
                    proxy_entries.clear()
                    proxy_expand_states.clear()
                    proxy_line_map.clear()
                    proxy_log_position = 0
                    proxy_scroll_offset = 0
                    proxy_hover_row = None
                    input_changed = True
                new_entries, proxy_log_position = parse_proxy_log(_monitor.active_project_filter, proxy_log_position)
                filtered = [e for e in new_entries if e.get('timestamp', '') >= session_start_ts]
                proxy_entries.extend(filtered)
                last_data_refresh = now
                input_changed = True

            if input_changed:
                try:
                    term = os.get_terminal_size()
                    pane_height = term.lines - 1
                    pane_width = term.columns
                except OSError:
                    pane_height = 50
                    pane_width = 80
                output = format_proxy_block(proxy_entries, proxy_expand_states, proxy_line_map, proxy_hover_row, pane_height, pane_width, proxy_scroll_offset)
                if output != last_output:
                    print("\033[2J\033[3J\033[H", end='', flush=True)
                    if output:
                        print(output)
                    last_output = output
            time.sleep(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()
