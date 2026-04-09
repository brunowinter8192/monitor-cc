# INFRASTRUCTURE
from typing import Dict, List, Optional
import os
import time

from .constants import (
    RESET, GREEN, YELLOW, WHITE, PASTEL_PURPLE, PASTEL_ORANGE,
    LIGHT_RED_BG, HOVER_BG,
    POLL_INTERVAL, INPUT_POLL_INTERVAL,
)
from .jsonl_parser import read_new_lines, parse_jsonl_lines, extract_cache_turns
from .click_handler import (
    read_keypress, setup_keyboard_input, restore_terminal,
    enable_mouse, disable_mouse, read_mouse_event,
)

cache_expand_states: Dict[tuple, bool] = {}
cache_line_map: Dict[int, tuple] = {}
cache_hover_row: Optional[int] = None
cache_scroll_offset: int = 0

_cache_jsonl_position: int = 0
_cache_turns: list = []
_cache_current_filepath = None

# FUNCTIONS

# Format token count as compact "Xk" or "X.Xk" string
def _format_k(n: int) -> str:
    if n >= 1000:
        return f"{n / 1000:.0f}k" if n >= 10000 else f"{n / 1000:.1f}k"
    return str(n)

# Format a single API call line for cache tracker (wide or compact based on pane width)
def _format_cache_call(symbol: str, cr: int, cc: int, d: int, out: int, wide: bool, req_num: int = 0, has_thinking: bool = False) -> str:
    from .formatter import shorten_tool_name as _shorten
    cc_broken = cc > cr
    bg = LIGHT_RED_BG if cc_broken else ''
    end = RESET if cc_broken else ''
    think_indicator = ' 🧠' if has_thinking else ''
    if wide:
        return f"{bg}  {symbol} REQ #{req_num}  CR: {cr:>7,}  CC: {cc:>7,}  D: {d:>5,}  ({_format_k(out)} out){think_indicator}{end}"
    return f"{bg} {symbol} #{req_num} {_format_k(cr)}/{_format_k(cc)}/{_format_k(d)} ({_format_k(out)} out){think_indicator}{end}"

# Extract first meaningful value from tool input dict for preview
def _get_tool_preview(input_data: dict) -> str:
    for key in ('file_path', 'pattern', 'command', 'subagent_type', 'prompt', 'query'):
        if key in input_data:
            return str(input_data[key]).replace('\n', ' ')
    return ''

# Format cache tracker for dedicated tokens pane with per-turn, per-API-call detail
def format_cache_tracker(turns: list, expand_states: dict = None, line_map: dict = None, hover_row: Optional[int] = None, pane_height: int = 50, pane_width: int = 80, scroll_offset: int = 0) -> str:
    from .formatter import shorten_tool_name
    if not turns:
        return f"{YELLOW}No turns yet{RESET}"

    if expand_states is None:
        expand_states = {}

    wide = pane_width >= 60
    prompt_max = min(pane_width - 15, 60) if wide else min(pane_width - 8, 30)

    all_lines = []
    line_keys = []
    request_num = 0

    if not wide:
        all_lines.append(f"{WHITE}CR/CC/D = Read/Create/Direct{RESET}")
        line_keys.append(None)

    for turn_idx, turn in enumerate(turns):
        prompt = turn.get('prompt', '').replace('\n', ' ')
        timestamp = _format_ts(turn.get('timestamp', ''))
        truncated = prompt[:prompt_max] + ('...' if len(prompt) > prompt_max else '')

        api_calls = turn.get('api_calls', [])
        thinking_calls = sum(
            1 for call in api_calls
            if any(b.get('type') == 'thinking' for b in call.get('content_blocks', []))
        )
        think_str = f" ({thinking_calls}/{len(api_calls)} 🧠)" if thinking_calls > 0 else ""
        all_lines.append(f"{PASTEL_PURPLE}Turn {turn_idx + 1} [{timestamp}]{think_str}: \"{truncated}\"{RESET}")
        line_keys.append(None)

        for call_idx, call in enumerate(api_calls):
            cr = call.get('cache_read', 0)
            cc = call.get('cache_creation', 0)
            d = call.get('direct', 0)
            out = call.get('output_tokens', 0)

            key = (turn_idx, call_idx)
            is_expanded = expand_states.get(key, False)
            symbol = '\u25bc' if is_expanded else '\u25b6'

            request_num += 1
            has_thinking = any(b.get('type') == 'thinking' for b in call.get('content_blocks', []))
            call_line = _format_cache_call(symbol, cr, cc, d, out, wide, request_num, has_thinking)
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
                        think_chars = block.get('chars', 0)
                        if think_chars and think_out:
                            all_lines.append(f"    {PASTEL_ORANGE}thinking ({think_chars:,}c, {_format_k(think_out)} out){RESET}")
                        elif think_out:
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

