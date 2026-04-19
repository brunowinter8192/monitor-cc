# INFRASTRUCTURE
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

from .constants import (
    YELLOW, ORANGE, DIM, WHITE, RESET, HOVER_BG,
    POLL_INTERVAL, INPUT_POLL_INTERVAL,
)
from .click_handler import (
    read_keypress, setup_keyboard_input, restore_terminal,
    enable_mouse, disable_mouse, read_mouse_event,
)
from .proxy_forensics import pairs, format_timestamp_local, Pair
from .proxy_display.parser import get_proxy_session_start_ts
from .utils import visual_line_count, first_word_of_call, _iso_to_float

# Tools whose high ratio is structural (content-driven), not actionable waste
RATIO_EXCLUDED_TOOLS = ['Edit', 'Write', 'worker_send']

# Default ratio threshold; keys 1-9 set it, key 0 resets to default
WASTE_THRESHOLD_DEFAULT = 3.0

# Max source lines shown in expanded command / output sections
CMD_MAX_LINES = 20
OUT_MAX_LINES = 10

# Module state
waste_threshold: float = WASTE_THRESHOLD_DEFAULT
_waste_above: List[Pair] = []
waste_expand_states: Dict[int, bool] = {}
waste_line_map: Dict[int, int] = {}
waste_hover_row: Optional[int] = None
waste_scroll_offset: int = 0
_waste_all_events: List[dict] = []
_waste_worker_all_events: List[dict] = []
_waste_worker_log_positions: Dict[str, int] = {}
_waste_log_path: Optional[Path] = None
_waste_log_position: int = 0
_last_project_filter: Optional[str] = None
_monitor_start_ts: float = 0.0


# ORCHESTRATOR

