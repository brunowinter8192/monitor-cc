# INFRASTRUCTURE
import hashlib
import os
import re
import subprocess
import sys
from typing import Optional

# From constants.py: Colors and config values
from .constants import TMUX_HISTORY_LIMIT

# Layout definition for self-healing pane recreation (mirrors launch_split_screen)
# Format: [(win_idx, win_name, [(mode, split_from_or_None, pct_or_None)])]
_WINDOW_LAYOUT = [
    (0, 'main',    [('main',            None,            None),
                    ('tokens',          'main',          '30%')]),
    (1, 'proxy',   [('proxy',           None,            None),
                    ('metadata',        'proxy',         '30%')]),
    (2, 'rules',   [('rules',           None,            None),
                    ('hooks',           'rules',         '50%')]),
    (3, 'workers', [('workers',         None,            None),
                    ('worker-proxy',    'workers',       '66%'),
                    ('worker-metadata', 'worker-proxy',  '50%')]),
    (4, 'debug',   [('warnings',        None,            None),
                    ('waste',           'warnings',      '50%')]),
]

# ORCHESTRATOR
def launch_split_screen(project_filter: Optional[str] = None, script_path: str = '') -> None:
    if not is_tmux_installed():
        print("Error: tmux is not installed. Install with: brew install tmux")
        sys.exit(1)

    if is_inside_tmux():
        print("Error: Already inside tmux session. Use --mode main")
        sys.exit(1)

    session_name = generate_session_name(project_filter)

    if check_session_exists(session_name):
        print(f"Warning: Session '{session_name}' already exists for this project.")
        print("This might be a stale session. Killing it and creating fresh one...")
        kill_session(session_name)

    project_arg = f"--project {project_filter}" if project_filter else ""

    main_cmd = f"python3 {script_path} --mode main {project_arg}"
    tokens_cmd = f"python3 {script_path} --mode tokens {project_arg}"
    proxy_cmd = f"python3 {script_path} --mode proxy {project_arg}"
    metadata_cmd = f"python3 {script_path} --mode metadata {project_arg}"
    rules_cmd = f"python3 {script_path} --mode rules {project_arg}"
    warnings_cmd = f"python3 {script_path} --mode warnings {project_arg}"
    hooks_cmd = f"python3 {script_path} --mode hooks {project_arg}"
    workers_cmd = f"python3 {script_path} --mode workers {project_arg}"
    worker_proxy_cmd = f"python3 {script_path} --mode worker-proxy {project_arg}"
    worker_metadata_cmd = f"python3 {script_path} --mode worker-metadata {project_arg}"
    # Propagate Monitor_CC root so waste_pane.py finds proxy logs regardless of cwd
    _monitor_root = os.environ.get('MONITOR_CC_ROOT', '') or os.path.dirname(os.path.abspath(script_path))
    waste_cmd = f"MONITOR_CC_ROOT={_monitor_root} python3 {script_path} --mode waste {project_arg}"

    original_history_limit = get_global_history_limit()
    subprocess.run(["tmux", "set-option", "-g", "history-limit", TMUX_HISTORY_LIMIT])

    # 5-Window Layout:
    # Window 0 "main":    Main (left, 70%) + Tokens (right, 30%)
    # Window 1 "proxy":   API Proxy log (fullscreen)
    # Window 2 "rules":   Rules (left, 50%) + Hooks (right, 50%)
    # Window 3 "workers": Workers (left, 50%) + Worker-Proxy (right-top, 50%) + Worker-Metadata (right-bottom, 50%)
    # Window 4 "debug":   Warnings (fullscreen)
    subprocess.run(["tmux", "new-session", "-d", "-s", session_name, main_cmd])
    subprocess.run(["tmux", "rename-window", "-t", f"{session_name}:0", "main"])
    subprocess.run(["tmux", "split-window", "-h", "-t", f"{session_name}:0.0", "-l", "30%", tokens_cmd])

    subprocess.run(["tmux", "new-window", "-t", f"{session_name}:1", "-n", "proxy", proxy_cmd])
    subprocess.run(["tmux", "split-window", "-h", "-t", f"{session_name}:1.0", "-l", "30%", metadata_cmd])

    subprocess.run(["tmux", "new-window", "-t", f"{session_name}:2", "-n", "rules", rules_cmd])
    subprocess.run(["tmux", "split-window", "-h", "-t", f"{session_name}:2.0", "-l", "50%", hooks_cmd])

    subprocess.run(["tmux", "new-window", "-t", f"{session_name}:3", "-n", "workers", workers_cmd])
    subprocess.run(["tmux", "split-window", "-h", "-t", f"{session_name}:3.0", "-l", "66%", worker_proxy_cmd])
    subprocess.run(["tmux", "split-window", "-h", "-t", f"{session_name}:3.1", "-l", "50%", worker_metadata_cmd])

    subprocess.run(["tmux", "new-window", "-t", f"{session_name}:4", "-n", "debug", warnings_cmd])
    subprocess.run(["tmux", "split-window", "-h", "-t", f"{session_name}:4.0", "-l", "50%", waste_cmd])

    subprocess.run(["tmux", "select-window", "-t", f"{session_name}:0"])

    restore_global_history_limit(original_history_limit)
    configure_tmux_session(session_name, script_path, project_arg)

    subprocess.run(["tmux", "attach-session", "-t", session_name])