# Build cache turns incrementally — only reads new lines since last_position
def build_cache_turns(filepath, last_position: int, existing_turns: list):
    from .jsonl_parser import get_current_position
    lines = read_new_lines(filepath, last_position)
    new_position = get_current_position(filepath) if filepath.exists() else last_position
    if not lines:
        return existing_turns, last_position
    messages, _ = parse_jsonl_lines(lines)
    new_turns = extract_cache_turns(messages)
    if not new_turns:
        return existing_turns, new_position
    if existing_turns and new_turns[0].get('prompt') == existing_turns[-1].get('prompt'):
        # Last existing turn was incomplete (streaming) — merge its api_calls with fresh parse
        merged = dict(existing_turns[-1])
        merged_calls = list(merged.get('api_calls', []))
        for call in new_turns[0].get('api_calls', []):
            new_rid = call.get('request_id', '')
            if new_rid:
                dup_idx = next(
                    (i for i, c in enumerate(merged_calls) if c.get('request_id') == new_rid),
                    None
                )
            else:
                dup_idx = next(
                    (i for i, c in enumerate(merged_calls)
                     if c.get('cache_read') == call.get('cache_read')
                     and c.get('cache_creation') == call.get('cache_creation')
                     and c.get('direct') == call.get('direct')),
                    None
                )
            if dup_idx is None:
                merged_calls.append(call)
            else:
                # Update output_tokens in case streaming advanced
                prev = dict(merged_calls[dup_idx])
                prev['output_tokens'] = max(prev.get('output_tokens', 0), call.get('output_tokens', 0))
                merged_calls[dup_idx] = prev
        merged['api_calls'] = merged_calls
        result = existing_turns[:-1] + [merged] + new_turns[1:]
    else:
        result = existing_turns + new_turns
    return result, new_position

# Format timestamp for display (import lazily to avoid circular at module level)
def _format_ts(timestamp: str) -> str:
    from .utils import format_timestamp
    return format_timestamp(timestamp)

# Runs cache tracker display loop (for dedicated tokens tmux pane)
def run_tokens_loop() -> None:
    from . import monitor as _monitor
    global cache_expand_states, cache_line_map, cache_hover_row, cache_scroll_offset
    global _cache_jsonl_position, _cache_turns, _cache_current_filepath
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
                            key = cache_line_map.get(row)
                            if key:
                                cache_expand_states[key] = not cache_expand_states.get(key, False)
                                input_changed = True
                        elif button == 64:
                            cache_scroll_offset += 3
                            input_changed = True
                        elif button == 65:
                            cache_scroll_offset = max(0, cache_scroll_offset - 3)
                            input_changed = True
                        elif button >= 32:
                            cache_hover_row = row
                            input_changed = True

            now = time.time()
            if now - last_data_refresh >= POLL_INTERVAL:
                main_sessions = _monitor.get_main_session_files()
                filepath = main_sessions[0] if main_sessions else None

                if filepath != _cache_current_filepath:
                    # Session changed — reset all incremental state
                    _cache_current_filepath = filepath
                    _cache_jsonl_position = 0
                    _cache_turns = []
                    cache_expand_states.clear()
                    cache_scroll_offset = 0
                    cache_hover_row = None

                if filepath is not None:
                    _cache_turns, _cache_jsonl_position = build_cache_turns(
                        filepath, _cache_jsonl_position, _cache_turns
                    )

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
                output = format_cache_tracker(_cache_turns, cache_expand_states, cache_line_map, cache_hover_row, pane_height, pane_width, cache_scroll_offset)
                if output != last_output:
                    print("\033[2J\033[3J\033[H", end='', flush=True)
                    if output:
                        print(output)
                    last_output = output
            time.sleep(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()
