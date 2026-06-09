# INFRASTRUCTURE
import os
import re
import subprocess
import time

from ..constants import (
    RESET, GREEN, YELLOW, RED, DIM, ORANGE,
    INPUT_POLL_INTERVAL,
)
from ..utils import format_timestamp
from ..input.click_handler import (
    setup_keyboard_input, restore_terminal, read_keypress, wait_for_input,
    enable_mouse, disable_mouse, read_mouse_event,
)
from .status import all_statuses, get_anomalies, PRESET_NAMES, _fetch_collections
from .errors import errors_today, errors_today_by_server

GPU_POLL_INTERVAL         = 2.0   # seconds between server data refreshes
COLLECTIONS_POLL_INTERVAL = 30.0  # seconds between RAG collection count refreshes
TOGGLE_TIMEOUT            = 120   # seconds before [starting…]/[stopping…] label expires
IDLE_TIMEOUT              = int(os.getenv("RAG_SERVER_IDLE_TIMEOUT", "3600"))
_ANSI_RE          = re.compile(r'\x1b\[[0-9;]*[mKHJABCDEFGsuTXP]')

_toggle_state: dict = {}   # preset name or 'port-{N}' → ('starting'|'stopping', float ts)
_button_regions: dict = {} # (start_col, end_col, phys_row) → (action, target_str)

# ORCHESTRATOR

