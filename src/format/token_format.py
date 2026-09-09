# INFRASTRUCTURE
import datetime
import time
import re as _re
from typing import Optional
from ..colors import (
    RED, GREEN, YELLOW, WHITE, PASTEL_PURPLE, PASTEL_ORANGE, LIGHT_RED_BG, DIM, SOFT_RESET,
    SEARCH_MATCH_BG, SEARCH_CURRENT_BG,
)
# From utils.py: right-align a ⎘/✓ copy symbol at the pane edge, width-guarded; browser-find-style
# inline substring highlight
from ..utils import append_copy_symbol, highlight_query_in_line
# From search_bar.py: shared BG-restore sentinel (2026-08-18, rollout sub-milestone 4) — this
# module doesn't know a row's eventual chosen_bg (zebra/hover) at embed time, only
# token_pane.py's own render loop does, once computed; same pattern as proxy_display/format.py
from ..search_bar import _BG_RESTORE_SENTINEL

# FUNCTIONS

# Shorten MCP tool names for display (mcp__plugin_xxx_yyy__tool_name → tool_name)
def shorten_tool_name(name: str) -> str:
    if name.startswith('mcp__'):
        parts = name.split('__')
        if len(parts) >= 3:
            return parts[-1]
    return name

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

# Compute (has_thinking, sig_chars) for a call's content_blocks — extracted 2026-08-18 (rollout
# sub-milestone 4) so the real render loop and token_search.py's matcher can never disagree on
# which calls show the 🧠 indicator / think_color threshold.
def _call_thinking_meta(call: dict) -> tuple:
    has_thinking = any(b.get('type') == 'thinking' for b in call.get('content_blocks', []))
    sig_chars = sum(b.get('sig_chars', 0) for b in call.get('content_blocks', []) if b.get('type') == 'thinking')
    return has_thinking, sig_chars

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

# Format rate-limit reset epoch string for display (HH:MM same-day, or DayName HH:MM otherwise)
def _fmt_rl_reset_time(epoch_str: str) -> str:
    try:
        ts = datetime.datetime.fromtimestamp(int(epoch_str))
        now = datetime.datetime.now()
        if ts.date() == now.date():
            return ts.strftime('%H:%M')
        return ts.strftime('%a %H:%M')
    except (ValueError, OSError):
        return epoch_str

# TTL split / web_search-fetch / tier-speed-geo / iteration-count lines; returns (lines, keys).
def _render_usage_extras_lines(call: dict) -> tuple:
    lines = []
    keys = []
    ttl = call.get('cache_creation_ttl') or {}
    m5  = ttl.get('ephemeral_5m_input_tokens', 0)
    h1  = ttl.get('ephemeral_1h_input_tokens', 0)
    if ttl:
        lines.append(f"    {DIM}5m:{_format_k(m5)}  1h:{_format_k(h1)}{SOFT_RESET}")
        keys.append(None)
    stu = call.get('server_tool_use') or {}
    ws  = stu.get('web_search_requests', 0)
    wf  = stu.get('web_fetch_requests', 0)
    if ws or wf:
        lines.append(f"    {DIM}web_search:{ws}  web_fetch:{wf}{SOFT_RESET}")
        keys.append(None)
    tier = call.get('service_tier', '')
    spd  = call.get('speed', '')
    geo  = call.get('inference_geo', '')
    meta_parts = []
    if tier: meta_parts.append(f"tier:{tier}")
    if spd:  meta_parts.append(f"speed:{spd}")
    if geo:  meta_parts.append(f"geo:{geo}")
    if meta_parts:
        lines.append(f"    {DIM}{' '.join(meta_parts)}{SOFT_RESET}")
        keys.append(None)
    iters = call.get('iterations') or []
    if iters:
        lines.append(f"    {DIM}iter:{len(iters)}{SOFT_RESET}")
        keys.append(None)
    return lines, keys

