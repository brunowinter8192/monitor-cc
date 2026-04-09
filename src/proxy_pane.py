# INFRASTRUCTURE
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import hashlib
import json
import os
import time

from .constants import (
    RESET, GREEN, RED, YELLOW, WHITE, CYAN, DIM, DIM_YELLOW_BG,
    PASTEL_GREEN, PASTEL_PURPLE,
    HOVER_BG,
    POLL_INTERVAL, INPUT_POLL_INTERVAL,
    KNOWN_PAYLOAD_KEYS, KNOWN_CONTENT_BLOCK_TYPES, KNOWN_TOOL_DEFINITION_KEYS, KNOWN_MESSAGE_ROLES,
    TOOL_BLOCKLIST, AGENT_TRIMMED_DESCRIPTION,
)
from .token_pane import _format_k, build_cache_turns
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

_proxy_jsonl_position: int = 0
_proxy_cache_turns: list = []

# FUNCTIONS

# Estimate token count from char count (chars/3.5 heuristic, ~±15%)
def _chars_to_tokens(chars: int) -> int:
    return int(chars / 3.5)

# Format token estimate as compact string with ~ prefix
def _format_tok_est(chars: int) -> str:
    return f"~{_format_k(_chars_to_tokens(chars))}tok"

# Format a signed char-count delta with token estimate (GREEN=positive, RED=negative, DIM=zero)
def _format_delta(label: str, delta: int) -> str:
    if delta == 0:
        return f"{DIM}Δ{label}:0{RESET}"
    sign = '+' if delta > 0 else '-'
    color = GREEN if delta > 0 else RED
    abs_chars = abs(delta)
    tok_est = _chars_to_tokens(abs_chars)
    return f"{color}Δ{label}:{sign}{_format_k(abs_chars)}(~{_format_k(tok_est)}tok){RESET}"

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
            {'idx': i, 'chars': len(b.get('text', '')), 'has_cc': bool(b.get('cache_control')), 'preview': b.get('text', '')}
            for i, b in enumerate(system) if isinstance(b, dict)
        ] if isinstance(system, list) else []
        entry['system_total_chars'] = sum(b['chars'] for b in entry['system_blocks'])

        tools = raw.get('tools', [])
        entry['tools_total_chars'] = sum(len(json.dumps(t)) for t in tools)
        entry['tools_count'] = len(tools)
        entry['tools_hash'] = hashlib.md5(json.dumps(sorted([t.get('name', '') for t in tools])).encode()).hexdigest()[:8]
        entry['tools_names'] = [t.get('name', '') for t in tools]
        entry['tools_defs'] = [
            {
                'name': t.get('name', ''),
                'description': t.get('description', ''),
                'input_schema': t.get('input_schema', {}),
            }
            for t in tools
        ]

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

        # Enrich messages with content tail from raw payload for modified-message detection
        stored_msgs = entry.get('messages', [])
        if stored_msgs and isinstance(msgs, list):
            for i, raw_msg in enumerate(msgs):
                if i < len(stored_msgs):
                    content = raw_msg.get('content', '')
                    if isinstance(content, str):
                        text = content
                    elif isinstance(content, list):
                        text = ''.join(b.get('text', '') for b in content if isinstance(b, dict))
                    else:
                        text = ''
                    stored_msgs[i]['content_tail'] = text

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

# Assign each proxy entry to the matching turn based on timestamp comparison
def _assign_turns_to_entries(entries: list, turns: list) -> list:
    if not turns or not entries:
        return []
    groups = [{'turn_idx': i, 'timestamp': t.get('timestamp', ''), 'entry_pairs': []} for i, t in enumerate(turns)]
    for entry_idx, entry in enumerate(entries):
        entry_ts = entry.get('timestamp', '')
        assigned = False
        for i in range(len(turns) - 1, -1, -1):
            if entry_ts >= turns[i].get('timestamp', ''):
                groups[i]['entry_pairs'].append((entry_idx, entry))
                assigned = True
                break
        if not assigned:
            groups[0]['entry_pairs'].append((entry_idx, entry))
    return [g for g in groups if g['entry_pairs']]