# FUNCTIONS

# Check if tmux is installed
def is_tmux_installed() -> bool:
    result = subprocess.run(["which", "tmux"], capture_output=True)
    installed = result.returncode == 0
    return installed

# Check if already running inside tmux
def is_inside_tmux() -> bool:
    in_tmux = "TMUX" in os.environ
    return in_tmux

# Generate unique session name from project path
def generate_session_name(project_path: Optional[str] = None) -> str:
    if project_path is None:
        return "monitor_cc_global"
    normalized_path = os.path.normpath(os.path.expanduser(project_path))
    path_hash = hashlib.md5(normalized_path.encode()).hexdigest()[:8]
    session_name = f"monitor_cc_{path_hash}"
    return session_name

# Check if tmux session exists
def check_session_exists(session_name: str) -> bool:
    result = subprocess.run(["tmux", "has-session", "-t", session_name], capture_output=True)
    exists = result.returncode == 0
    return exists

# Kill tmux session
def kill_session(session_name: str) -> None:
    subprocess.run(["tmux", "kill-session", "-t", session_name], capture_output=True)

# Get current global history-limit setting
def get_global_history_limit() -> str:
    result = subprocess.run(["tmux", "show-options", "-gv", "history-limit"], capture_output=True, text=True)
    limit = result.stdout.strip() or "2000"
    return limit

# Restore global history-limit to original value
def restore_global_history_limit(original_value: str) -> None:
    subprocess.run(["tmux", "set-option", "-g", "history-limit", original_value])

