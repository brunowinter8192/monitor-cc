# INFRASTRUCTURE
import os
import pathlib
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
from .status import all_statuses, SERVERS
from .errors import errors_today, errors_today_by_server

GPU_POLL_INTERVAL = 2.0      # seconds between data refreshes
TOGGLE_TIMEOUT    = 120      # seconds before [starting…]/[stopping…] label expires
IDLE_TIMEOUT      = int(os.getenv("RAG_SERVER_IDLE_TIMEOUT", "3600"))
LOCK_DIR          = pathlib.Path.home() / ".rag-locks"
_ANSI_RE          = re.compile(r'\x1b\[[0-9;]*[mKHJABCDEFGsuTXP]')

_toggle_state: dict = {}     # name → ('starting'|'stopping', float timestamp)
_button_regions: dict = {}   # (start_col, end_col, phys_row) → (action, server_name)

# ORCHESTRATOR

# GPU pane event loop — 2s tick, keyboard toggle 1/2/3, r=refresh
def run_gpu_loop() -> None:
    last_output = None
    last_data_refresh = 0.0
    force_refresh = False
    statuses: list = []
    today_errors: list = []
    error_counts: dict = {}

    setup_keyboard_input()
    enable_mouse()
    try:
        while True:
            input_changed = False

            while True:
                char = read_keypress()
                if char is None:
                    break
                if char in ('1', '2', '3'):
                    idx = int(char) - 1
                    if 0 <= idx < len(SERVERS):
                        _toggle_server(SERVERS[idx], statuses)
                        input_changed = True
                elif char in ('r', 'R'):
                    force_refresh = True
                    input_changed = True
                elif char == '\033':
                    event = read_mouse_event(char)
                    if event is not None:
                        button, col, row = event
                        if button == 0:
                            for (sc, ec, er), (action, server) in list(_button_regions.items()):
                                if row == er and sc <= col <= ec:
                                    if server not in _toggle_state:
                                        _fire_button(action, server)
                                        input_changed = True
                                    break

            now = time.time()
            if force_refresh or now - last_data_refresh >= GPU_POLL_INTERVAL:
                force_refresh = False
                statuses = all_statuses()
                today_errors = errors_today()
                error_counts = errors_today_by_server()
                last_data_refresh = now
                input_changed = True
                _expire_toggle_states(statuses)

            if input_changed:
                try:
                    term = os.get_terminal_size()
                    pane_width = term.columns
                    pane_height = term.lines - 1
                except OSError:
                    pane_width = 100
                    pane_height = 30
                output = _render_pane(pane_width, pane_height, statuses, today_errors, error_counts)
                if output != last_output:
                    print("\033[2J\033[3J\033[H", end='', flush=True)
                    print(output, end='', flush=True)
                    last_output = output

            wait_for_input(INPUT_POLL_INTERVAL)
    finally:
        disable_mouse()
        restore_terminal()

# FUNCTIONS

# Fire-and-forget toggle: stop if running, start if stopped
def _toggle_server(name: str, statuses: list) -> None:
    current = next((s for s in statuses if s['name'] == name), None)
    if current is None:
        return
    devnull = subprocess.DEVNULL
    if current['status'] == 'running':
        subprocess.Popen(["rag-cli", "server", "stop", name],
                         stdout=devnull, stderr=devnull)
        _toggle_state[name] = ('stopping', time.time())
    else:
        subprocess.Popen(["rag-cli", "server", "start", name],
                         stdout=devnull, stderr=devnull)
        _toggle_state[name] = ('starting', time.time())


# Remove entries from _toggle_state when action completed or timed out
def _expire_toggle_states(statuses: list) -> None:
    now = time.time()
    for name in list(_toggle_state.keys()):
        action, ts = _toggle_state[name]
        if now - ts > TOGGLE_TIMEOUT:
            del _toggle_state[name]
            continue
        s = next((x for x in statuses if x['name'] == name), None)
        if s is None:
            continue
        if action == 'starting' and s['status'] == 'running' and s['healthy']:
            del _toggle_state[name]
        elif action == 'stopping' and s['status'] == 'stopped':
            del _toggle_state[name]


# Return colored status badge for a server dict
def _badge(s: dict) -> str:
    if s['status'] != 'running':
        return f"{RED}○{RESET}"
    return f"{GREEN}●{RESET}" if s['healthy'] else f"{YELLOW}◐{RESET}"