# Render a single proxy entry into (lines, line_keys). indent sets the nesting level.
def _render_entry_lines(entry_idx: int, entry: dict, entries: list, expand_states: dict, pane_width: int, indent: str = '', num_label: str = '#0') -> tuple:
    L1 = indent
    L2 = indent + '  '
    L3 = indent + '    '
    L4 = indent + '      '
    lines = []
    keys = []

    model = _shorten_model(entry.get('model', '?'))
    msg_count = entry.get('message_count', 0)
    cache_bp = entry.get('cache_breakpoints', [])
    diff = entry.get('diff_from_prev', {})
    first_diff = diff.get('first_diff_index', -1)
    mods = entry.get('modifications', [])

    bp_count = len(cache_bp)
    mods_count = len(mods)
    is_expanded = expand_states.get(entry_idx, False)
    symbol = '\u25bc' if is_expanded else '\u25b6'

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
            warn_details.append([f"{L3}{GREEN}+{n}{RESET}" for n in added] + [f"{L3}{RED}-{n}{RESET}" for n in removed])
        if entry.get('system_total_chars') is not None and prev_entry.get('system_total_chars') is not None and entry.get('system_total_chars') != prev_entry.get('system_total_chars'):
            warn_symbols.append(f"{RED}⚠S{RESET}")
            old_c = prev_entry['system_total_chars']
            new_c = entry['system_total_chars']
            delta = new_c - old_c
            warn_details.append([f"{L3}{DIM}sys: {_format_k(old_c)} → {_format_k(new_c)} ({delta:+,}){RESET}"])
    has_warn_m = False
    if prev_entry is not None:
        msgs_modified = diff.get('messages_modified', 0)
        if msgs_modified > 0 and first_diff >= 0 and cache_bp:
            if first_diff < min(cache_bp):
                has_warn_m = True

    all_status = warn_symbols[:]
    if has_warn_m:
        all_status.append(f"{RED}⚠M{RESET}")
    status_str = '  '.join(all_status)
    mods_str = f"  {YELLOW}🔧{mods_count}{RESET}" if mods_count > 0 else ''

    lines.append(f"{WHITE}{L1}{symbol} {num_label}  {model}  {msg_count}msg  BP:{bp_count}{mods_str}  {status_str}{RESET}")
    keys.append(entry_idx)

    sys_chars = entry.get('system_total_chars', entry.get('system_prompt_chars', 0))
    tools_chars = entry.get('tools_total_chars', entry.get('tools_chars', 0))
    msgs_chars = entry.get('messages_total_chars', 0)
    if prev_entry is None:
        lines.append(f"{L2}{DIM}(first request){RESET}")
    else:
        d_sys = sys_chars - prev_entry.get('system_total_chars', prev_entry.get('system_prompt_chars', 0))
        d_tools = tools_chars - prev_entry.get('tools_total_chars', prev_entry.get('tools_chars', 0))
        d_msgs = msgs_chars - prev_entry.get('messages_total_chars', 0)
        if d_sys == 0 and d_tools == 0 and d_msgs == 0:
            lines.append(f"{L2}{DIM}Δ: (no change){RESET}")
        else:
            lines.append(f"{L2}{_format_delta('sys', d_sys)}  {_format_delta('tools', d_tools)}  {_format_delta('msgs', d_msgs)}")
    keys.append(None)

    if warn_symbols:
        warn_key = (entry_idx, 'warnings')
        is_warn_expanded = expand_states.get(warn_key, False)
        warn_sym = '\u25bc' if is_warn_expanded else '\u25b6'
        lines.append(f"{L2}{warn_sym} {'  '.join(warn_symbols)}")
        keys.append(warn_key)
        if is_warn_expanded:
            for detail_lines in warn_details:
                for dl in detail_lines:
                    lines.append(dl)
                    keys.append(None)

    schema_warnings = entry.get('schema_warnings', [])
    if schema_warnings:
        schema_key = (entry_idx, 'schema')
        is_schema_expanded = expand_states.get(schema_key, False)
        schema_sym = '\u25bc' if is_schema_expanded else '\u25b6'
        lines.append(f"{L2}{schema_sym} {RED}⚠ SCHEMA DRIFT ({len(schema_warnings)}){RESET}")
        keys.append(schema_key)
        if is_schema_expanded:
            for sw in schema_warnings:
                lines.append(f"{L3}{DIM}{sw}{RESET}")
                keys.append(None)

    if is_expanded:
        lines.append(f"{L2}{DIM}{'─' * min(40, pane_width - len(L2) - 2)}{RESET}")
        keys.append(None)

        messages = entry.get('messages', [])
        stripped_indices = set()
        for _idx, _msg in enumerate(messages):
            if _msg.get('type', '') == 'system-reminder':
                _preview = _msg.get('content_preview', '')
                if 'stripped_task_tools_nag' in mods and 'task tools haven' in _preview:
                    stripped_indices.add(_idx)
                if 'removed_plan_mode_sr' in mods and 'Plan mode is active' in _preview:
                    stripped_indices.add(_idx)

        start_idx = prev_entry.get('message_count', 0) if prev_entry is not None else 0
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
                lines.append(f"{L2}{DIM}{msg_symbol} [{msg_idx:3d}] {role:<8} {msg_type:<20} {chars_fmt:>8}{RESET}{cc_marker}  {YELLOW}[STRIPPED]{RESET}")
            else:
                color = PASTEL_GREEN if has_cc else WHITE
                lines.append(f"{L2}{color}{msg_symbol} [{msg_idx:3d}] {role:<8} {msg_type:<20} {chars_fmt:>8}{RESET}{cc_marker}")
            keys.append(msg_key)

            if is_msg_expanded:
                preview = msg.get('content_preview', '')
                wrap_width = max(20, pane_width - len(L4) - 2)
                if preview:
                    for raw_line in preview.split('\n'):
                        if not raw_line:
                            lines.append(f"{L4}{DIM}{RESET}")
                            keys.append(None)
                            continue
                        for line_start in range(0, len(raw_line), wrap_width):
                            chunk = raw_line[line_start:line_start + wrap_width]
                            lines.append(f"{L4}{DIM}{chunk}{RESET}")
                            keys.append(None)
                else:
                    lines.append(f"{L4}{DIM}(no preview){RESET}")
                    keys.append(None)

    return lines, keys

