# INFRASTRUCTURE
from typing import Dict, Optional, Tuple

from src.colors import RESET, YELLOW, DIM, WHITE, GREEN, RED
from src.utils import _ANSI_ESCAPE_RE

_STATUS_COLORS = {
    'working': GREEN,
    'idle': YELLOW,
    'exited': RED,
    'unknown': WHITE,
}

# FUNCTIONS

def _register_marker_regions(regions_out: Dict[Tuple[int, int, int], str], name: str,
                              start: int, end: int, pane_width: int) -> None:
    pos = start
    while pos <= end:
        row, col = divmod(pos, pane_width)
        row_end = row * pane_width + pane_width - 1
        seg_end = min(end, row_end)
        regions_out[(col + 1, seg_end - row * pane_width + 1, row + 1)] = name
        pos = seg_end + 1

def _context_pct_color(pct: Optional[int]) -> str:
    if pct is None:
        return DIM
    return GREEN if pct >= 60 else (YELLOW if pct >= 40 else RED)

def _format_worker_marker(idx: int, w: dict, current_worker: Optional[str]) -> tuple:
    name = w['name']
    status = w.get('status', 'unknown')
    pct = w.get('context_pct')
    star = '*' if name == current_worker else ''
    name_part = f"[{idx}{star}]{name}"
    status_word = status.upper()
    pct_str = f"{pct}%" if pct is not None else "—%"
    plain = f"{name_part} {status_word} {pct_str}"
    name_color = WHITE if name == current_worker else DIM
    status_color = _STATUS_COLORS.get(status, WHITE)
    pct_color = _context_pct_color(pct)
    colored = f"{name_color}{name_part}{RESET} {status_color}{status_word}{RESET} {pct_color}{pct_str}{RESET}"
    return plain, colored

def format_worker_switch_header(workers: list, current_worker: Optional[str],
                                 pane_width: int = 80,
                                 regions_out: Optional[Dict[Tuple[int, int, int], str]] = None,
                                 label: str = 'WORKER-PROXY') -> str:
    label_str = f"{YELLOW}{label}{RESET}  "
    if regions_out is not None:
        regions_out.clear()
    if not workers:
        return label_str + f"{DIM}no workers{RESET}"
    parts = []
    visible_col = len(_ANSI_ESCAPE_RE.sub('', label_str))
    for i, w in enumerate(workers, 1):
        name = w['name']
        plain, colored = _format_worker_marker(i, w, current_worker)
        parts.append(colored)
        if regions_out is not None:
            _register_marker_regions(regions_out, name, visible_col, visible_col + len(plain) - 1, pane_width)
        visible_col += len(plain) + 2
    return label_str + '  '.join(parts)