# Rate-limit `rl:` line (5h/7d utilization+reset) + YELLOW warn line (non-allowed status/overage);
# returns (lines, keys). No-op (empty) when the call's request_id has no response_rid_map entry.
def _render_rate_limit_lines(call: dict, response_rid_map: dict) -> tuple:
    lines = []
    keys = []
    rid = call.get('request_id', '')
    rl_headers = (response_rid_map or {}).get(rid) if rid else None
    if not rl_headers:
        return lines, keys
    u5h = rl_headers.get('anthropic-ratelimit-unified-5h-utilization', '')
    r5h = rl_headers.get('anthropic-ratelimit-unified-5h-reset', '')
    u7d = rl_headers.get('anthropic-ratelimit-unified-7d-utilization', '')
    r7d = rl_headers.get('anthropic-ratelimit-unified-7d-reset', '')
    parts_rl = []
    if u5h:
        pct5 = f"{float(u5h)*100:.0f}%"
        parts_rl.append(f"5h:{pct5}→{_fmt_rl_reset_time(r5h)}" if r5h else f"5h:{pct5}")
    if u7d:
        pct7 = f"{float(u7d)*100:.0f}%"
        parts_rl.append(f"7d:{pct7}→{_fmt_rl_reset_time(r7d)}" if r7d else f"7d:{pct7}")
    if parts_rl:
        lines.append(f"    {DIM}rl: {'  '.join(parts_rl)}{SOFT_RESET}")
        keys.append(None)
    status = rl_headers.get('anthropic-ratelimit-unified-status', 'allowed')
    overage = rl_headers.get('anthropic-ratelimit-unified-overage-status', '')
    warn_parts = []
    if status != 'allowed':
        warn_parts.append(f"status:{status}")
    if overage and overage != 'allowed':
        reason = rl_headers.get('anthropic-ratelimit-unified-overage-disabled-reason', '')
        warn_parts.append(f"overage:{overage}" + (f"({reason})" if reason else ''))
    if warn_parts:
        lines.append(f"    {YELLOW}{'  '.join(warn_parts)}{SOFT_RESET}")
        keys.append(None)
    return lines, keys

# Content-blocks loop (tool_use / thinking / text); returns (lines, keys).
def _render_content_block_lines(call: dict) -> tuple:
    lines = []
    keys = []
    for block in call.get('content_blocks', []):
        bt = block.get('type', '')
        if bt == 'tool_use':
            tool_name = block.get('tool_name', 'Unknown')
            if tool_name.startswith('mcp__'):
                tool_name = shorten_tool_name(tool_name)
            input_data = block.get('preview', {})
            if isinstance(input_data, dict) and input_data:
                lines.append(f"    {GREEN}{tool_name}{SOFT_RESET}")
                keys.append(None)
                for k, v in input_data.items():
                    val_str = str(v).replace('\n', ' ') if not isinstance(v, str) else v.replace('\n', ' ')
                    lines.append(f"      {GREEN}{k}: {val_str}{SOFT_RESET}")
                    keys.append(None)
            else:
                lines.append(f"    {GREEN}{tool_name}{SOFT_RESET}")
                keys.append(None)
        elif bt == 'thinking':
            sc = block.get('sig_chars', 0)
            sig_str = f"sig: {_format_k(sc)}" if sc else "sig: —"
            lines.append(f"    {PASTEL_ORANGE}thinking ({sig_str}){SOFT_RESET}")
            keys.append(None)
        elif bt == 'text':
            preview = block.get('preview', '')
            if preview:
                lines.append(f"    {WHITE}text: {preview.replace(chr(10), ' ')}{SOFT_RESET}")
            else:
                lines.append(f"    {WHITE}text{SOFT_RESET}")
            keys.append(None)
    return lines, keys

# Render expanded detail lines for one API call; returns (lines, keys).
def _render_expanded_call_lines(call: dict, response_rid_map: dict) -> tuple:
    lines = []
    keys = []
    for group_lines, group_keys in (
        _render_usage_extras_lines(call),
        _render_rate_limit_lines(call, response_rid_map),
        _render_content_block_lines(call),
    ):
        lines.extend(group_lines)
        keys.extend(group_keys)
    return lines, keys

