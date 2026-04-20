# INFRASTRUCTURE
from typing import Dict, Optional
import os
import time

from ..constants import POLL_INTERVAL, INPUT_POLL_INTERVAL, RESET, ZEBRA_BG_A, ZEBRA_BG_B, HOVER_BG, LIGHT_RED_BG
from ..jsonl import read_new_lines, parse_jsonl_lines, extract_cache_turns
from ..input.click_handler import (
    read_keypress, setup_keyboard_input, restore_terminal,
    enable_mouse, disable_mouse, read_mouse_event,
)
from ..format.token_format import format_cache_tracker
from ..utils import truncate_visible

cache_expand_states: Dict[tuple, bool] = {}
cache_line_map: Dict[int, tuple] = {}
cache_hover_row: Optional[int] = None
cache_scroll_offset: int = 0

_cache_jsonl_position: int = 0
_cache_turns: list = []
_cache_current_filepath = None

# FUNCTIONS

# Build cache turns incrementally — only reads new lines since last_position
def build_cache_turns(filepath, last_position: int, existing_turns: list):
    from ..jsonl import get_current_position
    lines = read_new_lines(filepath, last_position)
    new_position = get_current_position(filepath) if filepath.exists() else last_position
    if not lines:
        return existing_turns, last_position
    messages, _ = parse_jsonl_lines(lines)
    new_turns = extract_cache_turns(messages)
    if not new_turns and existing_turns and messages:
        # No user message in this batch → mid-turn requests (user message was read in a prior cycle)
        # Synthesize a user message from the last existing turn so extract_cache_turns
        # can set current_turn and process the assistant messages in this batch
        last_turn = existing_turns[-1]
        synthetic_user = {
            'type': 'user',
            'userType': 'external',
            'message': {'content': last_turn.get('prompt', '')},
            'timestamp': last_turn.get('timestamp', ''),
        }
        new_turns = extract_cache_turns([synthetic_user] + messages)
    if not new_turns:
        return existing_turns, new_position
    if existing_turns and new_turns[0].get('prompt') == existing_turns[-1].get('prompt'):
        # Last existing turn was incomplete (streaming) — merge its api_calls with fresh parse
        merged = dict(existing_turns[-1])
        merged_calls = list(merged.get('api_calls', []))
        for call in new_turns[0].get('api_calls', []):
            new_rid = call.get('request_id', '')
            if new_rid:
                dup_idx = next(
                    (i for i, c in enumerate(merged_calls) if c.get('request_id') == new_rid),
                    None
                )
            else:
                dup_idx = next(
                    (i for i, c in enumerate(merged_calls)
                     if c.get('cache_read') == call.get('cache_read')
                     and c.get('cache_creation') == call.get('cache_creation')
                     and c.get('direct') == call.get('direct')),
                    None
                )
            if dup_idx is None:
                merged_calls.append(call)
            else:
                # Update output_tokens in case streaming advanced
                prev = dict(merged_calls[dup_idx])
                prev['output_tokens'] = max(prev.get('output_tokens', 0), call.get('output_tokens', 0))
                merged_calls[dup_idx] = prev
        merged['api_calls'] = merged_calls
        result = existing_turns[:-1] + [merged] + new_turns[1:]
    else:
        result = existing_turns + new_turns
    return result, new_position

# Runs cache tracker display loop (for dedicated tokens tmux pane)
def run_tokens_loop() -> None:
    from ..core import monitor as _monitor
    global cache_expand_states, cache_line_map, cache_hover_row, cache_scroll_offset
    global _cache_jsonl_position, _cache_turns, _cache_current_filepath
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
                            key = cache_line_map.get(row)
                            if key:
                                cache_expand_states[key] = not cache_expand_states.get(key, False)
                                input_changed = True
                        elif button == 64:
                            cache_scroll_offset = max(0, cache_scroll_offset + 3)
                            input_changed = True
                        elif button == 65:
                            cache_scroll_offset = max(0, cache_scroll_offset - 3)
                            input_changed = True
                        elif button >= 32:
                            cache_hover_row = row
                            input_changed = True

            now = time.time()
            if now - last_data_refresh >= POLL_INTERVAL:
                main_sessions = _monitor.get_main_session_files()
                filepath = main_sessions[0] if main_sessions else None

                if filepath != _cache_current_filepath:
                    # Session changed — reset all incremental state
                    _cache_current_filepath = filepath
                    _cache_jsonl_position = 0
                    _cache_turns = []
                    cache_expand_states.clear()
                    cache_scroll_offset = 0
                    cache_hover_row = None

                if filepath is not None:
                    _cache_turns, _cache_jsonl_position = build_cache_turns(
                        filepath, _cache_jsonl_position, _cache_turns
                    )

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
                visible_lines, visible_keys, sticky_header, viewport_start = format_cache_tracker(
                    _cache_turns, cache_expand_states, pane_height, pane_width, cache_scroll_offset
                )
                result_lines = []
                if sticky_header is not None:
                    trunc = truncate_visible(sticky_header, pane_width)
                    result_lines.append(f"{ZEBRA_BG_A}{trunc}{RESET}")
                cache_line_map.clear()
                phys_row = 1 + (1 if sticky_header is not None else 0)
                for i, (line, key) in enumerate(zip(visible_lines, visible_keys)):
                    logical_idx = viewport_start + i
                    zebra_bg = ZEBRA_BG_B if logical_idx % 2 else ZEBRA_BG_A
                    is_hovered = (key is not None and cache_hover_row is not None
                                  and phys_row == cache_hover_row)
                    if is_hovered:
                        chosen_bg = HOVER_BG
                    elif line.startswith(LIGHT_RED_BG):
                        chosen_bg = LIGHT_RED_BG
                    else:
                        chosen_bg = zebra_bg
                    trunc = truncate_visible(line, pane_width)
                    result_lines.append(f"{chosen_bg}{trunc}{RESET}")
                    if key is not None:
                        cache_line_map[phys_row] = key
                    phys_row += 1
                output = '\n'.join(result_lines)
                if output != last_output:
                    print("\033[2J\033[3J\033[H", end='', flush=True)
                    if output:
                        print(output)
                    last_output = output
            time.sleep(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()
