# INFRASTRUCTURE
from typing import Optional
from .constants import RESET, GREEN, YELLOW, WHITE, PASTEL_PURPLE, PASTEL_ORANGE, LIGHT_RED_BG, HOVER_BG, DIM
# FUNCTIONS
# Format token count as compact "Xk" or "X.Xk" string
def _format_k(n: int) -> str:
    if n >= 1000:
        return f"{n / 1000:.0f}k" if n >= 10000 else f"{n / 1000:.1f}k"
    return str(n)

# Format a single API call line for cache tracker (wide or compact based on pane width)
def _format_cache_call(symbol: str, cr: int, cc: int, d: int, out: int, wide: bool, req_num: int = 0, has_thinking: bool = False) -> str:
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

# Format timestamp for display (import lazily to avoid circular at module level)
def _format_ts(timestamp: str) -> str:
    from .utils import format_timestamp
    return format_timestamp(timestamp)

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
                wrap_width = max(20, pane_width - 8)
                for block in call.get('content_blocks', []):
                    bt = block.get('type', '')
                    if bt == 'tool_use':
                        tool_name = block.get('tool_name', 'Unknown')
                        if tool_name.startswith('mcp__'):
                            tool_name = shorten_tool_name(tool_name)
                        input_data = block.get('preview', {})
                        if isinstance(input_data, dict) and input_data:
                            all_lines.append(f"    {GREEN}{tool_name}{RESET}")
                            line_keys.append(None)
                            for k, v in input_data.items():
                                val_str = str(v).replace('\n', ' ') if not isinstance(v, str) else v
                                header = f"      {k}: "
                                remaining_width = max(20, wrap_width - len(header) + 6)
                                for raw_line in val_str.split('\n'):
                                    if not raw_line:
                                        all_lines.append(f"      {DIM}{RESET}")
                                        line_keys.append(None)
                                        continue
                                    first_chunk = True
                                    for chunk_start in range(0, max(1, len(raw_line)), remaining_width):
                                        chunk = raw_line[chunk_start:chunk_start + remaining_width]
                                        if first_chunk:
                                            all_lines.append(f"      {GREEN}{k}: {chunk}{RESET}")
                                            first_chunk = False
                                        else:
                                            all_lines.append(f"      {GREEN}{' ' * (len(k) + 2)}{chunk}{RESET}")
                                        line_keys.append(None)
                        else:
                            all_lines.append(f"    {GREEN}{tool_name}{RESET}")
                            line_keys.append(None)
                    elif bt == 'thinking':
                        think_out = block.get('output_tokens')
                        think_chars = block.get('chars', 0)
                        if think_chars and think_out:
                            all_lines.append(f"    {PASTEL_ORANGE}thinking ({think_chars:,}c, {_format_k(think_out)} out){RESET}")
                        elif think_out:
                            all_lines.append(f"    {PASTEL_ORANGE}thinking ({_format_k(think_out)} out){RESET}")
                        else:
                            all_lines.append(f"    {PASTEL_ORANGE}thinking{RESET}")
                        line_keys.append(None)
                    elif bt == 'text':
                        preview = block.get('preview', '')
                        if preview:
                            first = True
                            for raw_line in preview.split('\n'):
                                if not raw_line:
                                    all_lines.append(f"    {WHITE}{RESET}")
                                    line_keys.append(None)
                                    continue
                                for chunk_start in range(0, len(raw_line), wrap_width):
                                    chunk = raw_line[chunk_start:chunk_start + wrap_width]
                                    if first:
                                        all_lines.append(f"    {WHITE}text: {chunk}{RESET}")
                                        first = False
                                    else:
                                        all_lines.append(f"    {WHITE}{chunk}{RESET}")
                                    line_keys.append(None)
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