# Format proxy pane with API request entries grouped by turn, expand/collapse, scroll, hover
def format_proxy_block(entries: list, expand_states: dict = None, line_map: dict = None, hover_row: Optional[int] = None, pane_height: int = 50, pane_width: int = 80, scroll_offset: int = 0, turns: list = None) -> str:
    from .utils import format_timestamp
    if not entries:
        return f"{YELLOW}No API requests logged yet{RESET}"

    if expand_states is None:
        expand_states = {}

    all_lines = []
    line_keys = []

    groups = _assign_turns_to_entries(entries, turns) if turns else None
    opus_req_num = 0
    sub_req_num = 0

    if groups:
        prev_group_last_entry = None
        prev_effort = None
        prev_budget = None
        prev_think_type = None
        for group in groups:
            turn_idx = group['turn_idx']
            opus_req_num = sum(len(t.get('api_calls', [])) for t in turns[:turn_idx])
            sub_req_num = 0

            last_e = group['entry_pairs'][-1][1]
            last_sys = last_e.get('system_total_chars', last_e.get('system_prompt_chars', 0))
            last_tools = last_e.get('tools_total_chars', last_e.get('tools_chars', 0))
            last_msgs = last_e.get('messages_total_chars', 0)

            # Thinking config from first entry of turn
            first_e = group['entry_pairs'][0][1]
            tc = first_e.get('thinking_config', {})
            oc = first_e.get('output_config', {})
            effort = oc.get('effort', '?')
            effort_short = effort[:3] if len(effort) > 3 else effort
            budget = tc.get('budget_tokens', 0)
            budget_str = _format_k(budget) if budget else '?'
            think_type = tc.get('type', '?')
            effort_changed = prev_effort is not None and effort != prev_effort
            budget_changed = prev_budget is not None and budget != prev_budget
            type_changed = prev_think_type is not None and think_type != prev_think_type
            effort_color = RED if effort_changed else ''
            budget_color = RED if (budget_changed or type_changed) else ''
            config_str = f"  {effort_color}effort:{effort_short}{RESET if effort_color else ''}  {budget_color}think:{budget_str}({think_type}){RESET if budget_color else ''}"

            # Delta vs previous turn's last entry
            if prev_group_last_entry is not None:
                ple = prev_group_last_entry
                d_sys = last_sys - ple.get('system_total_chars', ple.get('system_prompt_chars', 0))
                d_tools = last_tools - ple.get('tools_total_chars', ple.get('tools_chars', 0))
                d_msgs = last_msgs - ple.get('messages_total_chars', 0)
                delta_str = f"  {_format_delta('sys', d_sys)}  {_format_delta('tools', d_tools)}  {_format_delta('msgs', d_msgs)}"
            else:
                delta_str = f"  {DIM}(first turn){RESET}"

            turn_key = ('turn', turn_idx)
            is_turn_expanded = expand_states.get(turn_key, False)
            turn_symbol = '\u25bc' if is_turn_expanded else '\u25b6'
            turn_ts = format_timestamp(group['timestamp'])[:5]

            # Turn header line (clickable — expand/collapse unit)
            all_lines.append(f"{PASTEL_PURPLE}{turn_symbol} Turn {turn_idx + 1} [{turn_ts}]{config_str}{delta_str}{RESET}")
            line_keys.append(turn_key)

            # Baseline totals from PREVIOUS turn's last entry (not clickable)
            if prev_group_last_entry is not None:
                ple = prev_group_last_entry
                prev_sys = ple.get('system_total_chars', ple.get('system_prompt_chars', 0))
                prev_tools = ple.get('tools_total_chars', ple.get('tools_chars', 0))
                prev_msgs = ple.get('messages_total_chars', 0)
                all_lines.append(f"  {DIM}total: sys:{_format_k(prev_sys)}  tools:{_format_k(prev_tools)}  msgs:{_format_k(prev_msgs)}{RESET}")
            else:
                all_lines.append(f"  {DIM}total: (first turn){RESET}")
            line_keys.append(None)

            if is_turn_expanded:
                # Request metadata lines — one compact line per entry, no click
                prev_entry_for_delta = prev_group_last_entry
                for entry_idx, entry in group['entry_pairs']:
                    model_short = _shorten_model(entry.get('model', '?'))
                    if model_short == 'haiku':
                        num_label = 'H'
                    else:
                        bp_len = len(entry.get('cache_breakpoints', []))
                        if entry_idx == 0 or bp_len >= 1:
                            opus_req_num += 1
                            sub_req_num = 0
                            num_label = f'#{opus_req_num}'
                        else:
                            sub_req_num += 1
                            num_label = f'#{opus_req_num}.{sub_req_num}'
                    msg_count = entry.get('message_count', 0)
                    cache_bp = entry.get('cache_breakpoints', [])
                    bp_count = len(cache_bp)
                    mods = entry.get('modifications', [])
                    mods_count = len(mods)
                    diff = entry.get('diff_from_prev', {})
                    first_diff = diff.get('first_diff_index', -1)
                    # Warning indicators (not expandable)
                    warn_parts = []
                    prev_same = None
                    for _i in range(entry_idx - 1, -1, -1):
                        _ef = 'haiku' if 'haiku' in entry.get('model', '').lower() else 'opus'
                        _pf = 'haiku' if 'haiku' in entries[_i].get('model', '').lower() else 'opus'
                        if _pf == _ef:
                            prev_same = entries[_i]
                            break
                    if prev_same is not None:
                        if entry.get('tools_hash') and prev_same.get('tools_hash') and entry.get('tools_hash') != prev_same.get('tools_hash'):
                            warn_parts.append(f"{RED}⚠T{RESET}")
                        if entry.get('system_total_chars') is not None and prev_same.get('system_total_chars') is not None and entry.get('system_total_chars') != prev_same.get('system_total_chars'):
                            warn_parts.append(f"{RED}⚠S{RESET}")
                        msgs_modified = diff.get('messages_modified', 0)
                        if msgs_modified > 0 and first_diff >= 0 and cache_bp:
                            if first_diff < min(cache_bp):
                                warn_parts.append(f"{RED}⚠M{RESET}")
                    # Per-request Δmsgs
                    e_msgs = entry.get('messages_total_chars', 0)
                    if prev_entry_for_delta is not None:
                        d_req_msgs = e_msgs - prev_entry_for_delta.get('messages_total_chars', 0)
                        req_delta_str = f"  {_format_delta('msgs', d_req_msgs)}" if d_req_msgs != 0 else ''
                    else:
                        req_delta_str = ''
                    mods_str = f" {YELLOW}🔧{mods_count}{RESET}" if mods_count > 0 else ''
                    warn_str = f"  {'  '.join(warn_parts)}" if warn_parts else ''
                    req_key = ('req', entry_idx)
                    is_req_expanded = expand_states.get(req_key, False)
                    req_symbol = '\u25bc' if is_req_expanded else '\u25b6'
                    all_lines.append(f"  {WHITE}{req_symbol} {num_label} {model_short} {msg_count}msg BP:{bp_count}{mods_str}{warn_str}{req_delta_str}{RESET}")
                    line_keys.append(req_key)
                    if is_req_expanded:
                        wrap_width_meta = max(20, pane_width - 10)
                        # System blocks (expandable)
                        sys_blocks = entry.get('system_blocks', [])
                        sys_total = entry.get('system_total_chars', 0)
                        if sys_blocks:
                            sys_key = ('sys', entry_idx)
                            is_sys_expanded = expand_states.get(sys_key, False)
                            sys_symbol = '\u25bc' if is_sys_expanded else '\u25b6'
                            prev_sys_total = prev_entry_for_delta.get('system_total_chars', 0) if prev_entry_for_delta else 0
                            sys_delta = sys_total - prev_sys_total if prev_entry_for_delta else 0
                            sys_delta_str = f"  {_format_delta('sys', sys_delta)}" if sys_delta != 0 else ''
                            all_lines.append(f"    {DIM}{sys_symbol} sys: {len(sys_blocks)} blocks ({sys_total:,}c){RESET}{sys_delta_str}")
                            line_keys.append(sys_key)
                            if is_sys_expanded:
                                for sb in sys_blocks:
                                    bidx = sb['idx']
                                    bchars = sb.get('chars', 0)
                                    has_cc = sb.get('has_cc', False)
                                    cc_str = f"  {PASTEL_GREEN}CC●{RESET}" if has_cc else ''
                                    stripped_str = f"  {YELLOW}[STRIPPED]{RESET}" if 'replaced_system_prompt' in mods and bidx == 2 else ''
                                    block_key = ('sys_block', entry_idx, bidx)
                                    is_block_expanded = expand_states.get(block_key, False)
                                    block_symbol = '\u25bc' if is_block_expanded else '\u25b6'
                                    all_lines.append(f"      {DIM}{block_symbol} [{bidx}]: {_format_k(bchars)}{RESET}{cc_str}{stripped_str}")
                                    line_keys.append(block_key)
                                    if is_block_expanded:
                                        preview = sb.get('preview', '')
                                        if preview:
                                            for raw_line in preview.split('\n'):
                                                if not raw_line:
                                                    all_lines.append(f"        {DIM}{RESET}")
                                                    line_keys.append(None)
                                                    continue
                                                for chunk_start in range(0, len(raw_line), wrap_width_meta):
                                                    all_lines.append(f"        {DIM}{raw_line[chunk_start:chunk_start + wrap_width_meta]}{RESET}")
                                                    line_keys.append(None)
                                        else:
                                            all_lines.append(f"        {DIM}(no preview){RESET}")
                                            line_keys.append(None)
                        # Tools (expandable)
                        tools_count = entry.get('tools_count', 0)
                        tools_chars = entry.get('tools_total_chars', 0)
                        tools_hash = entry.get('tools_hash', '')
                        tools_names = entry.get('tools_names', [])
                        if tools_count:
                            tools_key = ('tools', entry_idx)
                            is_tools_expanded = expand_states.get(tools_key, False)
                            tools_symbol = '\u25bc' if is_tools_expanded else '\u25b6'
                            hash_str = f"  hash:{tools_hash[:8]}" if tools_hash else ''
                            prev_tools_hash = prev_entry_for_delta.get('tools_hash', '') if prev_entry_for_delta else ''
                            prev_tools_names = prev_entry_for_delta.get('tools_names', []) if prev_entry_for_delta else []
                            tools_changed = bool(prev_tools_hash) and prev_tools_hash != tools_hash
                            added = [n for n in tools_names if n not in set(prev_tools_names)] if tools_changed else []
                            removed = [n for n in prev_tools_names if n not in set(tools_names)] if tools_changed else []
                            delta_parts = []
                            if added:
                                delta_parts.append(f"{RED}+{len(added)}{RESET}")
                            if removed:
                                delta_parts.append(f"{RED}-{len(removed)}{RESET}")
                            tools_delta_str = f"  {'  '.join(delta_parts)}" if delta_parts else ''
                            all_lines.append(f"    {DIM}{tools_symbol} tools: {tools_count} defs ({_format_k(tools_chars)}){hash_str}{RESET}{tools_delta_str}")
                            line_keys.append(tools_key)
                            if is_tools_expanded:
                                wrap_w = max(20, pane_width - 12)
                                tools_defs = entry.get('tools_defs', [])
                                for tool_idx, tool_def in enumerate(tools_defs):
                                    t_name = tool_def.get('name', '')
                                    is_stripped_tool = t_name in TOOL_BLOCKLIST
                                    # Stripped tools are not actually sent — suppress the + marker
                                    marker = f" {RED}+{RESET}" if (t_name in added and not is_stripped_tool) else ''
                                    tool_key = ('tool', entry_idx, tool_idx)
                                    is_tool_exp = expand_states.get(tool_key, False)
                                    t_symbol = '\u25bc' if is_tool_exp else '\u25b6'
                                    if is_stripped_tool:
                                        all_lines.append(f"      {DIM_YELLOW_BG}{DIM}{t_symbol} {t_name}{RESET}")
                                    else:
                                        all_lines.append(f"      {DIM}{t_symbol} {t_name}{RESET}{marker}")
                                    line_keys.append(tool_key)
                                    if is_tool_exp:
                                        if t_name == 'Agent':
                                            # Show trimmed description (what is actually sent to API)
                                            for raw_line in AGENT_TRIMMED_DESCRIPTION.split('\n'):
                                                if not raw_line:
                                                    all_lines.append(f"        {DIM}{RESET}")
                                                    line_keys.append(None)
                                                    continue
                                                for chunk_start in range(0, len(raw_line), wrap_w):
                                                    all_lines.append(f"        {DIM}{raw_line[chunk_start:chunk_start + wrap_w]}{RESET}")
                                                    line_keys.append(None)
                                            # Show original description with stripped background
                                            all_lines.append(f"        {DIM_YELLOW_BG}{DIM}(original, stripped){RESET}")
                                            line_keys.append(None)
                                            original_desc = tool_def.get('description', '')
                                            if original_desc:
                                                for raw_line in original_desc.split('\n'):
                                                    if not raw_line:
                                                        all_lines.append(f"        {DIM_YELLOW_BG}{DIM}{RESET}")
                                                        line_keys.append(None)
                                                        continue
                                                    for chunk_start in range(0, len(raw_line), wrap_w):
                                                        all_lines.append(f"        {DIM_YELLOW_BG}{DIM}{raw_line[chunk_start:chunk_start + wrap_w]}{RESET}")
                                                        line_keys.append(None)
                                        else:
                                            description = tool_def.get('description', '')
                                            if description:
                                                for raw_line in description.split('\n'):
                                                    if not raw_line:
                                                        all_lines.append(f"        {DIM}{RESET}")
                                                        line_keys.append(None)
                                                        continue
                                                    for chunk_start in range(0, len(raw_line), wrap_w):
                                                        all_lines.append(f"        {DIM}{raw_line[chunk_start:chunk_start + wrap_w]}{RESET}")
                                                        line_keys.append(None)
                                            input_schema = tool_def.get('input_schema', {})
                                            props = input_schema.get('properties', {}) if isinstance(input_schema, dict) else {}
                                            required_props = input_schema.get('required', []) if isinstance(input_schema, dict) else []
                                            for param_name, param_info in props.items():
                                                if isinstance(param_info, dict):
                                                    param_type = param_info.get('type', '?')
                                                    param_desc = param_info.get('description', '')
                                                    req_marker = '*' if param_name in required_props else ''
                                                    param_line = f"{param_name}{req_marker}: {param_type}"
                                                    if param_desc:
                                                        param_line += f" \u2014 {param_desc}"
                                                    for chunk_start in range(0, len(param_line), wrap_w):
                                                        all_lines.append(f"        {DIM}{param_line[chunk_start:chunk_start + wrap_w]}{RESET}")
                                                        line_keys.append(None)
                        messages = entry.get('messages', [])
                        stripped_indices = set()
                        for _idx, _msg in enumerate(messages):
                            _preview = _msg.get('content_preview', '')
                            if 'stripped_task_tools_nag' in mods and 'task tools haven' in _preview:
                                stripped_indices.add(_idx)
                            if 'removed_plan_mode_sr' in mods and 'Plan mode is active' in _preview:
                                stripped_indices.add(_idx)
                            if 'stripped_rejection_message' in mods and "doesn't want to proceed" in _preview:
                                stripped_indices.add(_idx)
                        prev_msg_count = prev_entry_for_delta.get('message_count', 0) if prev_entry_for_delta is not None else 0
                        wrap_width = max(20, pane_width - 8)
                        if prev_msg_count < len(messages):
                            for msg_idx in range(prev_msg_count, len(messages)):
                                msg = messages[msg_idx]
                                role = msg.get('role', '?')[:4]
                                msg_type = msg.get('type', 'text')
                                chars = msg.get('chars', 0)
                                chars_fmt = f"{chars:,}c"
                                has_cc = msg.get('has_cache_control', False)
                                cc_marker = f"  {PASTEL_GREEN}CC ●{RESET}" if has_cc else ''
                                is_stripped = msg_idx in stripped_indices
                                if is_stripped:
                                    all_lines.append(f"    {DIM}[{msg_idx:3d}] {role:<4}  {msg_type:<20} {chars_fmt:>8}{RESET}{cc_marker}  {YELLOW}[STRIPPED]{RESET}")
                                else:
                                    color = PASTEL_GREEN if has_cc else WHITE
                                    all_lines.append(f"    {color}[{msg_idx:3d}] {role:<4}  {msg_type:<20} {chars_fmt:>8}{RESET}{cc_marker}")
                                line_keys.append(None)
                                preview = msg.get('content_preview', '')
                                if preview:
                                    for raw_line in preview.split('\n'):
                                        if not raw_line:
                                            all_lines.append(f"      {DIM}{RESET}")
                                            line_keys.append(None)
                                            continue
                                        for chunk_start in range(0, len(raw_line), wrap_width):
                                            all_lines.append(f"      {DIM}{raw_line[chunk_start:chunk_start + wrap_width]}{RESET}")
                                            line_keys.append(None)
                        else:
                            prev_messages = prev_entry_for_delta.get('messages', []) if prev_entry_for_delta is not None else []
                            diff_start = len(messages)
                            for j in range(1, min(len(messages), len(prev_messages)) + 1):
                                curr_msg = messages[-j]
                                prev_msg = prev_messages[-j]
                                if curr_msg.get('chars', 0) != prev_msg.get('chars', 0) or curr_msg.get('type', '') != prev_msg.get('type', ''):
                                    diff_start = len(messages) - j
                                else:
                                    break
                            for msg_idx in range(diff_start, len(messages)):
                                msg = messages[msg_idx]
                                prev_msg = prev_messages[msg_idx] if msg_idx < len(prev_messages) else None
                                role = msg.get('role', '?')[:4]
                                msg_type = msg.get('type', 'text')
                                curr_chars = msg.get('chars', 0)
                                prev_chars = prev_msg.get('chars', 0) if prev_msg else 0
                                delta_chars = curr_chars - prev_chars
                                is_stripped = msg_idx in stripped_indices
                                stripped_marker = f"  {YELLOW}[STRIPPED]{RESET}" if is_stripped else ''
                                all_lines.append(f"    {DIM}[{msg_idx:3d}] {role:<4}  {msg_type:<20}{RESET}{stripped_marker}")
                                line_keys.append(None)
                                tail = msg.get('content_tail', '')
                                if tail and delta_chars > 0:
                                    new_content = tail[-delta_chars:] if len(tail) > delta_chars else tail
                                    wrap_width = max(20, pane_width - 8)
                                    for raw_line in new_content.split('\n'):
                                        if not raw_line:
                                            all_lines.append(f"      {DIM}{RESET}")
                                            line_keys.append(None)
                                            continue
                                        for chunk_start in range(0, len(raw_line), wrap_width):
                                            all_lines.append(f"      {DIM}{raw_line[chunk_start:chunk_start + wrap_width]}{RESET}")
                                            line_keys.append(None)
                    if len(entry.get('cache_breakpoints', [])) >= 1:
                        prev_entry_for_delta = entry

            main_entries = [e for _, e in group['entry_pairs'] if len(e.get('cache_breakpoints', [])) >= 1]
            if main_entries:
                prev_group_last_entry = main_entries[-1]
            prev_effort = effort
            prev_budget = budget
            prev_think_type = think_type
            all_lines.append('')
            line_keys.append(None)
    else:
        for entry_idx, entry in enumerate(entries):
            model_short = _shorten_model(entry.get('model', '?'))
            if model_short == 'haiku':
                num_label = 'H'
            else:
                bp_len = len(entry.get('cache_breakpoints', []))
                if entry_idx == 0 or bp_len >= 1:
                    opus_req_num += 1
                    sub_req_num = 0
                    num_label = f'#{opus_req_num}'
                else:
                    sub_req_num += 1
                    num_label = f'#{opus_req_num}.{sub_req_num}'
            e_lines, e_keys = _render_entry_lines(entry_idx, entry, entries, expand_states, pane_width, indent='', num_label=num_label)
            all_lines.extend(e_lines)
            line_keys.extend(e_keys)
            all_lines.append('')
            line_keys.append(None)

    while all_lines and all_lines[-1] == '':
        all_lines.pop()
        line_keys.pop()

    viewport_lines = max(1, pane_height - 1)
    max_scroll = max(0, len(all_lines) - viewport_lines)
    clamped_offset = min(scroll_offset, max_scroll)
    start = max(0, len(all_lines) - viewport_lines - clamped_offset)
    end = start + viewport_lines

    visible_lines = all_lines[start:end]
    visible_keys = line_keys[start:end]

    if line_map is not None:
        line_map.clear()
        for row_idx, key in enumerate(visible_keys):
            if key is not None:
                line_map[row_idx + 1] = key

    result_lines = []
    for row_offset, line in enumerate(visible_lines):
        row = row_offset + 1
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
    global _proxy_jsonl_position, _proxy_cache_turns
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
                    _proxy_jsonl_position = 0
                    _proxy_cache_turns = []
                    input_changed = True
                new_entries, proxy_log_position = parse_proxy_log(_monitor.active_project_filter, proxy_log_position)
                filtered = [e for e in new_entries if e.get('timestamp', '') >= session_start_ts]
                proxy_entries.extend(filtered)
                # Build cache turns from session JSONL for turn grouping
                main_sessions = _monitor.get_main_session_files()
                if main_sessions:
                    filepath = main_sessions[0]
                    _proxy_cache_turns, _proxy_jsonl_position = build_cache_turns(filepath, _proxy_jsonl_position, _proxy_cache_turns)
                # Auto-expand latest turn so new requests are visible without restart
                if filtered and _proxy_cache_turns:
                    latest_turn_key = ('turn', len(_proxy_cache_turns) - 1)
                    if latest_turn_key not in proxy_expand_states:
                        proxy_expand_states[latest_turn_key] = True
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
                output = format_proxy_block(proxy_entries, proxy_expand_states, proxy_line_map, proxy_hover_row, pane_height, pane_width, proxy_scroll_offset, turns=_proxy_cache_turns)
                if output != last_output:
                    print("\033[2J\033[3J\033[H", end='', flush=True)
                    if output:
                        print(output)
                    last_output = output
            time.sleep(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()
