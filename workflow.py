# INFRASTRUCTURE
import argparse
import hashlib
import logging
import os
import signal
import subprocess
import sys
from typing import Optional

# ANSI Colors
RESET = '\033[0m'
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
MAGENTA = '\033[95m'
CYAN = '\033[96m'
WHITE = '\033[97m'

log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

logger_startup = logging.getLogger('workflow.startup')
startup_handler = logging.FileHandler('src/logs/01_startup.log')
startup_handler.setFormatter(log_format)
logger_startup.addHandler(startup_handler)
logger_startup.setLevel(logging.INFO)

# Tagged logging helper
def log_tagged(logger, tag: str, color: str, message: str) -> None:
    colored_tag = f"{color}[{tag}]{RESET}"
    logger.info(f"{colored_tag} {message}")

# From src/monitor.py: Run continuous monitoring loop
from src.monitor import run_monitor

# ORCHESTRATOR
def main() -> None:
    args = parse_arguments()
    log_tagged(logger_startup, "MAIN_ENTRY", MAGENTA, f"main() called with args: mode={args.mode}, project={args.project}, ui={args.ui}")
    if args.mode == 'all':
        launch_split_screen(args.project, args.ui)
    else:
        setup_signal_handlers()
        print_startup_message(args.project, args.mode)
        run_monitor(args.project, args.mode, args.ui)

# FUNCTIONS

# Launch tmux split-screen with main and subagent monitors
def launch_split_screen(project_filter: Optional[str] = None, ui: bool = False) -> None:
    log_tagged(logger_startup, "SPLIT_LAUNCH", CYAN, f"launch_split_screen: project={project_filter}, ui={ui}")

    if not is_tmux_installed():
        print("Error: tmux is not installed. Install with: brew install tmux")
        sys.exit(1)

    if is_inside_tmux():
        print("Error: Already inside tmux session. Use --mode main or --mode subagent")
        sys.exit(1)

    session_name = generate_session_name(project_filter)
    script_path = os.path.abspath(__file__)
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

    original_history_limit = get_global_history_limit()
    log_tagged(logger_startup, "HIST_SET", BLUE, f"Setting history limit to 50000")
    subprocess.run(["tmux", "set-option", "-g", "history-limit", "50000"])

    log_tagged(logger_startup, "TMUX_CREATE", GREEN, f"Creating tmux session '{session_name}'")
    subprocess.run(["tmux", "new-session", "-d", "-s", session_name, main_cmd])

    log_tagged(logger_startup, "TMUX_SPLIT", GREEN, f"Splitting window for subagent pane")
    subprocess.run(["tmux", "split-window", "-h", "-t", session_name, subagent_cmd])

    restore_global_history_limit(original_history_limit)
    configure_tmux_session(session_name)

    subprocess.run(["tmux", "attach-session", "-t", session_name])

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
    subprocess.run(["tmux", "bind-key", "-T", "root", "WheelUpPane", "if-shell", "-F", "#{mouse_any_flag}", "send-keys -M", "copy-mode -e; send-keys -X -N 5 scroll-up"])
    subprocess.run(["tmux", "bind-key", "-T", "root", "WheelDownPane", "if-shell", "-F", "#{mouse_any_flag}", "send-keys -M", "copy-mode -e; send-keys -X -N 5 scroll-down"])
    subprocess.run(["tmux", "set-window-option", "-t", session_name, "pane-border-style", "fg=colour240"])
    subprocess.run(["tmux", "set-window-option", "-t", session_name, "pane-active-border-style", "fg=colour245"])
    subprocess.run(["tmux", "bind-key", "-T", "root", "M-m", "run-shell", "tmux capture-pane -t 0 -pS - | pbcopy && tmux display 'Main pane copied'"])
    subprocess.run(["tmux", "bind-key", "-T", "root", "M-s", "run-shell", "tmux capture-pane -t 1 -pS - | pbcopy && tmux display 'Subagent pane copied'"])

# Setup signal handlers for graceful shutdown
def setup_signal_handlers() -> None:
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    log_tagged(logger_startup, "SIGNAL_REG", MAGENTA, "Signal handlers registered for SIGINT and SIGTERM")

# Handle shutdown signals
def handle_shutdown(signum, frame) -> None:
    log_tagged(logger_startup, "SHUTDOWN", RED, f"Shutdown signal received: {signum}")
    print_shutdown_message()
    sys.exit(0)

# Parse command line arguments
def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Claude Code Tool Monitor')
    parser.add_argument('--project', type=str, default=None, help='Filter by project path')
    parser.add_argument('--mode', type=str, choices=['all', 'main', 'subagent'], default='all', help='Monitor mode: all, main, or subagent')
    parser.add_argument('--ui', action='store_true', help='Enable collapsible UI mode (subagent only)')
    args = parser.parse_args()
    log_tagged(logger_startup, "ARGPARSE", MAGENTA, f"Arguments parsed: mode={args.mode}, project={args.project}, ui={args.ui}")
    return args

# Print startup message
def print_startup_message(project_filter: Optional[str] = None, mode: str = 'all') -> None:
    log_tagged(logger_startup, "MONITOR_START", GREEN, "Monitor_CC started - Claude Code Tool Monitor")
    print("\033[38;5;35mMonitor_CC - Claude Code Tool Monitor\033[0m")

    if project_filter:
        print(f"Monitoring project: {project_filter}")
    else:
        print("Monitoring ~/.claude/projects for tool calls...")

    if mode != 'all':
        mode_label = 'MAIN AGENT' if mode == 'main' else 'SUBAGENT'
        print(f"Mode: {mode_label} only")

    print("Press Ctrl+C to stop\n")

# Print shutdown message
def print_shutdown_message() -> None:
    print("\n\033[38;5;35mMonitor stopped\033[0m")

if __name__ == "__main__":
    main()
