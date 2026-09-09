# INFRASTRUCTURE
import os
import subprocess
import time

from ..constants import INPUT_POLL_INTERVAL
from ..input.click_handler import (
    setup_keyboard_input, restore_terminal, read_keypress, wait_for_input,
    enable_mouse, disable_mouse, read_mouse_event, copy_to_clipboard,
)
from .status import all_statuses, get_anomalies, PRESET_NAMES, _fetch_collections
from .errors import errors_today, errors_today_by_server
from .gpu_actions import _toggle_state, _expire_toggle_states, _fire_button
from .gpu_render import _button_regions, _render_pane, _strip_ansi
from ..pane_error_log import log_pane_error
from .. import search_bar

GPU_POLL_INTERVAL         = 2.0
COLLECTIONS_POLL_INTERVAL = 30.0

_GPU_SEARCH_BAR_LINES = 1
_GPU_SEARCH_BAR_LABEL = 'search: '

_gpu_search: search_bar.SearchState = search_bar.SearchState()

# ORCHESTRATOR

def run_gpu_loop() -> None:
    last_output = None
    last_data_refresh = 0.0
    last_collections_refresh = 0.0
    presets: list = []
    arbitrary: list = []
    anomalies: list = []
    today_errors: list = []
    error_counts: dict = {}
    collections: list = []

    setup_keyboard_input()
    enable_mouse()
    try:
        while True:
            try:
                input_changed, force_refresh = _poll_gpu_input(
                    presets, arbitrary, anomalies, today_errors, error_counts, collections)

                now = time.time()
                (presets, arbitrary, anomalies, today_errors, error_counts, collections,
                 last_data_refresh, last_collections_refresh, refreshed) = _refresh_gpu_data(
                    now, force_refresh, last_data_refresh, last_collections_refresh,
                    presets, arbitrary, anomalies, today_errors, error_counts, collections)
                input_changed = input_changed or refreshed

                if input_changed:
                    last_output = _build_gpu_output(
                        presets, arbitrary, anomalies, today_errors, error_counts, collections,
                        last_output)

                wait_for_input(INPUT_POLL_INTERVAL)
            except Exception:
                log_pane_error('gpu')
                wait_for_input(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()

# FUNCTIONS

def _toggle_server(idx: int, presets: list) -> None:
    name = PRESET_NAMES[idx]
    s = next((p for p in presets if p['name'] == name), None)
    if s is None:
        return
    devnull = subprocess.DEVNULL
    if s['running'] and s['healthy']:
        subprocess.Popen(["rag-cli", "server", "stop", name],
                         stdout=devnull, stderr=devnull)
        _toggle_state[name] = ('stopping', time.time())
    elif s['running']:
        subprocess.Popen(["rag-cli", "server", "restart", name],
                         stdout=devnull, stderr=devnull)
        _toggle_state[name] = ('starting', time.time())
    else:
        subprocess.Popen(["rag-cli", "server", "start", name],
                         stdout=devnull, stderr=devnull)
        _toggle_state[name] = ('starting', time.time())


def _poll_gpu_input(presets: list, arbitrary: list, anomalies: list, today_errors: list,
                     error_counts: dict, collections: list) -> tuple:
    input_changed = False
    force_refresh = False
    while True:
        char = read_keypress()
        if char is None:
            break
        if char == '\033':
            event = read_mouse_event(char)
            if event is not None and event[0] != -1:
                button, col, row = event
                changed, refresh_hit = _handle_gpu_mouse(button, col, row)
                if changed:
                    input_changed = True
                if refresh_hit:
                    force_refresh = True
            elif event is not None:
                if search_bar.handle_search_mouse_release(_gpu_search, copy_to_clipboard):
                    input_changed = True
            elif _gpu_search.focused:
                if search_bar.handle_search_cancel(_gpu_search):
                    input_changed = True
        elif _gpu_search.focused:
            on_commit = lambda state: _gpu_search_on_commit(
                state, presets, arbitrary, anomalies, today_errors, error_counts, collections)
            if search_bar.handle_search_input(_gpu_search, char, on_commit=on_commit):
                input_changed = True
        elif char == '/':
            _gpu_search.focused = True
            input_changed = True
        elif char in ('n', 'N'):
            if _jump_gpu_search_match(forward=(char == 'n')):
                input_changed = True
        elif char.isdigit() and char != '0':
            idx = int(char) - 1
            if idx < len(PRESET_NAMES):
                name = PRESET_NAMES[idx]
                if name not in _toggle_state:
                    _toggle_server(idx, presets)
                    input_changed = True
        elif char in ('r', 'R'):
            force_refresh = True
            input_changed = True
    return input_changed, force_refresh


def _handle_gpu_mouse(button: int, col: int, row: int) -> tuple:
    if button == 0:
        if row == 1:
            return search_bar.handle_search_mouse_press(_gpu_search, col, _GPU_SEARCH_BAR_LABEL), False
        had_selection = _gpu_search.sel_anchor is not None
        search_bar.clear_selection(_gpu_search)
        for (sc, ec, er), (action, target) in list(_button_regions.items()):
            if row == er and sc <= col <= ec:
                if action == 'refresh':
                    return True, True
                if target not in _toggle_state:
                    _fire_button(action, target)
                    return True, False
                break
        return had_selection, False
    if button == 32 and _gpu_search.dragging:
        return search_bar.handle_search_mouse_motion(_gpu_search, col, _GPU_SEARCH_BAR_LABEL), False
    return False, False


def _gpu_search_on_commit(state: search_bar.SearchState, presets: list, arbitrary: list,
                           anomalies: list, today_errors: list, error_counts: dict,
                           collections: list) -> None:
    if not state.query:
        state.matches = []
        state.match_set = set()
        return
    try:
        pane_width = os.get_terminal_size().columns
    except OSError:
        pane_width = 100
    plain = _render_pane(pane_width, 0, presets, arbitrary, anomalies, today_errors, error_counts, collections)
    q = state.query.lower()
    matches = [i for i, line in enumerate(plain.split('\n')) if q in _strip_ansi(line).lower()]
    state.matches = matches
    state.match_set = set(matches)
    state.current_idx = 0

def _jump_gpu_search_match(forward: bool) -> bool:
    if not _gpu_search.matches:
        return False
    _gpu_search.current_idx = (_gpu_search.current_idx + (1 if forward else -1)) % len(_gpu_search.matches)
    return True

def _render_gpu_search_bar(pane_width: int) -> str:
    return search_bar.render_search_bar(_gpu_search, pane_width, label=_GPU_SEARCH_BAR_LABEL)


def _refresh_gpu_data(now: float, force_refresh: bool, last_data_refresh: float,
                       last_collections_refresh: float, presets: list, arbitrary: list,
                       anomalies: list, today_errors: list, error_counts: dict,
                       collections: list) -> tuple:
    changed = False
    if force_refresh or now - last_data_refresh >= GPU_POLL_INTERVAL:
        presets, arbitrary = all_statuses()
        anomalies = get_anomalies()
        today_errors = errors_today()
        error_counts = errors_today_by_server()
        last_data_refresh = now
        changed = True
        _expire_toggle_states(presets, arbitrary)
    if force_refresh or now - last_collections_refresh >= COLLECTIONS_POLL_INTERVAL:
        collections = _fetch_collections()
        last_collections_refresh = now
        changed = True
    return (presets, arbitrary, anomalies, today_errors, error_counts, collections,
            last_data_refresh, last_collections_refresh, changed)


def _build_gpu_output(presets: list, arbitrary: list, anomalies: list, today_errors: list,
                       error_counts: dict, collections: list, last_output) -> str:
    try:
        term = os.get_terminal_size()
        pane_width = term.columns
        pane_height = term.lines - 1
    except OSError:
        pane_width = 100
        pane_height = 30
    current_match_line = (
        _gpu_search.matches[_gpu_search.current_idx]
        if _gpu_search.matches and _gpu_search.current_idx < len(_gpu_search.matches)
        else None
    )
    body = _render_pane(pane_width, pane_height,
                        presets, arbitrary, anomalies,
                        today_errors, error_counts, collections,
                        search_query=_gpu_search.query,
                        search_match_line_set=_gpu_search.match_set,
                        search_current_line=current_match_line)
    shifted = {(sc, ec, er + _GPU_SEARCH_BAR_LINES): v for (sc, ec, er), v in _button_regions.items()}
    _button_regions.clear()
    _button_regions.update(shifted)
    output = _render_gpu_search_bar(pane_width) + '\n' + body
    if output != last_output:
        print("\033[2J\033[3J\033[H", end='', flush=True)
        print(output, end='', flush=True)
        return output
    return last_output
