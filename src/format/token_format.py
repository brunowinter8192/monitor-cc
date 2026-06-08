# INFRASTRUCTURE
import datetime
from typing import Optional
from ..constants import RED, GREEN, YELLOW, WHITE, PASTEL_PURPLE, PASTEL_ORANGE, LIGHT_RED_BG, DIM, SOFT_RESET
# FUNCTIONS
# Format token count as compact "Xk" or "X.Xk" string
def _format_k(n: int) -> str:
    if n >= 1000:
        return f"{n / 1000:.0f}k" if n >= 10000 else f"{n / 1000:.1f}k"
    return str(n)

# Format a single API call line for cache tracker (wide or compact based on pane width)
def _format_cache_call(symbol: str, cr: int, cc: int, d: int, out: int, wide: bool, req_num: int = 0, has_thinking: bool = False, sig_chars: int = 0) -> str:
    cc_broken = cc > cr
    bg = LIGHT_RED_BG if cc_broken else ''
    if has_thinking:
        if sig_chars > 8000:
            think_color = RED
        elif sig_chars > 2000:
            think_color = YELLOW
        else:
            think_color = GREEN
        think_indicator = f' {think_color}🧠{_format_k(sig_chars)}{SOFT_RESET}'
    else:
        think_indicator = ''
    if wide:
        return f"{bg}  {symbol} REQ #{req_num}  CR: {cr:>7,}  CC: {cc:>7,}  D: {d:>5,}  ({_format_k(out)} out){think_indicator}"
    return f"{bg} {symbol} #{req_num} {_format_k(cr)}/{_format_k(cc)}/{_format_k(d)} ({_format_k(out)} out){think_indicator}"

# Extract first meaningful value from tool input dict for preview
def _get_tool_preview(input_data: dict) -> str:
    for key in ('file_path', 'pattern', 'command', 'subagent_type', 'prompt', 'query'):
        if key in input_data:
            return str(input_data[key]).replace('\n', ' ')
    return ''

# Format timestamp for display (import lazily to avoid circular at module level)
def _format_ts(timestamp: str) -> str:
    from ..utils import format_timestamp
    return format_timestamp(timestamp)

