# INFRASTRUCTURE
import re
from typing import Optional

# From utils.py: Timestamp formatting
from .utils import format_timestamp
# From constants.py: Colors and config values
from .constants import GREEN, BLUE, YELLOW, CYAN, RED, PASTEL_BLUE, PASTEL_PURPLE, LIGHT_RED_BG, PASTEL_ORANGE, WHITE, ORANGE, DIM, RESET, LONG_OUTPUT_THRESHOLD, HOVER_BG, HOOK_EVENT_CATEGORIES

INDENT = '  '

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

# Format token count as compact "Xk" or "X.Xk" string
def _format_k(n: int) -> str:
    if n >= 1000:
        return f"{n / 1000:.0f}k" if n >= 10000 else f"{n / 1000:.1f}k"
    return str(n)
SCORE_PATTERN = re.compile(r'^-+ Result \d+ \(score: [\d.]+\) -+$')

# ORCHESTRATOR
def format_tool_call(tool_name: str, input_data: dict, output_data: str, tool_use_id: str, timestamp: str, call_number: int, is_subagent: bool = False, system_reminders: list = None, is_error: bool = False) -> str:
    request = format_request(tool_name, input_data, tool_use_id, timestamp, call_number, is_subagent)
    response = format_response(tool_name, output_data, tool_use_id, timestamp, call_number, is_subagent, system_reminders, is_error)
    return combine_request_response(request, response)

# FUNCTIONS

# Combine request and response sections with spacing
def combine_request_response(request: str, response: str) -> str:
    return f"{request}\n\n{response}"

# Format REQUEST header with color based on agent type
def format_request(tool_name: str, input_data: dict, tool_use_id: str, timestamp: str, call_number: int, is_subagent: bool = False) -> str:
    time_str = format_timestamp(timestamp)
    color = BLUE if is_subagent else GREEN
    header = f"{color}[{time_str}] REQUEST #{call_number} → {tool_name}{RESET}"

    if tool_name == 'TodoWrite' and 'todos' in input_data:
        params = format_todo_list(input_data['todos'])
    elif tool_name == 'Task' and 'subagent_type' in input_data:
        params = format_task_parameters(input_data)
    else:
        params = format_parameters(input_data)

    return f"{header}\n{params}"

# Format RESPONSE header with color based on agent type
def format_response(tool_name: str, output_data: str, tool_use_id: str, timestamp: str, call_number: int, is_subagent: bool = False, system_reminders: list = None, is_error: bool = False) -> str:
    time_str = format_timestamp(timestamp)

    if is_error:
        # RED imported from constants via INFRASTRUCTURE
        header = f"{RED}[{time_str}] RESPONSE #{call_number} ← {tool_name} [ERROR]{RESET}"
        content = format_error_output(output_data)
    else:
        color = BLUE if is_subagent else GREEN
        header = f"{color}[{time_str}] RESPONSE #{call_number} ← {tool_name}{RESET}"
        content = format_output(output_data)

    reminders = format_system_reminders(system_reminders)

    parts = [header, content]
    if reminders:
        parts.append(reminders)
    return '\n'.join(parts)

# Format todo list with colored status and icons
def format_todo_list(todos: list) -> str:
    if not todos:
        return f"{INDENT}(no todos)"

    lines = []
    for idx, todo in enumerate(todos, 1):
        status = todo.get('status', 'pending')
        content = todo.get('content', '(no content)')

        icon = get_status_icon(status)
        color = get_status_color(status)
        status_label = status.upper().replace('_', ' ')

        lines.append(f"\n{INDENT}TODO #{idx} - {status_label} {icon}")
        lines.append(f"{INDENT}{INDENT}{color}{content}{RESET}")

    return '\n'.join(lines)

# Format input parameters with 2-space indentation
def format_parameters(params: dict) -> str:
    lines = []
    for key, value in params.items():
        formatted_value = format_value(value)
        lines.append(f"{INDENT}{key}: {formatted_value}")
    return '\n'.join(lines)

# Format Task parameters with highlighted subagent_type
def format_task_parameters(params: dict) -> str:
    lines = []
    for key, value in params.items():
        if key == 'subagent_type':
            lines.append(f"{INDENT}{key}: {CYAN}{value}{RESET}")
        else:
            formatted_value = format_value(value)
            lines.append(f"{INDENT}{key}: {formatted_value}")
    return '\n'.join(lines)