# Return status label; shows [starting…]/[stopping…] while toggle in flight
def _status_text(s: dict) -> str:
    name = s['name']
    if name in _toggle_state:
        action, _ = _toggle_state[name]
        return f"[{action}\u2026]"
    return "running" if s['status'] == 'running' else "stopped"


# Remove ANSI escape codes to calculate visual display width
def _strip_ansi(s: str) -> str:
    return _ANSI_RE.sub('', s)


# Read last-used timestamp from LOCK_DIR; return 0.0 if missing or unreadable
def _read_last_used(name: str) -> float:
    ts_file = LOCK_DIR / f"rag-server-{name}-last-used"
    try:
        return float(ts_file.read_text().strip())
    except (FileNotFoundError, ValueError, OSError):
        return 0.0


# Return countdown string "stops in MM:SS" / "stops in H:MM:SS" / "stopping…" / ""
def _format_countdown(name: str, status: str) -> str:
    if status != 'running':
        return ""
    last_used = _read_last_used(name)
    if last_used == 0.0:
        return ""
    remaining = IDLE_TIMEOUT - (time.time() - last_used)
    if remaining <= 0:
        return "stopping…"
    remaining = int(remaining)
    if remaining >= 3600:
        h = remaining // 3600
        m = (remaining % 3600) // 60
        s = remaining % 60
        return f"stops in {h}:{m:02d}:{s:02d}"
    m = remaining // 60
    s = remaining % 60
    return f"stops in {m:02d}:{s:02d}"


# Return context-dependent button label for a server row
def _button_label(s: dict) -> str:
    if s['status'] != 'running':
        return '[start]'
    return '[stop]' if s['healthy'] else '[restart]'


# Fire-and-forget action via rag-cli; record in _toggle_state
def _fire_button(action: str, server: str) -> None:
    devnull = subprocess.DEVNULL
    subprocess.Popen(["rag-cli", "server", action, server],
                     stdout=devnull, stderr=devnull)
    _toggle_state[server] = ('starting' if action in ('start', 'restart') else 'stopping',
                             time.time())


# Build full pane content string; updates _button_regions as side effect
def _render_pane(pane_width: int, pane_height: int,
                 statuses: list, today_errors: list, error_counts: dict) -> str:
    _button_regions.clear()
    lines = []

    lines.append(f"{DIM}{'═' * min(pane_width, 64)}{RESET}  GPU Servers")

    for i, s in enumerate(statuses):
        badge      = _badge(s)
        status_txt = _status_text(s)
        err_n      = error_counts.get(s['name'], 0)
        port_str   = f"port {s['port']}"  if s['port']   else "          "
        pid_str    = f"pid {s['pid']}"    if s['pid']    else "         "
        rss_str    = f"RSS {s['rss_mb']} MB" if s['rss_mb'] is not None else "          "
        err_col    = GREEN if err_n == 0 else ORANGE
        err_str    = f"errors today: {err_col}{err_n}{RESET}"
        countdown  = _format_countdown(s['name'], s['status'])
        btn        = _button_label(s)
        action     = ('stop' if s['healthy'] else 'restart') if s['status'] == 'running' else 'start'
        content    = (f"[{i+1}] {s['name']:<12} {badge} {status_txt:<15} "
                      f"{countdown:<12} {port_str:<14} {pid_str:<13} {rss_str:<14} {err_str}")
        vis_len    = len(_strip_ansi(content))
        pad        = max(1, pane_width - vis_len - len(btn))
        btn_start  = vis_len + pad + 1   # 1-indexed SGR column
        phys_row   = i + 2              # row 1 = header, row 2+ = servers (1-indexed)
        _button_regions[(btn_start, btn_start + len(btn) - 1, phys_row)] = (action, s['name'])
        lines.append(content + ' ' * pad + btn)

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

    lines.append("")
    lines.append(
        f"{DIM}[1/2/3] toggle  [r] refresh  click [start]/[stop]/[restart]  "
        f"{GREEN}●{RESET}{DIM}=healthy {YELLOW}◐{RESET}{DIM}=unhealthy {RED}○{RESET}{DIM}=stopped{RESET}"
    )

    return "\n".join(lines)