# Configure tmux session appearance and behavior
def configure_tmux_session(session_name: str, script_path: str = '', project_arg: str = '') -> None:
    subprocess.run(["tmux", "set-option", "-t", session_name, "status", "on"])
    subprocess.run(["tmux", "set-option", "-t", session_name, "status-style", "bg=default"])
    subprocess.run(["tmux", "set-option", "-t", session_name, "status-left", "#{?pane_in_mode,#[fg=yellow bold] COPY #[default],#[fg=green] SCROLL #[default]}"])
    subprocess.run(["tmux", "set-option", "-t", session_name, "status-right", ""])
    subprocess.run(["tmux", "set-option", "-t", session_name, "status-left-length", "20"])
    subprocess.run(["tmux", "set-option", "-t", session_name, "window-status-format", "#[fg=colour240]#I:#W"])
    subprocess.run(["tmux", "set-option", "-t", session_name, "window-status-current-format", "#[fg=green,bold]#I:#W"])
    subprocess.run(["tmux", "bind-key", "-n", "C-q", "if-shell", "-F", "#{pane_in_mode}", "send-keys -X cancel", "copy-mode"])
    subprocess.run(["tmux", "set-option", "-t", session_name, "mouse", "on"])
    subprocess.run(["tmux", "bind-key", "-T", "copy-mode", "MouseDragEnd1Pane", "send-keys", "-X", "copy-pipe", "pbcopy"])
    subprocess.run(["tmux", "bind-key", "-T", "copy-mode-vi", "MouseDragEnd1Pane", "send-keys", "-X", "copy-pipe", "pbcopy"])
    subprocess.run(["tmux", "bind-key", "-T", "root", "WheelUpPane", "if-shell", "-F", "#{mouse_any_flag}", "send-keys -M", "copy-mode; send-keys -X -N 5 scroll-up"])
    subprocess.run(["tmux", "bind-key", "-T", "root", "WheelDownPane", "if-shell", "-F", "#{mouse_any_flag}", "send-keys -M", "copy-mode; send-keys -X -N 5 scroll-down"])
    pane_titles = {
        '0.0': 'MAIN', '0.1': 'TOKENS',
        '1.0': 'PROXY', '1.1': 'METADATA',
        '2.0': 'RULES', '2.1': 'HOOKS',
        '3.0': 'WORKERS', '3.1': 'WORKER-PROXY', '3.2': 'WORKER-METADATA',
        '4.0': 'WARNINGS', '4.1': 'WASTE',
    }
    for pane_ref, title in pane_titles.items():
        subprocess.run(["tmux", "select-pane", "-t", f"{session_name}:{pane_ref}", "-T", title])
    for win in range(5):
        subprocess.run(["tmux", "set-window-option", "-t", f"{session_name}:{win}", "pane-border-style", "fg=colour240"])
        subprocess.run(["tmux", "set-window-option", "-t", f"{session_name}:{win}", "pane-active-border-style", "fg=colour245"])
        subprocess.run(["tmux", "set-window-option", "-t", f"{session_name}:{win}", "wrap-search", "on"])
        subprocess.run(["tmux", "set-window-option", "-t", f"{session_name}:{win}", "pane-border-status", "top"])
        subprocess.run(["tmux", "set-window-option", "-t", f"{session_name}:{win}", "pane-border-format", "#[fg=colour216] ━━━ #{pane_title} ━━━"])
    subprocess.run(["tmux", "bind-key", "-T", "root", "M-m", "run-shell", f"tmux capture-pane -t {session_name}:0.0 -pS - | pbcopy && tmux display 'Main pane copied'"])
    subprocess.run(["tmux", "bind-key", "-T", "root", "M-t", "run-shell", f"tmux capture-pane -t {session_name}:0.1 -pS - | pbcopy && tmux display 'Tokens pane copied'"])
    subprocess.run(["tmux", "bind-key", "-T", "root", "M-p", "run-shell", f"tmux capture-pane -t {session_name}:1.0 -pS - | pbcopy && tmux display 'Proxy pane copied'"])
    subprocess.run(["tmux", "bind-key", "-T", "root", "M-r", "run-shell", f"tmux capture-pane -t {session_name}:2.0 -pS - | pbcopy && tmux display 'Rules pane copied'"])
    subprocess.run(["tmux", "bind-key", "-T", "root", "M-h", "run-shell", f"tmux capture-pane -t {session_name}:2.1 -pS - | pbcopy && tmux display 'Hooks pane copied'"])
    subprocess.run(["tmux", "bind-key", "-T", "root", "M-k", "run-shell", f"tmux capture-pane -t {session_name}:3.0 -pS - | pbcopy && tmux display 'Workers pane copied'"])
    subprocess.run(["tmux", "bind-key", "-T", "root", "M-w", "run-shell", f"tmux capture-pane -t {session_name}:4.0 -pS - | pbcopy && tmux display 'Warnings pane copied'"])
    subprocess.run(["tmux", "bind-key", "-T", "root", "C-f", "copy-mode", "\\;", "command-prompt", "-p", "(search):", "send-keys -X search-forward '%%'"])
    subprocess.run(["tmux", "bind-key", "-T", "copy-mode", "C-f", "command-prompt", "-p", "(search):", "send-keys -X search-forward '%%'"])
    subprocess.run(["tmux", "bind-key", "-T", "copy-mode-vi", "C-f", "command-prompt", "-p", "(search):", "send-keys -X search-forward '%%'"])
    subprocess.run(["tmux", "bind-key", "-T", "copy-mode", "Enter", "send-keys", "-X", "search-again"])
    subprocess.run(["tmux", "bind-key", "-T", "copy-mode-vi", "Enter", "send-keys", "-X", "search-again"])
    for digit in "123456789":
        subprocess.run(["tmux", "bind-key", "-T", "copy-mode", digit, "send-keys", "-X", "cancel", "\\;", "send-keys", digit])
        subprocess.run(["tmux", "bind-key", "-T", "copy-mode-vi", digit, "send-keys", "-X", "cancel", "\\;", "send-keys", digit])
    restart_cmd = f"python3 {script_path} --mode restart-panes --session '#{{session_name}}' {project_arg}"
    subprocess.run(["tmux", "bind-key", "-T", "root", "C-r", "run-shell", restart_cmd])

# Build mode -> shell command mapping (mirrors launch_split_screen construction exactly)
def _build_mode_commands(script_path: str, project_path: Optional[str]) -> dict:
    project_arg = f"--project {project_path}" if project_path else ""
    _monitor_root = os.environ.get('MONITOR_CC_ROOT', '') or os.path.dirname(os.path.abspath(script_path))
    cmds = {
        mode: f"python3 {script_path} --mode {mode} {project_arg}"
        for mode in ('main', 'tokens', 'proxy', 'metadata', 'rules', 'hooks',
                     'workers', 'worker-proxy', 'worker-metadata', 'warnings')
    }
    cmds['waste'] = f"MONITOR_CC_ROOT={_monitor_root} python3 {script_path} --mode waste {project_arg}"
    return cmds

