# INFRASTRUCTURE
import hashlib
import os
import subprocess
import sys
from typing import Optional

# From constants.py: Colors and config values
from .constants import GREEN, YELLOW, BLUE, CYAN, TMUX_HISTORY_LIMIT

# ORCHESTRATOR
def launch_split_screen(project_filter: Optional[str] = None, ui: bool = False, script_path: str = '') -> None:
    if not is_tmux_installed():
        print("Error: tmux is not installed. Install with: brew install tmux")
        sys.exit(1)

    if is_inside_tmux():
        print("Error: Already inside tmux session. Use --mode main or --mode subagent")
        sys.exit(1)

    session_name = generate_session_name(project_filter)

    if check_session_exists(session_name):
        print(f"Warning: Session '{session_name}' already exists for this project.")
        print("This might be a stale session. Killing it and creating fresh one...")
        kill_session(session_name)

    project_arg = f"--project {project_filter}" if project_filter else ""
    ui_flag = "--ui" if ui else ""

    main_cmd = f"python3 {script_path} --mode main {project_arg}"
    tokens_cmd = f"python3 {script_path} --mode tokens {project_arg}"
    subagent_cmd = f"python3 {script_path} --mode subagent {project_arg} {ui_flag}"
    rules_cmd = f"python3 {script_path} --mode rules {project_arg}"
    warnings_cmd = f"python3 {script_path} --mode warnings {project_arg}"
    hooks_cmd = f"python3 {script_path} --mode hooks {project_arg}"
    workers_cmd = f"python3 {script_path} --mode workers {project_arg}"

    original_history_limit = get_global_history_limit()
    subprocess.run(["tmux", "set-option", "-g", "history-limit", TMUX_HISTORY_LIMIT])

    # 4-Window Layout:
    # Window 0 "main":    Main (left, 70%) + Tokens (right, 30%)
    # Window 1 "rules":   Rules (left, 50%) + Hooks (right, 50%)
    # Window 2 "workers": Workers (fullscreen)
    # Window 3 "debug":   Warnings (left, 50%) + Subagents (right, 50%)
    subprocess.run(["tmux", "new-session", "-d", "-s", session_name, main_cmd])
    subprocess.run(["tmux", "rename-window", "-t", f"{session_name}:0", "main"])
    subprocess.run(["tmux", "split-window", "-h", "-t", f"{session_name}:0.0", "-l", "30%", tokens_cmd])

    subprocess.run(["tmux", "new-window", "-t", f"{session_name}:1", "-n", "rules", rules_cmd])
    subprocess.run(["tmux", "split-window", "-h", "-t", f"{session_name}:1.0", "-l", "50%", hooks_cmd])

    subprocess.run(["tmux", "new-window", "-t", f"{session_name}:2", "-n", "workers", workers_cmd])

    subprocess.run(["tmux", "new-window", "-t", f"{session_name}:3", "-n", "debug", warnings_cmd])
    subprocess.run(["tmux", "split-window", "-h", "-t", f"{session_name}:3.0", "-l", "50%", subagent_cmd])

    subprocess.run(["tmux", "select-window", "-t", f"{session_name}:0"])

    restore_global_history_limit(original_history_limit)
    configure_tmux_session(session_name)

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
def configure_tmux_session(session_name: str) -> None:
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
    for win in range(4):
        subprocess.run(["tmux", "set-window-option", "-t", f"{session_name}:{win}", "pane-border-style", "fg=colour240"])
        subprocess.run(["tmux", "set-window-option", "-t", f"{session_name}:{win}", "pane-active-border-style", "fg=colour245"])
        subprocess.run(["tmux", "set-window-option", "-t", f"{session_name}:{win}", "wrap-search", "on"])
    subprocess.run(["tmux", "bind-key", "-T", "root", "M-m", "run-shell", f"tmux capture-pane -t {session_name}:0.0 -pS - | pbcopy && tmux display 'Main pane copied'"])
    subprocess.run(["tmux", "bind-key", "-T", "root", "M-t", "run-shell", f"tmux capture-pane -t {session_name}:0.1 -pS - | pbcopy && tmux display 'Tokens pane copied'"])
    subprocess.run(["tmux", "bind-key", "-T", "root", "M-r", "run-shell", f"tmux capture-pane -t {session_name}:1.0 -pS - | pbcopy && tmux display 'Rules pane copied'"])
    subprocess.run(["tmux", "bind-key", "-T", "root", "M-h", "run-shell", f"tmux capture-pane -t {session_name}:1.1 -pS - | pbcopy && tmux display 'Hooks pane copied'"])
    subprocess.run(["tmux", "bind-key", "-T", "root", "M-k", "run-shell", f"tmux capture-pane -t {session_name}:2.0 -pS - | pbcopy && tmux display 'Workers pane copied'"])
    subprocess.run(["tmux", "bind-key", "-T", "root", "M-w", "run-shell", f"tmux capture-pane -t {session_name}:3.0 -pS - | pbcopy && tmux display 'Warnings pane copied'"])
    subprocess.run(["tmux", "bind-key", "-T", "root", "M-s", "run-shell", f"tmux capture-pane -t {session_name}:3.1 -pS - | pbcopy && tmux display 'Subagent pane copied'"])
    subprocess.run(["tmux", "bind-key", "-T", "root", "C-f", "copy-mode", "\\;", "command-prompt", "-p", "(search):", "send-keys -X search-forward '%%'"])
    subprocess.run(["tmux", "bind-key", "-T", "copy-mode", "C-f", "command-prompt", "-p", "(search):", "send-keys -X search-forward '%%'"])
    subprocess.run(["tmux", "bind-key", "-T", "copy-mode-vi", "C-f", "command-prompt", "-p", "(search):", "send-keys -X search-forward '%%'"])
    subprocess.run(["tmux", "bind-key", "-T", "copy-mode", "Enter", "send-keys", "-X", "search-again"])
    subprocess.run(["tmux", "bind-key", "-T", "copy-mode-vi", "Enter", "send-keys", "-X", "search-again"])
    for digit in "123456789":
        subprocess.run(["tmux", "bind-key", "-T", "copy-mode", digit, "send-keys", "-X", "cancel", "\\;", "send-keys", digit])
        subprocess.run(["tmux", "bind-key", "-T", "copy-mode-vi", digit, "send-keys", "-X", "cancel", "\\;", "send-keys", digit])
    subprocess.run(["tmux", "bind-key", "-T", "root", "C-r",
        "respawn-pane", "-k", "-t", "#{session_name}:0.0", "\\;",
        "respawn-pane", "-k", "-t", "#{session_name}:0.1", "\\;",
        "respawn-pane", "-k", "-t", "#{session_name}:1.0", "\\;",
        "respawn-pane", "-k", "-t", "#{session_name}:1.1", "\\;",
        "respawn-pane", "-k", "-t", "#{session_name}:2.0", "\\;",
        "respawn-pane", "-k", "-t", "#{session_name}:3.0", "\\;",
        "respawn-pane", "-k", "-t", "#{session_name}:3.1", "\\;",
        "display", "Monitor restarted"])
