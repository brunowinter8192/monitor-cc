# INFRASTRUCTURE
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

from ..constants import (
    YELLOW, ORANGE, DIM, WHITE, RESET, HOVER_BG, ZEBRA_BG_A, ZEBRA_BG_B, SOFT_RESET,
    DIM_YELLOW_BG, POLL_INTERVAL, INPUT_POLL_INTERVAL,
)
from ..input.click_handler import (
    read_keypress, setup_keyboard_input, restore_terminal,
    enable_mouse, disable_mouse, read_mouse_event,
    resolve_parent_key, copy_to_clipboard, wait_for_input,
)
from ..proxy_display.parser import get_proxy_session_start_ts, find_proxy_log_path
from ..utils import truncate_visible, first_word_of_call, _iso_to_float, format_worker_prefix
from ..format.strip_marker import highlight_stripped, build_tool_result_strip_lookup
from .waste_forensics import pairs, format_timestamp_local, Pair

# Tools whose high ratio is structural (content-driven), not actionable waste
RATIO_EXCLUDED_TOOLS = ['Edit', 'Write', 'worker_send']

# Default ratio threshold; keys 1-9 set it, key 0 resets to default
WASTE_THRESHOLD_DEFAULT = 3.0

# Max source lines shown in expanded command / output sections
CMD_MAX_LINES = 20
OUT_MAX_LINES = 10

# Maximum matched pairs retained across opus + worker logs; oldest dropped on overflow
_WASTE_PAIRS_CAP = 5000

# Module state
waste_threshold: float = WASTE_THRESHOLD_DEFAULT
_waste_above: List[Pair] = []
waste_expand_states: Dict[int, bool] = {}
waste_line_map: Dict[int, int] = {}
waste_hover_row: Optional[int] = None
waste_scroll_offset: int = 0
_waste_all_pairs: Dict[str, Pair] = {}
_waste_total_pairs_seen: int = 0
_waste_worker_log_positions: Dict[str, int] = {}
_waste_log_path: Optional[Path] = None
_waste_log_position: int = 0
_last_project_filter: Optional[str] = None
_monitor_start_ts: float = 0.0
_strip_by_tool_result_id: Dict[str, tuple] = {}  # tool_use_id → (pre_strip_text, removed_chunks)


# ORCHESTRATOR

