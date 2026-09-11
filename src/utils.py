# INFRASTRUCTURE
from datetime import datetime
import re
import unicodedata

from .colors import RESET, YELLOW
from .constants import WORKER_COL_WIDTH

_ANSI_ESCAPE_RE = re.compile(r'\x1b\[[0-9;]*m')

def _cell_width(ch: str) -> int:
    cp = ord(ch)
    if 0x1F000 <= cp <= 0x1FAFF or 0x2600 <= cp <= 0x27BF:
        return 2
    if unicodedata.east_asian_width(ch) in ('W', 'F'):
        return 2
    return 1

# FUNCTIONS

def format_timestamp(iso_timestamp: str) -> str:
    if not iso_timestamp:
        return '00:00:00'
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
        return dt.astimezone().strftime('%H:%M:%S')
    except ValueError:
        return '00:00:00'

def first_word_of_call(tool_name: str, tool_call_input: dict) -> str:
    if not tool_call_input:
        return ''
    if tool_name == 'Bash':
        cmd = tool_call_input.get('command', '')
        parts = cmd.split()
        return parts[0] if parts else ''
    if tool_name == 'Grep':
        pat = tool_call_input.get('pattern', '')
        parts = pat.split()
        return parts[0] if parts else ''
    if tool_name in ('Glob', 'Read', 'Edit', 'Write'):
        key = 'pattern' if tool_name == 'Glob' else 'file_path'
        return tool_call_input.get(key, '')
    return ''

def format_worker_prefix(name: str) -> str:
    if not name:
        return ' ' * (WORKER_COL_WIDTH + 3)
    if len(name) > WORKER_COL_WIDTH:
        name = name[:WORKER_COL_WIDTH - 1] + '\u2026'
    return f'{YELLOW}W:{name:<{WORKER_COL_WIDTH}}{RESET} '

def visual_line_count(line: str, pane_width: int) -> int:
    visible = _ANSI_ESCAPE_RE.sub('', line)
    if not visible:
        return 1
    return max(1, (len(visible) + pane_width - 1) // pane_width)

def append_copy_symbol(line: str, copy_sym: str, pane_width: int) -> str:
    stripped = _ANSI_ESCAPE_RE.sub('', line)
    sym_cells = _cell_width(copy_sym)
    visible_len = sum(_cell_width(ch) for ch in stripped)
    pad = pane_width - 1 - sym_cells - visible_len
    if pad >= 0:
        return line + ' ' * pad + ' ' + copy_sym
    return line

def compute_header_rule_len(prefix_text: str, btn_label: str, rule_cap: int, pane_width: int,
                             rule_min: int = 4, gap: int = 1) -> tuple:
    full_rule_len = min(pane_width, rule_cap)
    if full_rule_len + len(prefix_text) + gap + len(btn_label) <= pane_width:
        return full_rule_len, True
    shrunk = pane_width - len(prefix_text) - gap - len(btn_label)
    if shrunk >= rule_min:
        return shrunk, True
    return max(0, min(full_rule_len, pane_width - len(prefix_text))), False

def highlight_query_in_line(line: str, query: str, match_bg: str, restore_bg: str = '\033[49m') -> str:
    if not query or not line:
        return line
    stripped = _ANSI_ESCAPE_RE.sub('', line)
    q_lower = query.lower()
    s_lower = stripped.lower()
    if q_lower not in s_lower:
        return line
    seen: set = set()
    pos = 0
    while True:
        p = s_lower.find(q_lower, pos)
        if p == -1:
            break
        seen.add(stripped[p:p + len(query)])
        pos = p + 1
    result = line
    for chunk in seen:
        parts = result.split(chunk)
        if len(parts) < 2:
            continue
        result = f"{match_bg}{chunk}{restore_bg}".join(parts)
    return result

def truncate_visible(line: str, pane_width: int) -> str:
    if pane_width <= 0:
        return line
    stripped = _ANSI_ESCAPE_RE.sub('', line)
    if sum(_cell_width(ch) for ch in stripped) <= pane_width:
        return line
    budget = pane_width - 1
    width = 0
    i = 0
    while i < len(line):
        m = _ANSI_ESCAPE_RE.match(line, i)
        if m:
            i = m.end()
            continue
        cw = _cell_width(line[i])
        if width + cw > budget:
            break
        width += cw
        i += 1
    return line[:i] + '\u2026'

def wrap_visible(text: str, width_cells: int) -> list:
    if width_cells <= 0:
        return [text]
    words = text.split(' ')
    lines = []
    current = ''
    current_w = 0
    for word in words:
        word_w = sum(_cell_width(ch) for ch in word)
        if current and current_w + 1 + word_w > width_cells:
            lines.append(current)
            current = ''
            current_w = 0
        if word_w > width_cells:
            if current:
                lines.append(current)
                current = ''
                current_w = 0
            buf = ''
            buf_w = 0
            for ch in word:
                cw = _cell_width(ch)
                if buf and buf_w + cw > width_cells:
                    lines.append(buf)
                    buf = ''
                    buf_w = 0
                buf += ch
                buf_w += cw
            current = buf
            current_w = buf_w
        elif current:
            current = f"{current} {word}"
            current_w = current_w + 1 + word_w
        else:
            current = word
            current_w = word_w
    lines.append(current)
    return lines