def run_waste_loop() -> None:
    """Event loop for the waste-calls tmux pane."""
    from . import monitor as _monitor
    global waste_threshold, waste_expand_states, waste_line_map, waste_hover_row
    global waste_scroll_offset, _waste_log_path, _waste_log_position
    global _last_project_filter, _waste_above, _monitor_start_ts
    global _waste_all_events, _waste_worker_all_events, _waste_worker_log_positions

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

            time.sleep(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()


# FUNCTIONS

# Locate current proxy JSONL via marker file; returns Path or None
def _find_proxy_log_path(project_filter: Optional[str]) -> Optional[Path]:
    if not project_filter:
        return None
    root = os.environ.get('MONITOR_CC_ROOT', '')
    if not root:
        # src/waste_pane.py → src/ → Monitor_CC/
        root = str(Path(__file__).resolve().parent.parent)
    session_id = hashlib.md5(project_filter.encode()).hexdigest()[:8]
    marker_file = Path(root) / 'src' / 'logs' / f'.proxy_session_{session_id}'
    log_id = session_id
    if marker_file.exists():
        try:
            lines = marker_file.read_text(encoding='utf-8').splitlines()
            if len(lines) >= 2 and lines[1].strip():
                log_id = lines[1].strip()
        except OSError:
            pass
    return Path(root) / 'src' / 'logs' / f'api_requests_{log_id}.jsonl'


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


# Rebuild _waste_above from all accumulated events using current waste_threshold
def _rebuild_above() -> None:
    global _waste_above
    events = _waste_all_events + _waste_worker_all_events
    if not events:
        _waste_above = []
        return
    all_pairs = list(pairs(events))
    _waste_above = sorted(
        [p for p in all_pairs
         if p.ratio >= waste_threshold
         and not any(ex in p.tu.name for ex in RATIO_EXCLUDED_TOOLS)],
        key=lambda p: -p.ratio,
    )


# Read new proxy entries, rebuild waste_pairs above threshold; returns True if data changed
def _refresh_waste_data(project_filter: Optional[str]) -> bool:
    global _waste_log_path, _waste_log_position, _last_project_filter, _waste_above
    global waste_expand_states, waste_scroll_offset, waste_hover_row, _monitor_start_ts
    global _waste_all_events, _waste_worker_all_events, _waste_worker_log_positions

    log_path = _find_proxy_log_path(project_filter)

    # Reset on project change or log file path change
    if project_filter != _last_project_filter or log_path != _waste_log_path:
        _waste_all_events.clear()
        _waste_worker_all_events.clear()
        _waste_worker_log_positions.clear()
        _waste_log_path = log_path
        _waste_log_position = 0
        _waste_above = []
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
        _waste_all_events.clear()
        _waste_worker_all_events.clear()
        waste_expand_states.clear()
        waste_scroll_offset = 0

    data_changed = False
    new_events, new_position = _read_new_events(log_path, _waste_log_position)
    if new_events:
        _waste_log_position = new_position
        # Filter out events older than session start, then accumulate.
        # proxy_forensics deduplicates by first occurrence, so each ToolUse gets
        # the timestamp of its first API call — not the latest.
        new_events = [e for e in new_events
                      if not e.get('timestamp') or _iso_to_float(e['timestamp']) >= _monitor_start_ts]
        if new_events:
            _waste_all_events.extend(new_events)
            data_changed = True

    # Scan worker proxy logs inline: scan_worker_logs from parser.py strips raw_payload
    # via _extract_raw_payload_fields; waste_pane needs raw_payload for proxy_forensics.pairs()
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
                if w_events:
                    _waste_worker_all_events.extend(w_events)
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
    wrap_width = max(20, pane_width - 6)

    all_lines: List[str] = []
    all_keys: List[Optional[int]] = []

    if not _waste_above:
        if not _waste_all_events and not _waste_worker_all_events:
            if _waste_log_path is None:
                msg = 'No project filter — start monitor with --project.'
            else:
                msg = f'Proxy log not found: {_waste_log_path.name}'
            all_lines.append(f'{DIM}{msg}{RESET}')
        else:
            thr = int(waste_threshold) if waste_threshold == int(waste_threshold) else waste_threshold
            all_lines.append(f'{DIM}No pairs above threshold {thr}.{RESET}')
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
            w_prefix = f'{YELLOW}W:{worker_name}{RESET} ' if worker_name else ''

            header_line = (
                f'{DIM}{symbol} [{ts}]{RESET} '
                f'{w_prefix}'
                f'{WHITE}{tool_name:<16}{RESET} '
                f'{DIM}ratio={RESET}{ORANGE}{ratio_str}{RESET}  '
                f'{DIM}in={in_str}  out={out_str}{RESET}'
            )

            if is_expanded:
                all_lines.append(header_line)
                all_keys.append(idx)

                # Command section
                if p.tu.name == 'Bash':
                    cmd_text = p.tu.input.get('command', '')
                else:
                    cmd_text = json.dumps(p.tu.input, ensure_ascii=False)

                all_lines.append(f'  {DIM}COMMAND ({p.tu.input_chars:,} chars):{RESET}')
                all_keys.append(None)

                cmd_lines = cmd_text.split('\n')
                for cline in cmd_lines[:CMD_MAX_LINES]:
                    chunk = cline[:wrap_width]
                    all_lines.append(f'    {DIM}{chunk}{RESET}')
                    all_keys.append(None)
                if len(cmd_lines) > CMD_MAX_LINES:
                    remaining = len(cmd_lines) - CMD_MAX_LINES
                    all_lines.append(f'    {DIM}… ({remaining} more lines){RESET}')
                    all_keys.append(None)

                # Output section
                if isinstance(p.tr.content, str):
                    out_text = p.tr.content
                else:
                    out_text = json.dumps(p.tr.content, ensure_ascii=False)

                all_lines.append(f'  {DIM}OUTPUT ({p.tr.output_chars:,} chars):{RESET}')
                all_keys.append(None)

                out_lines = out_text.split('\n')
                for oline in out_lines[:OUT_MAX_LINES]:
                    chunk = oline[:wrap_width]
                    all_lines.append(f'    {DIM}{chunk}{RESET}')
                    all_keys.append(None)
                if len(out_lines) > OUT_MAX_LINES:
                    remaining = len(out_lines) - OUT_MAX_LINES
                    all_lines.append(f'    {DIM}… ({remaining} more lines){RESET}')
                    all_keys.append(None)

                all_lines.append('')
                all_keys.append(None)
            else:
                inline = first_word_of_call(p.tu.name, p.tu.input)
                collapsed_line = f'{header_line}  {DIM}{inline}{RESET}'
                all_lines.append(collapsed_line)
                all_keys.append(idx)

    # Apply scroll viewport
    visible_lines = all_lines[waste_scroll_offset:waste_scroll_offset + content_height]
    visible_keys = all_keys[waste_scroll_offset:waste_scroll_offset + content_height]

    rendered: List[str] = []
    header_offset = 2  # row 1 = header line, body starts at row 2
    screen_row = header_offset
    for row_offset, line in enumerate(visible_lines):
        key = visible_keys[row_offset]
        span = visual_line_count(line, pane_width)
        if key is not None:
            for r in range(screen_row, screen_row + span):
                waste_line_map[r] = key
        hover_active = (
            waste_hover_row is not None
            and screen_row <= waste_hover_row < screen_row + span
            and key is not None
        )
        rendered.append(f'{HOVER_BG}{line}{RESET}' if hover_active else line)
        screen_row += span

    return header + '\n' + '\n'.join(rendered)