def run_waste_loop() -> None:
    """Event loop for the waste-calls tmux pane."""
    from ..core import monitor as _monitor
    global waste_threshold, waste_expand_states, waste_line_map, waste_hover_row
    global waste_scroll_offset, _waste_log_path, _waste_log_position
    global _last_project_filter, _waste_above, _monitor_start_ts
    global _waste_all_pairs, _waste_total_pairs_seen, _waste_worker_log_positions
    global _strip_by_tool_result_id

    _monitor_start_ts = time.time()
    last_output = None
    last_data_refresh = 0.0
    setup_keyboard_input()
    enable_mouse()
    try:
        while True:
            input_changed = False

            # Input phase — drain all pending keystrokes/mouse events
            while True:
                char = read_keypress()
                if char is None:
                    break
                if char == '\033':
                    event = read_mouse_event(char)
                    if event is not None:
                        button, col, row = event
                        if button == 0:
                            idx = waste_line_map.get(row)
                            if idx is not None:
                                waste_expand_states[idx] = not waste_expand_states.get(idx, False)
                                input_changed = True
                        elif button == 64:
                            # Wheel up → scroll viewport towards beginning (lower offset)
                            waste_scroll_offset = max(0, waste_scroll_offset - 3)
                            input_changed = True
                        elif button == 65:
                            # Wheel down → scroll viewport towards end (higher offset)
                            waste_scroll_offset = waste_scroll_offset + 3
                            input_changed = True
                        elif button >= 32:
                            waste_hover_row = row
                            input_changed = True
                elif char == 'y':
                    key = resolve_parent_key(waste_line_map, waste_hover_row)
                    if key is not None:
                        copy_to_clipboard(_serialize_waste(key))
                elif char == '0':
                    waste_threshold = WASTE_THRESHOLD_DEFAULT
                    _rebuild_above()
                    waste_scroll_offset = 0
                    waste_expand_states.clear()
                    input_changed = True
                elif char.isdigit():
                    waste_threshold = float(char)
                    _rebuild_above()
                    waste_scroll_offset = 0
                    waste_expand_states.clear()
                    input_changed = True

            # Data refresh phase
            now = time.time()
            if now - last_data_refresh >= POLL_INTERVAL:
                project_filter = _monitor.active_project_filter
                data_changed = _refresh_waste_data(project_filter)
                last_data_refresh = now
                if data_changed:
                    input_changed = True

            # Render phase
            if input_changed:
                try:
                    term = os.get_terminal_size()
                    pane_height = term.lines - 1
                    pane_width = term.columns
                except OSError:
                    pane_height = 50
                    pane_width = 80
                output = _format_waste_pane(pane_height, pane_width)
                if output != last_output:
                    print('\033[2J\033[3J\033[H', end='', flush=True)
                    if output:
                        print(output, end='', flush=True)
                        # Header overdraw: keeps header visible even when body overflows
                        header = _format_waste_header(len(_waste_above))
                        print(f'\033[H{header}\033[K', end='', flush=True)
                    last_output = output

            wait_for_input(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()


# FUNCTIONS

# Serialize a waste-pane pair to full untruncated input + output text for clipboard
def _serialize_waste(idx: int) -> str:
    if idx < 0 or idx >= len(_waste_above):
        return ''
    p = _waste_above[idx]
    input_text = json.dumps(p.tu.input, ensure_ascii=False, indent=2)
    if isinstance(p.tr.content, str):
        output_text = p.tr.content
    else:
        output_text = json.dumps(p.tr.content, ensure_ascii=False, indent=2)
    parts = [
        f"{p.tu.name}  ratio={p.ratio:.1f}  in={p.tu.input_chars}c  out={p.tr.output_chars}c",
        "---INPUT---",
        input_text,
        "---OUTPUT---",
        output_text,
    ]
    return '\n'.join(parts)

# Read new raw proxy events from log_path since byte position; returns (events, new_position)
def _read_new_events(log_path: Path, position: int) -> tuple:
    if not log_path.exists():
        return [], position
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            f.seek(position)
            content = f.read()
        new_position = log_path.stat().st_size
    except OSError:
        return [], position
    events = []
    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get('raw_payload') is None:
            continue
        d['_session_file'] = log_path.name
        events.append(d)
    return events, new_position


# Extract worker_name from proxy log session_file basename (api_requests_worker_{name}_{ts}.jsonl)
def _get_worker_from_session_file(session_file: str) -> str:
    if not session_file or 'api_requests_worker_' not in session_file:
        return ''
    stem = session_file.replace('.jsonl', '')
    return stem.replace('api_requests_worker_', '').rsplit('_', 1)[0]


# Filter and sort _waste_all_pairs into _waste_above based on current threshold
def _rebuild_above() -> None:
    global _waste_above
    _waste_above = sorted(
        [p for p in _waste_all_pairs.values()
         if p.ratio >= waste_threshold
         and not any(ex in p.tu.name for ex in RATIO_EXCLUDED_TOOLS)],
        key=lambda p: p.tu.timestamp,
    )


# Merge pairs and strip data from new raw events into _waste_all_pairs; return True if any pair added
def _merge_new_events(new_events: list) -> bool:
    global _waste_all_pairs, _strip_by_tool_result_id, _waste_total_pairs_seen
    if not new_events:
        return False
    changed = False
    for pair in pairs(new_events):
        if pair.tu.id not in _waste_all_pairs:
            _waste_all_pairs[pair.tu.id] = pair
            _waste_total_pairs_seen += 1
            changed = True
    for tid, strip_data in build_tool_result_strip_lookup(new_events).items():
        if tid not in _strip_by_tool_result_id:
            _strip_by_tool_result_id[tid] = strip_data
    if len(_waste_all_pairs) > _WASTE_PAIRS_CAP:
        sorted_items = sorted(_waste_all_pairs.items(), key=lambda x: x[1].tu.timestamp)
        drop_n = len(_waste_all_pairs) - _WASTE_PAIRS_CAP
        for k, _ in sorted_items[:drop_n]:
            del _waste_all_pairs[k]
            _strip_by_tool_result_id.pop(k, None)
    return changed


# Read new proxy entries, merge pairs, rebuild waste_above; returns True if data changed
def _refresh_waste_data(project_filter: Optional[str]) -> bool:
    global _waste_log_path, _waste_log_position, _last_project_filter, _waste_above
    global waste_expand_states, waste_scroll_offset, waste_hover_row, _monitor_start_ts
    global _waste_all_pairs, _waste_total_pairs_seen, _waste_worker_log_positions
    global _strip_by_tool_result_id

    log_path = find_proxy_log_path(project_filter)

    # Reset on project change or log file path change
    if project_filter != _last_project_filter or log_path != _waste_log_path:
        _waste_all_pairs.clear()
        _waste_total_pairs_seen = 0
        _waste_worker_log_positions.clear()
        _waste_log_path = log_path
        _waste_log_position = 0
        _waste_above = []
        _strip_by_tool_result_id = {}
        waste_expand_states.clear()
        waste_scroll_offset = 0
        waste_hover_row = None
        _last_project_filter = project_filter
        _monitor_start_ts = get_proxy_session_start_ts(project_filter) if project_filter else time.time()

    if not log_path or not log_path.exists():
        return False

    # Detect file truncation (proxy restarted with same path)
    try:
        file_size = log_path.stat().st_size
    except OSError:
        return False
    if file_size < _waste_log_position:
        _waste_log_position = 0
        _waste_all_pairs.clear()
        _waste_total_pairs_seen = 0
        waste_expand_states.clear()
        waste_scroll_offset = 0

    data_changed = False
    new_events, new_position = _read_new_events(log_path, _waste_log_position)
    if new_events:
        _waste_log_position = new_position
        new_events = [e for e in new_events
                      if not e.get('timestamp') or _iso_to_float(e['timestamp']) >= _monitor_start_ts]
        if new_events and _merge_new_events(new_events):
            data_changed = True

    # Scan worker proxy logs inline: scan_worker_logs from parser.py strips raw_payload
    # via _extract_raw_payload_fields; waste_pane needs raw_payload intact for pairs()
    root = os.environ.get('MONITOR_CC_ROOT', '')
    if not root:
        root = str(Path(__file__).resolve().parent.parent)
    logs_dir = Path(root) / 'src' / 'logs'
    if logs_dir.exists():
        for wlog in logs_dir.glob('api_requests_worker_*.jsonl'):
            pos = _waste_worker_log_positions.get(str(wlog), 0)
            w_events, w_pos = _read_new_events(wlog, pos)
            if w_events:
                _waste_worker_log_positions[str(wlog)] = w_pos
                w_events = [e for e in w_events
                            if not e.get('timestamp') or _iso_to_float(e['timestamp']) >= _monitor_start_ts]
                if w_events and _merge_new_events(w_events):
                    data_changed = True

    if not data_changed:
        return False

    _rebuild_above()
    return True


# Render header: "WASTE CALLS  threshold=N  [M above]  [0]=reset [1-9]=set"
def _format_waste_header(above_count: int) -> str:
    thr = int(waste_threshold) if waste_threshold == int(waste_threshold) else waste_threshold
    return (f"{YELLOW}WASTE CALLS{RESET}  "
            f"{DIM}threshold={thr}  [{above_count} above]  "
            f"[0]=reset [1-9]=threshold{RESET}")


# Derive short display name for a tool (strips MCP prefix noise)
def _tool_display_name(name: str) -> str:
    if '__' in name:
        return name.split('__')[-1][:16]
    return name[:16]


# Render waste pane body; fills waste_line_map; returns header + body string
def _format_waste_pane(pane_height: int, pane_width: int) -> str:
    global waste_line_map
    waste_line_map = {}

    above_count = len(_waste_above)
    header = _format_waste_header(above_count)
    content_height = max(1, pane_height - 1)

    all_lines: List[str] = []
    all_keys: List[Optional[int]] = []

    if not _waste_above:
        if _waste_total_pairs_seen == 0:
            if _waste_log_path is None:
                msg = 'No project filter — start monitor with --project.'
            else:
                msg = f'Proxy log not found: {_waste_log_path.name}'
            all_lines.append(f'{DIM}{msg}{SOFT_RESET}')
        else:
            thr = int(waste_threshold) if waste_threshold == int(waste_threshold) else waste_threshold
            all_lines.append(f'{DIM}No pairs above threshold {thr}.{SOFT_RESET}')
        all_keys.append(None)
    else:
        for idx, p in enumerate(_waste_above):
            is_expanded = waste_expand_states.get(idx, False)
            symbol = '\u25bc' if is_expanded else '\u25b6'
            ts = format_timestamp_local(p.tu.timestamp)
            tool_name = _tool_display_name(p.tu.name)
            ratio_str = f'{p.ratio:>6.1f}'
            in_str = f'{p.tu.input_chars:>5}'
            out_str = f'{p.tr.output_chars:>5}'
            worker_name = _get_worker_from_session_file(p.tu.session_file)
            w_prefix = format_worker_prefix(worker_name)

            header_line = (
                f'{DIM}{symbol} [{ts}]{SOFT_RESET} '
                f'{w_prefix}'
                f'{WHITE}{tool_name:<16}{SOFT_RESET} '
                f'{DIM}ratio={SOFT_RESET}{ORANGE}{ratio_str}{SOFT_RESET}  '
                f'{DIM}in={in_str}  out={out_str}{SOFT_RESET}'
            )

            if is_expanded:
                all_lines.append(header_line)
                all_keys.append(idx)

                # Input section
                cmd_text = json.dumps(p.tu.input, ensure_ascii=False)
                all_lines.append(f'  {DIM}INPUT ({p.tu.input_chars:,} chars):{SOFT_RESET}')
                all_keys.append(None)
                rendered_cmd = 0
                for cline in cmd_text.split('\n'):
                    if rendered_cmd >= CMD_MAX_LINES:
                        break
                    all_lines.append(f'    {DIM}{cline}{SOFT_RESET}')
                    all_keys.append(None)
                    rendered_cmd += 1
                if rendered_cmd >= CMD_MAX_LINES:
                    all_lines.append(f'    {DIM}… (truncated){SOFT_RESET}')
                    all_keys.append(None)

                # Output section — use pre-strip content if available, else post-strip
                strip_info = _strip_by_tool_result_id.get(p.tr.tool_use_id)
                if strip_info:
                    pre_strip_text, stripped_chunks = strip_info
                    out_text = highlight_stripped(pre_strip_text or '', stripped_chunks) if pre_strip_text else (
                        p.tr.content if isinstance(p.tr.content, str) else json.dumps(p.tr.content, ensure_ascii=False)
                    )
                elif isinstance(p.tr.content, str):
                    out_text = p.tr.content
                else:
                    out_text = json.dumps(p.tr.content, ensure_ascii=False)
                all_lines.append(f'  {DIM}OUTPUT ({p.tr.output_chars:,} chars):{SOFT_RESET}')
                all_keys.append(None)
                rendered_out = 0
                for oline in out_text.split('\n'):
                    oline = oline.expandtabs(8)
                    if rendered_out >= OUT_MAX_LINES:
                        break
                    all_lines.append(f'    {DIM}{oline}{SOFT_RESET}')
                    all_keys.append(None)
                    rendered_out += 1
                if rendered_out >= OUT_MAX_LINES:
                    all_lines.append(f'    {DIM}… (truncated){SOFT_RESET}')
                    all_keys.append(None)

                all_lines.append('')
                all_keys.append(None)
            else:
                inline = first_word_of_call(p.tu.name, p.tu.input)
                collapsed_line = f'{header_line}  {DIM}{inline}{SOFT_RESET}'
                all_lines.append(collapsed_line)
                all_keys.append(idx)

    # Apply scroll viewport
    visible_lines = all_lines[waste_scroll_offset:waste_scroll_offset + content_height]
    visible_keys = all_keys[waste_scroll_offset:waste_scroll_offset + content_height]

    rendered: List[str] = []
    parent_count = sum(1 for k in all_keys[:waste_scroll_offset] if k is not None)
    header_offset = 2  # row 1 = header line, body starts at row 2
    phys_row = header_offset
    for i, (line, key) in enumerate(zip(visible_lines, visible_keys)):
        if key is not None:
            zebra_bg = ZEBRA_BG_B if parent_count % 2 else ZEBRA_BG_A
            parent_count += 1
        else:
            zebra_bg = ZEBRA_BG_A
        is_hovered = (key is not None and waste_hover_row is not None
                      and phys_row == waste_hover_row)
        if is_hovered:
            chosen_bg = HOVER_BG
        elif DIM_YELLOW_BG in line:
            chosen_bg = DIM_YELLOW_BG
        else:
            chosen_bg = zebra_bg
        if key is not None:
            waste_line_map[phys_row] = key
        rendered.append(f'{chosen_bg}{truncate_visible(line, pane_width)}\033[K{RESET}')
        phys_row += 1

    return header + '\n' + '\n'.join(rendered)
