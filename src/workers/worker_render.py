# INFRASTRUCTURE
from typing import Optional
import os

from ..colors import RESET, ZEBRA_BG_A, ZEBRA_BG_B, HOVER_BG, LIGHT_RED_BG
from ..utils import truncate_visible
from .. import search_bar
# From token_format.py: format_cache_tracker's nav_out param, called directly (not through
# format_workers_block) for fresh jump-to-match scroll-position computation
from ..format.token_format import format_cache_tracker

# FUNCTIONS

# Compute the per-worker scroll offset that brings a jump-to-match target (a turn/call-level
# match key) into view, via a fresh, self-contained format_cache_tracker(...,nav_out=...) call —
# None when the target can't be resolved (nav didn't find it). Moved out of
# worker_pane._jump_to_workers_match (2026-09) — pure given (key, turns, per_worker_expand,
# pane_width); mirrors format_cache_tracker's own internal -1 against the fixed nested-view
# height (15) format_workers_block always passes.
def compute_jump_scroll_offset(key, turns: list, per_worker_expand: dict, pane_width: int) -> Optional[int]:
    target_key = ('turn', key[2]) if key[1] == 'turn' else (key[1], key[2])
    nav: dict = {}
    format_cache_tracker(turns, per_worker_expand, 15, pane_width - 4, 0, nav_out=nav)
    target_line = nav.get(target_key)
    total_lines = nav.get('total_lines')
    if target_line is None or total_lines is None:
        return None
    viewport_lines = max(1, 15 - 1)
    new_start = max(0, target_line - 2)  # 2 lines context above match
    return max(0, total_lines - viewport_lines - new_start)

# Current (pane_height, pane_width) for the workers pane, falling back to a fixed default when
# unavailable (piped stdout, no tty). Unlike proxy_display's own _terminal_size, pane_height is
# the RAW terminal line count (no -1 adjustment) — _build_workers_output derives content_height
# by subtracting _WORKERS_SEARCH_BAR_LINES itself, matching the pre-split inline try/except.
def _workers_terminal_size(default_lines: int = 50, default_cols: int = 80) -> tuple:
    try:
        term = os.get_terminal_size()
        return term.lines, term.columns
    except OSError:
        return default_lines, default_cols

# Clamp scroll_offset against total_lines/content_height and compute the viewport start index —
# returning (clamped_offset, vp_start). Pure; the caller writes clamped_offset back into its own
# worker_scroll_offset global.
def _compute_viewport(total_lines: int, content_height: int, scroll_offset: int) -> tuple:
    max_offset = max(0, total_lines - content_height)
    clamped_offset = min(scroll_offset, max_offset)
    vp_start = max(0, total_lines - content_height - clamped_offset)
    return clamped_offset, vp_start

# Resolve the copyable key at/above hover_row, preferring whichever of worker_cache_line_map /
# worker_line_map has the CLOSER ancestor row — a plain worker_line_map-first fallback would
# always shadow a cache-row hover (its backward search never stops at cache rows, so it always
# finds the owning worker's header first), making the cache-map fallback unreachable. Moved out of
# worker_pane.py (2026-09, helper-extraction milestone) — pure, takes both maps explicitly.
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

# Scroll-wheel handling for a worker row (or the currently-selected worker when the wheel lands
# on an unmapped row) — resolves the target worker and nudges its per-worker scroll offset by ±3.
# Moved out of _handle_workers_mouse (2026-09) — no scalar-global rebind (only a dict item
# mutation on worker_scroll_offsets, passed by reference), so safe to relocate; returns bool
# (True unless no worker could be resolved, matching the pre-split `(False, frozen)` no-op case).
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

# Render the visible slice's rows with zebra/hover backgrounds — mirrors
# proxy_display.format._apply_row_backgrounds's shape. Populates line_map_out (str key rows) /
# cache_line_map_out (tuple key rows) / copy_rows_out (⎘/✓-carrying rows) in place; returns the
# rendered ANSI lines (search bar NOT included — the caller prepends it).
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
        elif LIGHT_RED_BG in line:  # substring, not prefix — a search-match wrap may precede it
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
