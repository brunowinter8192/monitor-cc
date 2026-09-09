# INFRASTRUCTURE
from typing import Optional
import os

from ..colors import RESET, ZEBRA_BG_A, ZEBRA_BG_B, HOVER_BG, LIGHT_RED_BG
from ..utils import truncate_visible
from .. import search_bar
from ..format.token_format import format_cache_tracker

# FUNCTIONS

def compute_jump_scroll_offset(key, turns: list, per_worker_expand: dict, pane_width: int) -> Optional[int]:
    target_key = ('turn', key[2]) if key[1] == 'turn' else (key[1], key[2])
    nav: dict = {}
    format_cache_tracker(turns, per_worker_expand, 15, pane_width - 4, 0, nav_out=nav)
    target_line = nav.get(target_key)
    total_lines = nav.get('total_lines')
    if target_line is None or total_lines is None:
        return None
    viewport_lines = max(1, 15 - 1)
    new_start = max(0, target_line - 2)
    return max(0, total_lines - viewport_lines - new_start)

def _workers_terminal_size(default_lines: int = 50, default_cols: int = 80) -> tuple:
    try:
        term = os.get_terminal_size()
        return term.lines, term.columns
    except OSError:
        return default_lines, default_cols

def _compute_viewport(total_lines: int, content_height: int, scroll_offset: int) -> tuple:
    max_offset = max(0, total_lines - content_height)
    clamped_offset = min(scroll_offset, max_offset)
    vp_start = max(0, total_lines - content_height - clamped_offset)
    return clamped_offset, vp_start

def _resolve_workers_hover_key(hover_row: Optional[int], worker_cache_line_map: dict, worker_line_map: dict):
    if hover_row is None:
        return None
    cache_row = worker_row = None
    for r in range(hover_row, 0, -1):
        if cache_row is None and r in worker_cache_line_map:
            cache_row = r
        if worker_row is None and r in worker_line_map:
            worker_row = r
        if cache_row is not None and worker_row is not None:
            break
    if cache_row is not None and (worker_row is None or cache_row > worker_row):
        return worker_cache_line_map[cache_row]
    return worker_line_map.get(worker_row)

def apply_scroll(button: int, row: int, worker_cache_line_map: dict, worker_line_map: dict,
                  selected_name: Optional[str], worker_scroll_offsets: dict) -> bool:
    w_name = None
    cache_hit = worker_cache_line_map.get(row)
    if cache_hit is not None:
        w_name = cache_hit[0]
    else:
        map_hit = worker_line_map.get(row)
        w_name = map_hit if map_hit is not None else selected_name
    if w_name is None:
        return False
    current = worker_scroll_offsets.get(w_name, 0)
    delta = 3 if button == 64 else -3
    worker_scroll_offsets[w_name] = max(0, current + delta)
    return True

def _render_workers_rows(visible_all: list, visible_keys: list, hover_row: Optional[int],
                          start_phys_row: int, parent_count_start: int, pane_width: int,
                          line_map_out: dict, cache_line_map_out: dict, copy_rows_out: set) -> list:
    result_lines = []
    phys_row = start_phys_row
    parent_count = parent_count_start
    for line, key in zip(visible_all, visible_keys):
        if isinstance(key, str):
            zebra_bg = ZEBRA_BG_B if parent_count % 2 else ZEBRA_BG_A
            parent_count += 1
        else:
            zebra_bg = ZEBRA_BG_A
        is_hovered = key is not None and hover_row is not None and phys_row == hover_row
        if is_hovered:
            chosen_bg = HOVER_BG
        elif LIGHT_RED_BG in line:
            chosen_bg = LIGHT_RED_BG
        else:
            chosen_bg = zebra_bg
        line = search_bar.resolve_bg_restore(line, chosen_bg)
        if key is not None and ('⎘' in line or '✓' in line):
            copy_rows_out.add(phys_row)
        trunc = truncate_visible(line, pane_width)
        result_lines.append(f"{chosen_bg}{trunc}\033[K{RESET}")
        if isinstance(key, str):
            line_map_out[phys_row] = key
        elif isinstance(key, tuple):
            cache_line_map_out[phys_row] = key
        phys_row += 1
    return result_lines