# Format cache tracker — returns (visible_lines, visible_keys, sticky_header, viewport_start, initial_parent_count)
def format_cache_tracker(turns: list, expand_states: dict = None, pane_height: int = 50, pane_width: int = 80, scroll_offset: int = 0, response_rid_map: dict = None) -> tuple:
    from .formatter import shorten_tool_name
    if not turns:
        return [f"{YELLOW}No turns yet{SOFT_RESET}"], [None], None, 0, 0

    if expand_states is None:
        expand_states = {}

    wide = pane_width >= 60
    prompt_max = min(pane_width - 15, 60) if wide else min(pane_width - 8, 30)

    all_lines = []
    line_keys = []
    request_num = 0

    if not wide:
        all_lines.append(f"{WHITE}CR/CC/D = Read/Create/Direct{SOFT_RESET}")
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
        all_lines.append(f"{PASTEL_PURPLE}Turn {turn_idx + 1} [{timestamp}]{think_str}: \"{truncated}\"{SOFT_RESET}")
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
            sig_chars = sum(b.get('sig_chars', 0) for b in call.get('content_blocks', []) if b.get('type') == 'thinking')
            call_line = _format_cache_call(symbol, cr, cc, d, out, wide, request_num, has_thinking, sig_chars)
            all_lines.append(call_line)
            line_keys.append(key)

            if is_expanded:
                ttl = call.get('cache_creation_ttl') or {}
                m5  = ttl.get('ephemeral_5m_input_tokens', 0)
                h1  = ttl.get('ephemeral_1h_input_tokens', 0)
                if ttl:
                    all_lines.append(f"    {DIM}5m:{_format_k(m5)}  1h:{_format_k(h1)}{SOFT_RESET}")
                    line_keys.append(None)
                stu = call.get('server_tool_use') or {}
                ws  = stu.get('web_search_requests', 0)
                wf  = stu.get('web_fetch_requests', 0)
                if ws or wf:
                    all_lines.append(f"    {DIM}web_search:{ws}  web_fetch:{wf}{SOFT_RESET}")
                    line_keys.append(None)
                tier = call.get('service_tier', '')
                spd  = call.get('speed', '')
                geo  = call.get('inference_geo', '')
                meta_parts = []
                if tier: meta_parts.append(f"tier:{tier}")
                if spd:  meta_parts.append(f"speed:{spd}")
                if geo:  meta_parts.append(f"geo:{geo}")
                if meta_parts:
                    all_lines.append(f"    {DIM}{' '.join(meta_parts)}{SOFT_RESET}")
                    line_keys.append(None)
                iters = call.get('iterations') or []
                if iters:
                    all_lines.append(f"    {DIM}iter:{len(iters)}{SOFT_RESET}")
                    line_keys.append(None)
                rid = call.get('request_id', '')
                rl_headers = (response_rid_map or {}).get(rid) if rid else None
                if rl_headers:
                    def _fmt_reset(epoch_str: str) -> str:
                        try:
                            ts = datetime.datetime.fromtimestamp(int(epoch_str))
                            now = datetime.datetime.now()
                            if ts.date() == now.date():
                                return ts.strftime('%H:%M')
                            return ts.strftime('%a %H:%M')
                        except (ValueError, OSError):
                            return epoch_str
                    u5h = rl_headers.get('anthropic-ratelimit-unified-5h-utilization', '')
                    r5h = rl_headers.get('anthropic-ratelimit-unified-5h-reset', '')
                    u7d = rl_headers.get('anthropic-ratelimit-unified-7d-utilization', '')
                    r7d = rl_headers.get('anthropic-ratelimit-unified-7d-reset', '')
                    parts_rl = []
                    if u5h:
                        pct5 = f"{float(u5h)*100:.0f}%"
                        parts_rl.append(f"5h:{pct5}→{_fmt_reset(r5h)}" if r5h else f"5h:{pct5}")
                    if u7d:
                        pct7 = f"{float(u7d)*100:.0f}%"
                        parts_rl.append(f"7d:{pct7}→{_fmt_reset(r7d)}" if r7d else f"7d:{pct7}")
                    if parts_rl:
                        all_lines.append(f"    {DIM}rl: {'  '.join(parts_rl)}{SOFT_RESET}")
                        line_keys.append(None)
                    status = rl_headers.get('anthropic-ratelimit-unified-status', 'allowed')
                    overage = rl_headers.get('anthropic-ratelimit-unified-overage-status', '')
                    warn_parts = []
                    if status != 'allowed':
                        warn_parts.append(f"status:{status}")
                    if overage and overage != 'allowed':
                        reason = rl_headers.get('anthropic-ratelimit-unified-overage-disabled-reason', '')
                        warn_parts.append(f"overage:{overage}" + (f"({reason})" if reason else ''))
                    if warn_parts:
                        all_lines.append(f"    {YELLOW}{'  '.join(warn_parts)}{SOFT_RESET}")
                        line_keys.append(None)
                for block in call.get('content_blocks', []):
                    bt = block.get('type', '')
                    if bt == 'tool_use':
                        tool_name = block.get('tool_name', 'Unknown')
                        if tool_name.startswith('mcp__'):
                            tool_name = shorten_tool_name(tool_name)
                        input_data = block.get('preview', {})
                        if isinstance(input_data, dict) and input_data:
                            all_lines.append(f"    {GREEN}{tool_name}{SOFT_RESET}")
                            line_keys.append(None)
                            for k, v in input_data.items():
                                val_str = str(v).replace('\n', ' ') if not isinstance(v, str) else v.replace('\n', ' ')
                                all_lines.append(f"      {GREEN}{k}: {val_str}{SOFT_RESET}")
                                line_keys.append(None)
                        else:
                            all_lines.append(f"    {GREEN}{tool_name}{SOFT_RESET}")
                            line_keys.append(None)
                    elif bt == 'thinking':
                        sc = block.get('sig_chars', 0)
                        sig_str = f"sig: {_format_k(sc)}" if sc else "sig: —"
                        all_lines.append(f"    {PASTEL_ORANGE}thinking ({sig_str}){SOFT_RESET}")
                        line_keys.append(None)
                    elif bt == 'text':
                        preview = block.get('preview', '')
                        if preview:
                            all_lines.append(f"    {WHITE}text: {preview.replace(chr(10), ' ')}{SOFT_RESET}")
                        else:
                            all_lines.append(f"    {WHITE}text{SOFT_RESET}")
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
                        sticky_header = f"{PASTEL_PURPLE}{m.group(0)}...{SOFT_RESET}"
                    else:
                        sticky_header = raw
                else:
                    sticky_header = raw
                break

    visible_lines = all_lines[start:end]
    visible_keys = line_keys[start:end]
    initial_parent_count = sum(1 for k in line_keys[:start] if k is not None)

    return visible_lines, visible_keys, sticky_header, start, initial_parent_count