# Parse 'list-panes -F #{pane_index}|#{pane_start_command}' output; return {mode: pane_idx_str}
def _parse_pane_modes(list_panes_output: str) -> dict:
    present = {}
    for line in list_panes_output.strip().split('\n'):
        if '|' not in line:
            continue
        idx, cmd = line.split('|', 1)
        m = re.search(r'--mode\s+(\S+)', cmd)
        if m:
            present[m.group(1)] = idx.strip()
    return present

# Return first available pane index from list-panes output, or None
def _first_pane_idx(list_panes_output: str) -> Optional[str]:
    for line in list_panes_output.strip().split('\n'):
        if '|' in line:
            idx = line.split('|', 1)[0].strip()
            if idx.isdigit():
                return idx
    return None

# Self-healing Ctrl+R: recreates missing panes then respawns all surviving panes
def restart_panes(session_name: str, project_path: Optional[str] = None, script_path: str = '') -> None:
    """Recreate any missing panes from _WINDOW_LAYOUT, then respawn all panes.

    Known limitation: when multiple panes in a window are missing simultaneously,
    the split percentage is applied against whichever pane survives (not the original
    source), so visual proportions may differ from the initial launch. Single-missing-
    pane case always restores the correct size.
    """
    mode_cmds = _build_mode_commands(script_path, project_path)

    # Get existing window indices
    win_result = subprocess.run(
        ["tmux", "list-windows", "-t", session_name, "-F", "#{window_index}"],
        capture_output=True, text=True
    )
    existing_windows = {int(x) for x in win_result.stdout.strip().split('\n') if x.strip().isdigit()}

    for win_idx, win_name, pane_specs in _WINDOW_LAYOUT:
        if win_idx not in existing_windows:
            # Entire window is missing — recreate from scratch
            first_mode = pane_specs[0][0]
            subprocess.run([
                "tmux", "new-window", "-t", f"{session_name}:{win_idx}",
                "-n", win_name, mode_cmds[first_mode]
            ])
            for mode, split_from, pct in pane_specs[1:]:
                raw = subprocess.run(
                    ["tmux", "list-panes", "-t", f"{session_name}:{win_idx}",
                     "-F", "#{pane_index}|#{pane_start_command}"],
                    capture_output=True, text=True
                ).stdout
                present = _parse_pane_modes(raw)
                src = present.get(split_from) if split_from else _first_pane_idx(raw)
                if src is not None:
                    subprocess.run([
                        "tmux", "split-window", "-h",
                        "-t", f"{session_name}:{win_idx}.{src}",
                        "-l", pct, mode_cmds[mode]
                    ])
        else:
            # Window exists — recreate only the missing panes
            raw = subprocess.run(
                ["tmux", "list-panes", "-t", f"{session_name}:{win_idx}",
                 "-F", "#{pane_index}|#{pane_start_command}"],
                capture_output=True, text=True
            ).stdout
            present = _parse_pane_modes(raw)

            for mode, split_from, pct in pane_specs:
                if mode in present:
                    continue
                # Prefer natural split-source; fall back to any surviving pane
                src = present.get(split_from) if (split_from and split_from in present) else _first_pane_idx(raw)
                if src is None:
                    continue
                subprocess.run([
                    "tmux", "split-window", "-h",
                    "-t", f"{session_name}:{win_idx}.{src}",
                    "-l", pct or "50%", mode_cmds[mode]
                ])
                # Refresh pane list so subsequent iterations see the new pane
                raw = subprocess.run(
                    ["tmux", "list-panes", "-t", f"{session_name}:{win_idx}",
                     "-F", "#{pane_index}|#{pane_start_command}"],
                    capture_output=True, text=True
                ).stdout
                present = _parse_pane_modes(raw)

    # Respawn every pane to pick up latest code changes
    for win_idx, _, _ in _WINDOW_LAYOUT:
        pane_raw = subprocess.run(
            ["tmux", "list-panes", "-t", f"{session_name}:{win_idx}", "-F", "#{pane_index}"],
            capture_output=True, text=True
        ).stdout
        for line in pane_raw.strip().split('\n'):
            if line.strip().isdigit():
                subprocess.run(["tmux", "respawn-pane", "-k",
                                 "-t", f"{session_name}:{win_idx}.{line.strip()}"])

    subprocess.run(["tmux", "display-message", "-t", session_name, "Monitor restarted"])