# Format output content with 2-space indentation and red background for long outputs
def format_output(content: str) -> str:
    if not content:
        return f"{INDENT}(empty)"

    is_long = len(content) >= LONG_OUTPUT_THRESHOLD

    lines = content.split('\n')
    formatted_lines = []
    for line in lines:
        if SCORE_PATTERN.match(line.strip()):
            formatted_lines.append(f"{INDENT}{GREEN}{line}{RESET}")
        else:
            formatted_lines.append(f"{INDENT}{line}")
    result = '\n'.join(formatted_lines)

    if is_long:
        return f"{LIGHT_RED_BG}{result}{RESET}"
    return result

# Format error output content in red
def format_error_output(content: str) -> str:
    if not content:
        return f"{INDENT}{RED}(empty){RESET}"

    lines = content.split('\n')
    formatted_lines = '\n'.join(f"{INDENT}{RED}{line}{RESET}" for line in lines)
    return formatted_lines

# Format system reminders with pastel blue color
def format_system_reminders(reminders: list) -> str:
    if not reminders:
        return ''
    lines = []
    for reminder in reminders:
        for line in reminder.split('\n'):
            if line.strip():
                lines.append(f"{INDENT}{PASTEL_BLUE}{line}{RESET}")
    return '\n'.join(lines)

# Format parameter value preserving newlines for multiline strings
def format_value(value) -> str:
    if isinstance(value, str) and '\n' in value:
        lines = value.split('\n')
        return '\n' + '\n'.join(f"{INDENT}{line}" for line in lines)
    elif isinstance(value, dict):
        return str(value)
    elif isinstance(value, list):
        return str(value)
    else:
        return str(value)

# Get status icon for todo item
def get_status_icon(status: str) -> str:
    icons = {
        'completed': '[X]',
        'in_progress': '[>]',
        'pending': '[-]'
    }
    return icons.get(status, '[-]')

# Get status color for todo item
def get_status_color(status: str) -> str:
    colors = {
        'completed': GREEN,
        'in_progress': YELLOW,
        'pending': RESET
    }
    return colors.get(status, RESET)

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

# Format single hook event for hooks pane display, color-coded by event category
def format_hook_event(timestamp: str, hook_event: str, hook_script: str, output: str) -> str:
    time_str = format_timestamp(timestamp)
    category = HOOK_EVENT_CATEGORIES.get(hook_event, 'tool')
    color = _HOOK_CATEGORY_COLORS.get(category, PASTEL_PURPLE)
    header = f"{color}[{time_str}] {hook_event} | {hook_script}{RESET}"
    if output:
        lines = output.split('\n')
        formatted_lines = '\n'.join(f"{INDENT}{color}{line}{RESET}" for line in lines)
        return f"{header}\n{formatted_lines}"
    return header

# Format system reminder for Hooks pane display, attributed to triggering tool
def format_system_reminder_for_hooks(timestamp: str, reminder_text: str, tool_name: str) -> str:
    time_str = format_timestamp(timestamp)
    header = f"{PASTEL_BLUE}[{time_str}] SYSTEM REMINDER \u2190 {tool_name}{RESET}"
    clean_text = reminder_text.replace('\\n', '\n')
    lines = clean_text.split('\n')
    formatted_lines = '\n'.join(f"{INDENT}{PASTEL_BLUE}{line}{RESET}" for line in lines if line.strip())
    return f"{header}\n{formatted_lines}" if formatted_lines else header

_REMINDER_JUNK_PATTERN = re.compile(r'^[\.\*\?\(\)\[\]\+\|\\^$\s]+$')