# GPU pane event loop — 2s tick, keyboard toggle 1/2/3, r=refresh
def run_gpu_loop() -> None:
    last_output = None
    last_data_refresh = 0.0
    last_collections_refresh = 0.0
    force_refresh = False
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
            input_changed = False

            while True:
                char = read_keypress()
                if char is None:
                    break
                if char.isdigit() and char != '0':
                    idx = int(char) - 1
                    if idx < len(PRESET_NAMES):
                        name = PRESET_NAMES[idx]
                        if name not in _toggle_state:
                            _toggle_server(idx, presets)
                            input_changed = True
                elif char in ('r', 'R'):
                    force_refresh = True
                    input_changed = True
                elif char == '\033':
                    event = read_mouse_event(char)
                    if event is not None:
                        button, col, row = event
                        if button == 0:
                            for (sc, ec, er), (action, target) in list(_button_regions.items()):
                                if row == er and sc <= col <= ec:
                                    if target not in _toggle_state:
                                        _fire_button(action, target)
                                        input_changed = True
                                    break

            now = time.time()
            if force_refresh or now - last_data_refresh >= GPU_POLL_INTERVAL:
                presets, arbitrary = all_statuses()
                anomalies = get_anomalies()
                today_errors = errors_today()
                error_counts = errors_today_by_server()
                last_data_refresh = now
                input_changed = True
                _expire_toggle_states(presets, arbitrary)

            if force_refresh or now - last_collections_refresh >= COLLECTIONS_POLL_INTERVAL:
                collections = _fetch_collections()
                last_collections_refresh = now
                input_changed = True

            force_refresh = False

            if input_changed:
                try:
                    term = os.get_terminal_size()
                    pane_width = term.columns
                    pane_height = term.lines - 1
                except OSError:
                    pane_width = 100
                    pane_height = 30
                output = _render_pane(pane_width, pane_height,
                                      presets, arbitrary, anomalies,
                                      today_errors, error_counts, collections)
                if output != last_output:
                    print("\033[2J\033[3J\033[H", end='', flush=True)
                    print(output, end='', flush=True)
                    last_output = output

            wait_for_input(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()

# FUNCTIONS

# Toggle preset server by 0-based index; context-dependent stop/restart/start
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


# Remove _toggle_state entries when action completed or timed out
def _expire_toggle_states(presets: list, arbitrary: list) -> None:
    now = time.time()
    for key in list(_toggle_state.keys()):
        action, ts = _toggle_state[key]
        if now - ts > TOGGLE_TIMEOUT:
            del _toggle_state[key]
            continue
        if key.startswith('port-'):
            try:
                port_n = int(key[5:])
            except ValueError:
                continue
            s = next((x for x in arbitrary if x['port'] == port_n), None)
        else:
            s = next((x for x in presets if x['name'] == key), None)
        if s is None:
            continue
        if action == 'starting' and s['running'] and s['healthy']:
            del _toggle_state[key]
        elif action == 'stopping' and not s['running']:
            del _toggle_state[key]


# Return colored status badge
def _badge(s: dict) -> str:
    if not s['running']:
        return f"{RED}○{RESET}"
    return f"{GREEN}●{RESET}" if s['healthy'] else f"{YELLOW}◐{RESET}"


# Return status label; shows [starting…]/[stopping…] while toggle in flight
def _status_text(s: dict) -> str:
    key = s['name'] if s['kind'] == 'preset' else f'port-{s["port"]}'
    if key in _toggle_state:
        action, _ = _toggle_state[key]
        return f"[{action}\u2026]"
    return "running" if s['running'] else "stopped"


# Remove ANSI escape codes to calculate visual display width
def _strip_ansi(s: str) -> str:
    return _ANSI_RE.sub('', s)


# Return countdown string from status dict; "" if stopped, "?" if state file missing
def _format_countdown(s: dict) -> str:
    if not s['running']:
        return ""
    if s.get('idle_state_missing'):
        return "?"
    idle_seconds = s.get('idle_seconds')
    if idle_seconds is None:
        return ""
    remaining = int(IDLE_TIMEOUT - idle_seconds)
    if remaining <= 0:
        return "stopping\u2026"
    if remaining >= 3600:
        h = remaining // 3600
        m = (remaining % 3600) // 60
        sec = remaining % 60
        return f"stops in {h}:{m:02d}:{sec:02d}"
    m = remaining // 60
    sec = remaining % 60
    return f"stops in {m:02d}:{sec:02d}"


# Return context-dependent button label; arbitrary rows always [stop]
def _button_label(s: dict) -> str:
    if s['kind'] == 'arbitrary':
        return '[stop]'
    if not s['running']:
        return '[start]'
    return '[stop]' if s['healthy'] else '[restart]'


# Fire-and-forget action via rag-cli; target is preset name or 'port-{N}' for arbitrary
def _fire_button(action: str, target: str) -> None:
    devnull = subprocess.DEVNULL
    if target.startswith('port-'):
        port = target[5:]
        subprocess.Popen(["rag-cli", "server", "stop", "--port", port],
                         stdout=devnull, stderr=devnull)
    else:
        subprocess.Popen(["rag-cli", "server", action, target],
                         stdout=devnull, stderr=devnull)
    _toggle_state[target] = ('starting' if action in ('start', 'restart') else 'stopping',
                              time.time())


# Build full pane content; updates _button_regions as side effect
def _render_pane(pane_width: int, pane_height: int,
                 presets: list, arbitrary: list, anomalies: list,
                 today_errors: list, error_counts: dict,
                 collections: list) -> str:
    _button_regions.clear()
    lines: list[str] = []

    lines.append(f"{DIM}{'═' * min(pane_width, 64)}{RESET}  GPU Servers")

    # Preset block — always 3 rows, digit-keyed [1]/[2]/[3]
    for i, s in enumerate(presets):
        badge      = _badge(s)
        status_txt = _status_text(s)
        countdown  = _format_countdown(s)
        port_str   = f"port {s['port']}"         if s['port']               else ""
        pid_str    = f"pid {s['pid']}"           if s['pid']                else ""
        rss_str    = f"RSS {s['rss_mb']} MB"     if s['rss_mb'] is not None else ""
        model_str  = (s.get('model_name') or '')[:20]
        err_n      = error_counts.get(s['name'], 0)
        err_col    = GREEN if err_n == 0 else ORANGE
        err_str    = f"errors today: {err_col}{err_n}{RESET}"
        btn        = _button_label(s)
        action     = ('stop' if s['healthy'] else 'restart') if s['running'] else 'start'
        content    = (f"[{i+1}] {s['name']:<16} {badge} {status_txt:<15} "
                      f"{countdown:<16} {port_str:<14} {pid_str:<13} "
                      f"{rss_str:<14} {model_str:<20} {err_str}")
        vis_len    = len(_strip_ansi(content))
        pad        = max(1, pane_width - vis_len - len(btn))
        phys_row   = len(lines) + 1
        _button_regions[(vis_len + pad + 1, vis_len + pad + len(btn), phys_row)] = (action, s['name'])
        lines.append(content + ' ' * pad + btn)

    # Arbitrary block — dynamic, sorted by port, no digit keys
    if arbitrary:
        lines.append("")
        lines.append(f"{DIM}{'─' * min(pane_width, 40)}  arbitrary{RESET}")
        for s in arbitrary:
            badge      = _badge(s)
            status_txt = _status_text(s)
            countdown  = _format_countdown(s)
            port_str   = f"port {s['port']}"         if s['port']               else ""
            pid_str    = f"pid {s['pid']}"           if s['pid']                else ""
            rss_str    = f"RSS {s['rss_mb']} MB"     if s['rss_mb'] is not None else ""
            model_str  = (s.get('model_name') or '')[:20]
            err_n      = error_counts.get(s['name'], 0)
            err_col    = GREEN if err_n == 0 else ORANGE
            err_str    = f"errors today: {err_col}{err_n}{RESET}"
            btn        = '[stop]'
            target     = f'port-{s["port"]}'
            content    = (f"    {s['name']:<12} {badge} {status_txt:<15} "
                          f"{countdown:<16} {port_str:<14} {pid_str:<13} "
                          f"{rss_str:<14} {model_str:<20} {err_str}")
            vis_len    = len(_strip_ansi(content))
            pad        = max(1, pane_width - vis_len - len(btn))
            phys_row   = len(lines) + 1
            _button_regions[(vis_len + pad + 1, vis_len + pad + len(btn), phys_row)] = ('stop', target)
            lines.append(content + ' ' * pad + btn)

    lines.append("")
    lines.append(f"{DIM}{'═' * min(pane_width, 64)}{RESET}  RAG Collections")
    if collections:
        for c in collections:
            lines.append(f"  {c['collection']:<32} {c['chunks']} chunks")
    else:
        lines.append(f"  {DIM}(none indexed){RESET}")

    lines.append("")
    lines.append(f"{DIM}{'═' * min(pane_width, 64)}{RESET}  Errors today (last 10)")

    recent = list(reversed(today_errors))[:10]
    if recent:
        for e in recent:
            ts_str  = format_timestamp(e.get("ts", ""))
            server  = e.get("server", "?")
            code    = e.get("code", "?")
            msg     = e.get("msg", "")
            prefix_plain = f"{ts_str}  {server:<12} {code:<14} "
            max_msg = max(0, pane_width - len(prefix_plain) - 1)
            if len(msg) > max_msg:
                msg = msg[:max_msg] + "\u2026"
            lines.append(f"{ts_str}  {server:<12} {ORANGE}{code:<14}{RESET} {msg}")
    else:
        lines.append(f"  {DIM}(no errors today){RESET}")

    if anomalies:
        n = len(anomalies)
        lines.append(
            f"  {YELLOW}\u26a0 {n} anomal{'y' if n == 1 else 'ies'} "
            f"(see logs/gpu_pane.log){RESET}"
        )

    return "\n".join(lines)
