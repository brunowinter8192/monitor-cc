# INFRASTRUCTURE
import hashlib
import logging
import os
import subprocess
import sys
from typing import Optional

# From utils.py: ANSI colors and logging utility
from .utils import RESET, GREEN, YELLOW, BLUE, CYAN, log_tagged

log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

logger_startup = logging.getLogger('tmux_launcher.startup')
startup_handler = logging.FileHandler('src/logs/01_startup.log')
startup_handler.setFormatter(log_format)
logger_startup.addHandler(startup_handler)
logger_startup.setLevel(logging.INFO)

# ORCHESTRATOR
def launch_split_screen(project_filter: Optional[str] = None, ui: bool = False, script_path: str = '') -> None:
    log_tagged(logger_startup, "SPLIT_LAUNCH", CYAN, f"launch_split_screen: project={project_filter}, ui={ui}")

    if not is_tmux_installed():
        print("Error: tmux is not installed. Install with: brew install tmux")
        sys.exit(1)

    if is_inside_tmux():
        print("Error: Already inside tmux session. Use --mode main or --mode subagent")
        sys.exit(1)

    session_name = generate_session_name(project_filter)
    log_tagged(logger_startup, "SESS_NAME", CYAN, f"Generated session name: {session_name}")
    log_tagged(logger_startup, "SCRIPT_PATH", CYAN, f"Script path: {script_path}")

    if check_session_exists(session_name):
        print(f"Warning: Session '{session_name}' already exists for this project.")
        print("This might be a stale session. Killing it and creating fresh one...")
        kill_session(session_name)

    project_arg = f"--project {project_filter}" if project_filter else ""
    ui_flag = "--ui" if ui else ""

    main_cmd = f"python3 {script_path} --mode main {project_arg}"
    subagent_cmd = f"python3 {script_path} --mode subagent {project_arg} {ui_flag}"
    rules_cmd = f"python3 {script_path} --mode rules {project_arg}"
    warnings_cmd = f"python3 {script_path} --mode warnings {project_arg}"
    hooks_cmd = f"python3 {script_path} --mode hooks {project_arg}"

    original_history_limit = get_global_history_limit()
    log_tagged(logger_startup, "HIST_SET", BLUE, f"Setting history limit to 50000")
    subprocess.run(["tmux", "set-option", "-g", "history-limit", "50000"])

    # 5-Pane Layout:
    # Pane 0 = left (main), Pane 1 = top-right (rules), Pane 2 = mid-right (subagents), Pane 3 = bottom-right-left (hooks), Pane 4 = bottom-right-right (warnings)
    log_tagged(logger_startup, "TMUX_CREATE", GREEN, f"Creating tmux session '{session_name}'")
    subprocess.run(["tmux", "new-session", "-d", "-s", session_name, main_cmd])

    log_tagged(logger_startup, "TMUX_SPLIT_H", GREEN, f"Splitting window for subagent pane")
    subprocess.run(["tmux", "split-window", "-h", "-t", f"{session_name}:0.0", "-l", "50%", subagent_cmd])

    log_tagged(logger_startup, "TMUX_SPLIT_V", GREEN, f"Splitting right pane for rules pane")
    subprocess.run(["tmux", "split-window", "-v", "-t", f"{session_name}:0.1", "-b", "-l", "25%", rules_cmd])

    log_tagged(logger_startup, "TMUX_SPLIT_V2", GREEN, f"Splitting right pane for warnings pane")
    subprocess.run(["tmux", "split-window", "-v", "-t", f"{session_name}:0.2", "-l", "25%", warnings_cmd])

    log_tagged(logger_startup, "TMUX_SPLIT_H2", GREEN, f"Splitting warnings pane for hooks pane")
    subprocess.run(["tmux", "split-window", "-h", "-b", "-t", f"{session_name}:0.3", "-l", "50%", hooks_cmd])

    restore_global_history_limit(original_history_limit)
    configure_tmux_session(session_name)

    subprocess.run(["tmux", "attach-session", "-t", session_name])

# FUNCTIONS

# Check if tmux is installed
def is_tmux_installed() -> bool:
    result = subprocess.run(["which", "tmux"], capture_output=True)
    installed = result.returncode == 0
    log_tagged(logger_startup, "TMUX_CHECK", CYAN, f"tmux installation check: {installed}")
    return installed

# Check if already running inside tmux
def is_inside_tmux() -> bool:
    in_tmux = "TMUX" in os.environ
    log_tagged(logger_startup, "TMUX_INSIDE", CYAN, f"Inside tmux check: {in_tmux}, TMUX={os.environ.get('TMUX', 'not set')}")
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
    log_tagged(logger_startup, "SESS_EXISTS", CYAN, f"Session existence check: session={session_name}, exists={exists}")
    return exists

# Kill tmux session
def kill_session(session_name: str) -> None:
    log_tagged(logger_startup, "SESS_KILL", YELLOW, f"Killing session: {session_name}")
    subprocess.run(["tmux", "kill-session", "-t", session_name], capture_output=True)