# Check if reminder text is a real reminder (not a regex snippet or too short)
def _is_valid_reminder(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 20:
        return False
    if _REMINDER_JUNK_PATTERN.match(stripped):
        return False
    return True

# Build hooks pane display item dict for a hook log entry
def build_hook_display_item(entry: dict) -> dict:
    time_str = format_timestamp(entry.get('timestamp', ''))
    category = HOOK_EVENT_CATEGORIES.get(entry.get('hook_event', ''), 'tool')
    color = _HOOK_CATEGORY_COLORS.get(category, PASTEL_PURPLE)
    return {
        'type': 'hook',
        'timestamp': entry.get('timestamp', ''),
        'time_str': time_str,
        'hook_event': entry.get('hook_event', ''),
        'hook_script': entry.get('hook_script', ''),
        'detail': entry.get('output', ''),
        'color': color,
        'expanded': False,
    }

# Build hooks pane display item dict for a system reminder, returns None if invalid
def build_reminder_display_item(timestamp: str, reminder_text: str, tool_name: str) -> Optional[dict]:
    clean_text = reminder_text.replace('\\n', '\n')
    if not _is_valid_reminder(clean_text):
        return None
    time_str = format_timestamp(timestamp)
    return {
        'type': 'reminder',
        'timestamp': timestamp,
        'time_str': time_str,
        'tool_name': tool_name,
        'detail': clean_text,
        'color': PASTEL_BLUE,
        'expanded': False,
    }

# Render hooks pane items with [+]/[-] expand/collapse, hover highlight, scrolling
def format_hooks_block(items: list, line_map: dict, hover_item_idx: Optional[int], scroll_offset: int) -> tuple:
    if not items:
        return ('', 0)
    all_lines = []
    item_idx_at: dict = {}
    for item_idx, item in enumerate(items):
        toggle = "[-]" if item.get('expanded') else "[+]"
        color = item.get('color', PASTEL_PURPLE)
        time_str = item.get('time_str', '')
        if item['type'] == 'hook':
            hook_event = item.get('hook_event', '')
            hook_script = item.get('hook_script', '')
            header = f"{color}{toggle} [{time_str}] {hook_event} | {hook_script}{RESET}"
        else:
            tool_name = item.get('tool_name', '')
            header = f"{PASTEL_BLUE}{toggle} [{time_str}] SYSTEM REMINDER \u2190 {tool_name}{RESET}"
        line_idx = len(all_lines)
        all_lines.append(header)
        item_idx_at[line_idx] = item_idx
        if item.get('expanded'):
            detail = item.get('detail', '')
            if detail:
                for line in detail.split('\n'):
                    if line.strip():
                        all_lines.append(f"    {color}{line}{RESET}")
    total_lines = len(all_lines)
    visible = all_lines[scroll_offset:]
    if line_map is not None:
        line_map.clear()
        for screen_row_0, content_idx in enumerate(range(scroll_offset, total_lines)):
            screen_row = screen_row_0 + 1
            if content_idx in item_idx_at:
                line_map[screen_row] = item_idx_at[content_idx]
    output_lines = []
    for screen_row_0, line in enumerate(visible):
        content_idx = scroll_offset + screen_row_0
        if hover_item_idx is not None and item_idx_at.get(content_idx) == hover_item_idx:
            line = f"{HOVER_BG}{line}{RESET}"
        output_lines.append(line)
    return ('\n'.join(output_lines), total_lines)

# Format system message from JSONL for display
def format_system_message(timestamp: str, text: str) -> str:
    time_str = format_timestamp(timestamp)
    header = f"{CYAN}[{time_str}] SYSTEM MESSAGE{RESET}"
    body_lines = text.split('\n')
    formatted_body = '\n'.join(f"{INDENT}{line}" for line in body_lines if line.strip())
    return f"{header}\n{formatted_body}" if formatted_body else header

# Format user media item (image or document)
def format_user_media(media_item: dict) -> str:
    time_str = format_timestamp(media_item.get('timestamp', ''))
    media_type = media_item.get('type', 'unknown')
    mime_type = media_item.get('media_type', 'unknown')

    if media_type == 'image':
        label = f"[IMAGE: {mime_type}]"
    elif media_type == 'document':
        label = f"[DOC: {mime_type}]"
    else:
        label = f"[MEDIA: {mime_type}]"

    return f"{PASTEL_PURPLE}[{time_str}] USER PROMPT {label}{RESET}"

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
    return f"{PASTEL_ORANGE}[{time_str}] THINKING: {thinking_text}{RESET}"

# Format unknown JSONL type warning for warnings pane
def format_unknown_type_warning(msg_type: str, count: int) -> str:
    return f"{INDENT}{YELLOW}[!] Unknown JSONL type: {msg_type} (seen {count}x){RESET}"

# Format a single API call line for cache tracker (wide or compact based on pane width)
def _format_cache_call(symbol: str, cr: int, cc: int, d: int, out: int, wide: bool) -> str:
    cc_broken = cc > cr
    bg = LIGHT_RED_BG if cc_broken else ''
    end = RESET if cc_broken else ''
    if wide:
        return f"{bg}  {symbol} CR: {cr:>7,}  CC: {cc:>7,}  D: {d:>5,}  ({_format_k(out)} out){end}"
    return f"{bg} {symbol} {_format_k(cr)}/{_format_k(cc)}/{_format_k(d)} ({_format_k(out)} out){end}"

# Extract first meaningful value from tool input dict for preview
def _get_tool_preview(input_data: dict) -> str:
    for key in ('file_path', 'pattern', 'command', 'subagent_type', 'prompt', 'query'):
        if key in input_data:
            return str(input_data[key]).replace('\n', ' ')
    return ''

# Format cache tracker for dedicated tokens pane with per-turn, per-API-call detail
def format_cache_tracker(turns: list, expand_states: dict = None, line_map: dict = None, hover_row: Optional[int] = None, pane_height: int = 50, pane_width: int = 80, scroll_offset: int = 0) -> str:
    if not turns:
        return f"{YELLOW}No turns yet{RESET}"

    if expand_states is None:
        expand_states = {}

    wide = pane_width >= 60
    prompt_max = min(pane_width - 15, 60) if wide else min(pane_width - 8, 30)

    all_lines = []
    line_keys = []

    if not wide:
        all_lines.append(f"{WHITE}CR/CC/D = Read/Create/Direct{RESET}")
        line_keys.append(None)

    for turn_idx, turn in enumerate(turns):
        prompt = turn.get('prompt', '').replace('\n', ' ')
        timestamp = format_timestamp(turn.get('timestamp', ''))
        truncated = prompt[:prompt_max] + ('...' if len(prompt) > prompt_max else '')

        all_lines.append(f"{PASTEL_PURPLE}Turn {turn_idx + 1} [{timestamp}]: \"{truncated}\"{RESET}")
        line_keys.append(None)

        for call_idx, call in enumerate(turn.get('api_calls', [])):
            cr = call.get('cache_read', 0)
            cc = call.get('cache_creation', 0)
            d = call.get('direct', 0)
            out = call.get('output_tokens', 0)

            key = (turn_idx, call_idx)
            is_expanded = expand_states.get(key, False)
            symbol = '\u25bc' if is_expanded else '\u25b6'

            call_line = _format_cache_call(symbol, cr, cc, d, out, wide)
            all_lines.append(call_line)
            line_keys.append(key)

            if is_expanded:
                for block in call.get('content_blocks', []):
                    bt = block.get('type', '')
                    if bt == 'tool_use':
                        tool_name = block.get('tool_name', 'Unknown')
                        if tool_name.startswith('mcp__'):
                            tool_name = shorten_tool_name(tool_name)
                        preview = _get_tool_preview(block.get('preview', {}))
                        if preview:
                            all_lines.append(f"    {GREEN}{tool_name}: {preview[:50]}{RESET}")
                        else:
                            all_lines.append(f"    {GREEN}{tool_name}{RESET}")
                    elif bt == 'thinking':
                        think_out = block.get('output_tokens')
                        if think_out:
                            all_lines.append(f"    {PASTEL_ORANGE}thinking ({_format_k(think_out)} out){RESET}")
                        else:
                            all_lines.append(f"    {PASTEL_ORANGE}thinking{RESET}")
                    elif bt == 'text':
                        preview = block.get('preview', '')
                        if preview:
                            all_lines.append(f"    {WHITE}text: {preview}{RESET}")
                        else:
                            all_lines.append(f"    {WHITE}text{RESET}")
                    line_keys.append(None)

        all_lines.append('')
        line_keys.append(None)

    while all_lines and all_lines[-1] == '':
        all_lines.pop()
        line_keys.pop()

    viewport_lines = pane_height - 1
    max_scroll = max(0, len(all_lines) - viewport_lines)
    clamped_offset = min(scroll_offset, max_scroll)
    start = max(0, len(all_lines) - viewport_lines - clamped_offset)
    end = start + viewport_lines

    sticky_header = None
    if start > 0:
        for i in range(start, -1, -1):
            if line_keys[i] is None and 'Turn ' in all_lines[i]:
                raw = all_lines[i]
                if len(raw) > pane_width + 20:
                    import re as _re
                    m = _re.search(r'Turn \d+ \[[^\]]+\]', raw)
                    if m:
                        sticky_header = f"{PASTEL_PURPLE}{m.group(0)}...{RESET}"
                    else:
                        sticky_header = raw
                else:
                    sticky_header = raw
                break

    visible_lines = all_lines[start:end]
    visible_keys = line_keys[start:end]

    if line_map is not None:
        line_map.clear()
        offset = 2 if sticky_header else 1
        for row_idx, key in enumerate(visible_keys):
            if key is not None:
                line_map[row_idx + offset] = key

    result_lines = []
    if sticky_header:
        result_lines.append(sticky_header)

    for row_offset, line in enumerate(visible_lines):
        row = row_offset + (2 if sticky_header else 1)
        key = visible_keys[row_offset]
        if key is not None and hover_row is not None and row == hover_row:
            result_lines.append(f"{HOVER_BG}{line}{RESET}")
        else:
            result_lines.append(line)

    return '\n'.join(result_lines)

# Format workers pane with optional expand/collapse showing cache tracker per worker
def format_workers_block(workers: list, expand_states: dict = None, worker_turns: dict = None, line_map: dict = None, hover_row: Optional[int] = None, scroll_offsets: dict = None, cache_expand_states: dict = None, cache_line_map: dict = None, frozen: bool = False) -> str:
    freeze_indicator = f" {YELLOW}[FROZEN]{RESET}" if frozen else f" {CYAN}[LIVE]{RESET}"

    if not workers:
        return f"{WHITE}Workers{RESET}{freeze_indicator}\n\n{YELLOW}No active workers{RESET}"

    if expand_states is None:
        expand_states = {}
    if worker_turns is None:
        worker_turns = {}

    status_colors = {
        'working': GREEN,
        'idle': YELLOW,
        'exited': RED,
        'unknown': WHITE,
    }

    lines = []
    current_line = 1

    lines.append(f"{WHITE}Workers{RESET}{freeze_indicator}")
    lines.append('')
    current_line += 2

    if line_map is not None:
        line_map.clear()
    if cache_line_map is not None:
        cache_line_map.clear()

    for idx, w in enumerate(workers, 1):
        status = w.get('status', 'unknown')
        sc = status_colors.get(status, WHITE)
        name = w.get('name', '?')
        spawned = w.get('spawned', '')
        purpose = w.get('purpose', '')
        is_expanded = expand_states.get(name, False)
        toggle_symbol = "[-]" if is_expanded else "[+]"

        if line_map is not None:
            line_map[current_line] = name

        spawned_str = f"  {WHITE}{spawned}{RESET}" if spawned else ''
        model = w.get('model', '')
        model_str = f"  {PASTEL_PURPLE}{model}{RESET}" if model else ''
        tokens = w.get('tokens', {})
        tok_in = tokens.get('input', 0)
        tok_out = tokens.get('output', 0)
        tokens_str = f"  {WHITE}{_format_k(tok_in)}in {_format_k(tok_out)}out{RESET}" if tok_in or tok_out else ''
        header_line = f"{toggle_symbol} {CYAN}[{idx}] {name}{RESET}  {sc}{status.upper()}{RESET}{spawned_str}{model_str}{tokens_str}"
        if hover_row is not None and current_line == hover_row:
            header_line = f"{HOVER_BG}{header_line}{RESET}"
        lines.append(header_line)
        current_line += 1

        if purpose:
            if is_expanded:
                purpose_line = f"{INDENT}{WHITE}{purpose}{RESET}"
                if line_map is not None:
                    line_map[current_line] = name
            else:
                truncated = purpose[:60] + ('...' if len(purpose) > 60 else '')
                purpose_line = f"{INDENT}{WHITE}{truncated}{RESET}"
            lines.append(purpose_line)
            current_line += 1

        if is_expanded:
            turns = worker_turns.get(name, [])
            if not turns:
                if line_map is not None:
                    line_map[current_line] = name
                lines.append(f"{INDENT}{YELLOW}(no token data yet){RESET}")
                current_line += 1
            else:
                scroll_offset = (scroll_offsets or {}).get(name, 0)
                per_worker_expand = (cache_expand_states or {}).get(name, {})
                try:
                    import os as _os
                    pane_width = _os.get_terminal_size().columns
                except OSError:
                    pane_width = 80
                if cache_line_map is not None:
                    temp_clm: dict = {}
                    cache_output = format_cache_tracker(turns, per_worker_expand, temp_clm, None, 15, pane_width - 2, scroll_offset)
                    cache_start = current_line
                    for rel_row, key in temp_clm.items():
                        cache_line_map[rel_row + cache_start - 1] = (name, key[0], key[1])
                else:
                    cache_output = format_cache_tracker(turns, per_worker_expand, None, None, 15, pane_width - 2, scroll_offset)
                for cl in cache_output.split('\n'):
                    lines.append(f"  {cl}")
                    if line_map is not None:
                        line_map[current_line] = name
                    current_line += 1

        lines.append('')
        current_line += 1

    if lines and lines[-1] == '':
        lines.pop()
    return '\n'.join(lines)

# Shorten MCP tool names for display (mcp__plugin_xxx_yyy__tool_name → tool_name)
def shorten_tool_name(name: str) -> str:
    if name.startswith('mcp__'):
        parts = name.split('__')
        if len(parts) >= 3:
            return parts[-1]
    return name