# Compute viewport slice, sticky header, and initial_parent_count; returns the 5-tuple.
def _compute_cache_viewport(all_lines: list, line_keys: list, pane_height: int, pane_width: int, scroll_offset: int) -> tuple:
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

# Format one turn's header line (prompt truncation + timestamp + thinking-count badge) —
# extracted 2026-08-18 (rollout sub-milestone 4) so the real render loop and
# token_search.py's matcher can never disagree on what a turn's own line actually says.
def _format_turn_header_line(turn_idx: int, turn: dict, pane_width: int) -> str:
    wide = pane_width >= 60
    prompt_max = min(pane_width - 15, 60) if wide else min(pane_width - 8, 30)
    prompt = turn.get('prompt', '').replace('\n', ' ')
    timestamp = _format_ts(turn.get('timestamp', ''))
    truncated = prompt[:prompt_max] + ('...' if len(prompt) > prompt_max else '')
    api_calls = turn.get('api_calls', [])
    thinking_calls = sum(1 for call in api_calls if _call_thinking_meta(call)[0])
    think_str = f" ({thinking_calls}/{len(api_calls)} 🧠)" if thinking_calls > 0 else ""
    return f"{PASTEL_PURPLE}Turn {turn_idx + 1} [{timestamp}]{think_str}: \"{truncated}\"{SOFT_RESET}"

# Format cache tracker — returns (visible_lines, visible_keys, sticky_header, viewport_start, initial_parent_count)
# (2026-08-18, rollout sub-milestone 4) search_match_set/search_current_key/search_query embed
# search highlights at construction time via _BG_RESTORE_SENTINEL — a MATCH key is either
# (turn_idx, call_idx) [container-marked whole line, unconditionally, regardless of expand
# state — mirrors proxy_display's REQ-header "text extent" marking] or ('turn', turn_idx)
# [same whole-line container mark, since a turn has no expand state to distinguish]. An
# expanded matching call ADDITIONALLY gets its specific matching detail line(s) browser-find
# substring-highlighted via utils.highlight_query_in_line — the header stays marked too
# (uniform, keeps orientation when scrolling, same decision proxy made). nav_out, when given,
# is populated (NOT returned — cleared+rewritten in place, same contract as
# proxy_display.format's copy_rows_out) with {key: absolute_line_idx, ..., 'total_lines': N}
# for the caller's own jump-to-match scroll math — deliberately kept OUT of line_keys so
# ('turn', idx) keys never reach cache_line_map/click handling (turn headers stay
# non-interactive for clicks, exactly as before) and workers/worker_format.py's own reuse of
# this function (which assumes every non-None key is a plain 2-int-tuple) is unaffected.
# Per-call summary-line build: symbol + _format_cache_call + search-marker-wrap + copy-symbol.
# Returns (call_line, key, marker) — marker is None unless this call is a search match; the
# caller uses it to decide whether/how to highlight this call's expanded detail lines.
def _render_call_line(turn_idx: int, call_idx: int, call: dict, is_expanded: bool, request_num: int,
                      wide: bool, pane_width: int, search_match_set: Optional[set],
                      search_current_key, copy_feedback: Optional[dict]) -> tuple:
    cr = call.get('cache_read', 0)
    cc = call.get('cache_creation', 0)
    d = call.get('direct', 0)
    out = call.get('output_tokens', 0)
    key = (turn_idx, call_idx)
    symbol = '▼' if is_expanded else '▶'
    has_thinking, sig_chars = _call_thinking_meta(call)
    call_line = _format_cache_call(symbol, cr, cc, d, out, wide, request_num, has_thinking, sig_chars)
    call_is_match = bool(search_match_set) and key in search_match_set
    marker = None
    if call_is_match:
        marker = SEARCH_CURRENT_BG if key == search_current_key else SEARCH_MATCH_BG
        call_line = f"{marker}{call_line}{_BG_RESTORE_SENTINEL}"
    if copy_feedback is not None:
        is_flash = copy_feedback.get(key, 0) > time.time()
        call_line = append_copy_symbol(call_line, '✓' if is_flash else '⎘', pane_width)
    return call_line, key, marker

