# INFRASTRUCTURE
import time
from datetime import datetime

from .constants import (
    RESET, WHITE, RED, DIM, PASTEL_GREEN, YELLOW,
    POLL_INTERVAL,
)
from .token_pane import _format_k

_prev_values: dict = {}
_meta_log_position: int = 0
_meta_entries: list = []

LEGEND = [
    f"{PASTEL_GREEN}▶/▼ expand  ⚠ cache break  🔧 mods  BP: breakpoints  ~tok: chars/3.5 ±15%{RESET}",
    f"{PASTEL_GREEN}sys=system  tools=tool defs  msgs=messages{RESET}",
]

# ORCHESTRATOR

# Run metadata pane loop — reads proxy log directly and shows API config state
def run_metadata_loop() -> None:
    from . import monitor as _monitor
    from .proxy_pane import parse_proxy_log
    global _prev_values, _meta_log_position, _meta_entries

    session_start_ts = _monitor._get_session_start_ts()
    if session_start_ts is None:
        session_start_ts = datetime.utcnow().isoformat() + 'Z'
    current_main_session = _monitor._get_newest_main_session()
    last_output = None

    while True:
        newest = _monitor._get_newest_main_session()
        if newest != current_main_session and newest is not None:
            current_main_session = newest
            session_start_ts = _monitor._get_session_start_ts()
            if session_start_ts is None:
                session_start_ts = datetime.utcnow().isoformat() + 'Z'
            _meta_entries.clear()
            _meta_log_position = 0
            _prev_values = {}

        new_entries, _meta_log_position = parse_proxy_log(_monitor.active_project_filter, _meta_log_position)
        filtered = [e for e in new_entries if e.get('timestamp', '') >= session_start_ts]
        _meta_entries.extend(filtered)

        if _meta_entries:
            output = _format_metadata(_meta_entries[-1])
        else:
            output = '\n'.join(LEGEND) + f"\n{DIM}Waiting for proxy data...{RESET}"

        if output != last_output:
            print("\033[2J\033[3J\033[H", end='', flush=True)
            print(output)
            last_output = output

        time.sleep(POLL_INTERVAL)

# FUNCTIONS

# Format metadata display for latest proxy entry with change detection
def _format_metadata(entry: dict) -> str:
    global _prev_values
    lines = list(LEGEND)
    lines.append('')
    new_values: dict = {}

    # SYSTEM section
    sys_blocks = entry.get('system_blocks', [])
    sys_total = entry.get('system_total_chars', 0)
    lines.append(f"{WHITE}─── SYSTEM ───{RESET}")
    if sys_blocks:
        for sb in sys_blocks:
            idx = sb.get('idx', 0)
            chars = sb.get('chars', 0)
            key = f"sys_chars_{idx}"
            new_values[key] = chars
            prev = _prev_values.get(key)
            changed = prev is not None and prev != chars
            if changed:
                lines.append(f"  {RED}[{idx}]: {_format_k(prev)} → {_format_k(chars)}{RESET}")
            else:
                lines.append(f"  {DIM}[{idx}]: {_format_k(chars)}{RESET}")
        new_values['sys_total'] = sys_total
        prev_total = _prev_values.get('sys_total')
        total_changed = prev_total is not None and prev_total != sys_total
        if total_changed:
            lines.append(f"  {RED}total: {_format_k(prev_total)} → {_format_k(sys_total)} ({len(sys_blocks)} blocks){RESET}")
        else:
            lines.append(f"  {DIM}total: {_format_k(sys_total)} ({len(sys_blocks)} blocks){RESET}")
    else:
        lines.append(f"  {DIM}(no system data){RESET}")

    # TOOLS section
    tools_count = entry.get('tools_count', 0)
    tools_chars = entry.get('tools_total_chars', 0)
    tools_hash = entry.get('tools_hash', '')
    lines.append('')
    lines.append(f"{WHITE}─── TOOLS ───{RESET}")
    new_values['tools_count'] = tools_count
    new_values['tools_hash'] = tools_hash
    prev_hash = _prev_values.get('tools_hash')
    hash_changed = prev_hash is not None and prev_hash != tools_hash
    hash_str = f"  hash:{tools_hash[:8]}" if tools_hash else ''
    if tools_count:
        color = RED if hash_changed else DIM
        lines.append(f"  {color}{tools_count} defs ({_format_k(tools_chars)}){hash_str}{RESET}")
    else:
        lines.append(f"  {DIM}(no tools data){RESET}")

    # CONFIG section
    tc = entry.get('thinking_config', {})
    oc = entry.get('output_config', {})
    effort = oc.get('effort', '?')
    budget = tc.get('budget_tokens', 0)
    think_type = tc.get('type', '?')
    lines.append('')
    lines.append(f"{WHITE}─── CONFIG ───{RESET}")
    new_values['effort'] = effort
    new_values['budget'] = budget
    new_values['think_type'] = think_type
    prev_effort = _prev_values.get('effort')
    effort_changed = prev_effort is not None and prev_effort != effort
    if effort_changed:
        lines.append(f"  {RED}effort: {prev_effort} → {effort}{RESET}")
    else:
        lines.append(f"  {DIM}effort: {effort}{RESET}")
    prev_budget = _prev_values.get('budget')
    prev_think_type = _prev_values.get('think_type')
    think_changed = (prev_budget is not None and prev_budget != budget) or (prev_think_type is not None and prev_think_type != think_type)
    budget_str = _format_k(budget) if budget else '?'
    think_color = RED if think_changed else DIM
    lines.append(f"  {think_color}thinking: {budget_str} ({think_type}){RESET}")

    # CACHE MARKERS section
    cache_bps = entry.get('cache_breakpoints', [])
    msg_count = entry.get('message_count', 0)
    lines.append('')
    lines.append(f"{WHITE}─── CACHE MARKERS ───{RESET}")
    if cache_bps:
        for bp_idx in cache_bps:
            label = '  (last msg)' if bp_idx == msg_count - 1 else ''
            lines.append(f"  {DIM}msg[{bp_idx}]{label}{RESET}")
    else:
        lines.append(f"  {DIM}(no message breakpoints){RESET}")

    _prev_values = new_values
    return '\n'.join(lines)