# Get current global history-limit setting
def get_global_history_limit() -> str:
    result = subprocess.run(["tmux", "show-options", "-gv", "history-limit"], capture_output=True, text=True)
    limit = result.stdout.strip() or "2000"
    log_tagged(logger_startup, "HIST_ORIG", BLUE, f"Original history limit: {limit}")
    return limit

# Restore global history-limit to original value
def restore_global_history_limit(original_value: str) -> None:
    log_tagged(logger_startup, "HIST_RESTORE", BLUE, f"Restoring history limit to {original_value}")
    subprocess.run(["tmux", "set-option", "-g", "history-limit", original_value])

# Configure tmux session appearance and behavior
def configure_tmux_session(session_name: str) -> None:
    log_tagged(logger_startup, "TMUX_CONFIG", GREEN, f"Configuring tmux session: {session_name}")
    subprocess.run(["tmux", "set-option", "-t", session_name, "status", "on"])
    subprocess.run(["tmux", "set-option", "-t", session_name, "status-style", "bg=default"])
    subprocess.run(["tmux", "set-option", "-t", session_name, "status-left", "#{?pane_in_mode,#[fg=yellow bold] COPY #[default],#[fg=green] SCROLL #[default]}"])
    subprocess.run(["tmux", "set-option", "-t", session_name, "status-right", ""])
    subprocess.run(["tmux", "set-option", "-t", session_name, "status-left-length", "20"])
    subprocess.run(["tmux", "set-option", "-t", session_name, "window-status-format", ""])
    subprocess.run(["tmux", "set-option", "-t", session_name, "window-status-current-format", ""])
    subprocess.run(["tmux", "bind-key", "-n", "C-q", "if-shell", "-F", "#{pane_in_mode}", "send-keys -X cancel", "copy-mode"])
    subprocess.run(["tmux", "set-option", "-t", session_name, "mouse", "on"])
    subprocess.run(["tmux", "bind-key", "-T", "copy-mode", "MouseDragEnd1Pane", "send-keys", "-X", "copy-pipe", "pbcopy"])
    subprocess.run(["tmux", "bind-key", "-T", "copy-mode-vi", "MouseDragEnd1Pane", "send-keys", "-X", "copy-pipe", "pbcopy"])
    subprocess.run(["tmux", "bind-key", "-T", "root", "WheelUpPane", "if-shell", "-F", "#{mouse_any_flag}", "send-keys -M", "copy-mode; send-keys -X -N 5 scroll-up"])
    subprocess.run(["tmux", "bind-key", "-T", "root", "WheelDownPane", "if-shell", "-F", "#{mouse_any_flag}", "send-keys -M", "copy-mode; send-keys -X -N 5 scroll-down"])
    subprocess.run(["tmux", "set-window-option", "-t", session_name, "pane-border-style", "fg=colour240"])
    subprocess.run(["tmux", "set-window-option", "-t", session_name, "pane-active-border-style", "fg=colour245"])
    subprocess.run(["tmux", "set-window-option", "-t", session_name, "wrap-search", "on"])
    subprocess.run(["tmux", "bind-key", "-T", "root", "M-m", "run-shell", "tmux capture-pane -t 0 -pS - | pbcopy && tmux display 'Main pane copied'"])
    subprocess.run(["tmux", "bind-key", "-T", "root", "M-s", "run-shell", "tmux capture-pane -t 2 -pS - | pbcopy && tmux display 'Subagent pane copied'"])
    subprocess.run(["tmux", "bind-key", "-T", "root", "M-r", "run-shell", "tmux capture-pane -t 1 -pS - | pbcopy && tmux display 'Rules pane copied'"])
    subprocess.run(["tmux", "bind-key", "-T", "root", "M-h", "run-shell", "tmux capture-pane -t 3 -pS - | pbcopy && tmux display 'Hooks pane copied'"])
    subprocess.run(["tmux", "bind-key", "-T", "root", "M-w", "run-shell", "tmux capture-pane -t 4 -pS - | pbcopy && tmux display 'Warnings pane copied'"])
    subprocess.run(["tmux", "bind-key", "-T", "root", "C-f", "copy-mode", "\\;", "command-prompt", "-p", "(search):", "send-keys -X search-forward '%%'"])
    subprocess.run(["tmux", "bind-key", "-T", "copy-mode", "C-f", "command-prompt", "-p", "(search):", "send-keys -X search-forward '%%'"])
    subprocess.run(["tmux", "bind-key", "-T", "copy-mode-vi", "C-f", "command-prompt", "-p", "(search):", "send-keys -X search-forward '%%'"])
    subprocess.run(["tmux", "bind-key", "-T", "copy-mode", "Enter", "send-keys", "-X", "search-again"])
    subprocess.run(["tmux", "bind-key", "-T", "copy-mode-vi", "Enter", "send-keys", "-X", "search-again"])
    for digit in "123456789":
        subprocess.run(["tmux", "bind-key", "-T", "copy-mode", digit, "send-keys", "-X", "cancel", "\\;", "send-keys", digit])
        subprocess.run(["tmux", "bind-key", "-T", "copy-mode-vi", digit, "send-keys", "-X", "cancel", "\\;", "send-keys", digit])