# Appends one turn's header + all its call lines + trailing blank line directly into the
# caller's all_lines/line_keys (in-place — same contract nav_out already uses, keeps nav_out's
# absolute line-index bookkeeping correct without threading an offset). Returns the updated
# request_num (a running counter across turns).
def _render_turn_lines(turn_idx: int, turn: dict, expand_states: dict, pane_width: int, wide: bool,
                       request_num: int, response_rid_map: dict, copy_feedback: Optional[dict],
                       search_match_set: Optional[set], search_current_key, search_query: str,
                       nav_out: Optional[dict], all_lines: list, line_keys: list) -> int:
    turn_key = ('turn', turn_idx)
    turn_line = _format_turn_header_line(turn_idx, turn, pane_width)
    turn_is_match = bool(search_match_set) and turn_key in search_match_set
    if turn_is_match:
        marker = SEARCH_CURRENT_BG if turn_key == search_current_key else SEARCH_MATCH_BG
        turn_line = f"{marker}{turn_line}{_BG_RESTORE_SENTINEL}"
    if nav_out is not None:
        nav_out[turn_key] = len(all_lines)
    all_lines.append(turn_line)
    line_keys.append(None)

    api_calls = turn.get('api_calls', [])
    for call_idx, call in enumerate(api_calls):
        is_expanded = expand_states.get((turn_idx, call_idx), False)
        request_num += 1
        call_line, key, marker = _render_call_line(
            turn_idx, call_idx, call, is_expanded, request_num, wide, pane_width,
            search_match_set, search_current_key, copy_feedback)
        if nav_out is not None:
            nav_out[key] = len(all_lines)
        all_lines.append(call_line)
        line_keys.append(key)
        if is_expanded:
            exp_lines, exp_keys = _render_expanded_call_lines(call, response_rid_map)
            if marker is not None and search_query:
                exp_lines = [highlight_query_in_line(l, search_query, marker, _BG_RESTORE_SENTINEL) for l in exp_lines]
            all_lines.extend(exp_lines)
            line_keys.extend(exp_keys)

    all_lines.append('')
    line_keys.append(None)
    return request_num

def format_cache_tracker(turns: list, expand_states: dict = None, pane_height: int = 50, pane_width: int = 80, scroll_offset: int = 0, response_rid_map: dict = None, copy_feedback: Optional[dict] = None, search_match_set: Optional[set] = None, search_current_key=None, search_query: str = '', nav_out: Optional[dict] = None) -> tuple:
    if not turns:
        return [f"{YELLOW}No turns yet{SOFT_RESET}"], [None], None, 0, 0

    if expand_states is None:
        expand_states = {}
    if nav_out is not None:
        nav_out.clear()

    wide = pane_width >= 60
    prompt_max = min(pane_width - 15, 60) if wide else min(pane_width - 8, 30)

    all_lines = []
    line_keys = []
    request_num = 0

    if not wide:
        all_lines.append(f"{WHITE}CR/CC/D = Read/Create/Direct{SOFT_RESET}")
        line_keys.append(None)

    for turn_idx, turn in enumerate(turns):
        request_num = _render_turn_lines(
            turn_idx, turn, expand_states, pane_width, wide, request_num, response_rid_map,
            copy_feedback, search_match_set, search_current_key, search_query, nav_out,
            all_lines, line_keys)

    while all_lines and all_lines[-1] == '':
        all_lines.pop()
        line_keys.pop()

    if nav_out is not None:
        nav_out['total_lines'] = len(all_lines)

    return _compute_cache_viewport(all_lines, line_keys, pane_height, pane_width, scroll_offset)
