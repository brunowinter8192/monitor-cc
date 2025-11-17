# INFRASTRUCTURE
import argparse
import hashlib
import logging
import os
import signal
import subprocess
import sys
from typing import Optional

logging.basicConfig(
    filename='logs/workflow.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# From monitor.py: Run continuous monitoring loop
from monitor import run_monitor

# ORCHESTRATOR
def main() -> None:
    args = parse_arguments()
    if args.mode == 'all':
        launch_split_screen(args.project)
    else:
        setup_signal_handlers()
        print_startup_message(args.project, args.mode)
        run_monitor(args.project, args.mode)

# FUNCTIONS

# Launch tmux split-screen with main and subagent monitors
def launch_split_screen(project_filter: Optional[str] = None) -> None:
    if not is_tmux_installed():
        print("Error: tmux is not installed. Install with: brew install tmux")
        sys.exit(1)

    if is_inside_tmux():
        print("Error: Already inside tmux session. Use --mode main or --mode subagent")
        sys.exit(1)

    session_name = generate_session_name(project_filter)
    script_path = os.path.abspath(__file__)

    if check_session_exists(session_name):
        print(f"Warning: Session '{session_name}' already exists for this project.")
        print("This might be a stale session. Killing it and creating fresh one...")
        kill_session(session_name)

    project_arg = f"--project {project_filter}" if project_filter else ""

    main_cmd = f"python3 {script_path} --mode main {project_arg}"
    subagent_cmd = f"python3 {script_path} --mode subagent {project_arg}"

    subprocess.run(["tmux", "new-session", "-d", "-s", session_name, main_cmd])
    configure_tmux_session(session_name)
    subprocess.run(["tmux", "split-window", "-h", "-t", session_name, subagent_cmd])
    subprocess.run(["tmux", "attach-session", "-t", session_name])

# Check if tmux is installed
def is_tmux_installed() -> bool:
    result = subprocess.run(["which", "tmux"], capture_output=True)
    return result.returncode == 0

# Check if already running inside tmux
def is_inside_tmux() -> bool:
    return "TMUX" in os.environ

# Generate unique session name from project path
def generate_session_name(project_path: Optional[str] = None) -> str:
    if project_path is None:
        return "monitor_cc_global"
    normalized_path = os.path.normpath(os.path.expanduser(project_path))
    path_hash = hashlib.md5(normalized_path.encode()).hexdigest()[:8]
    return f"monitor_cc_{path_hash}"

# Check if tmux session exists
def check_session_exists(session_name: str) -> bool:
    result = subprocess.run(["tmux", "has-session", "-t", session_name], capture_output=True)
    return result.returncode == 0

# Kill tmux session
def kill_session(session_name: str) -> None:
    subprocess.run(["tmux", "kill-session", "-t", session_name], capture_output=True)

# Configure tmux session appearance and behavior
def configure_tmux_session(session_name: str) -> None:
    subprocess.run(["tmux", "set-option", "-t", session_name, "status", "off"])
    subprocess.run(["tmux", "set-option", "-t", session_name, "history-limit", "0"])
    subprocess.run(["tmux", "set-option", "-t", session_name, "mouse", "on"])
    subprocess.run(["tmux", "bind", "-T", "copy-mode", "MouseDragEnd1Pane", "send-keys", "-X", "copy-pipe-and-cancel", "pbcopy"])
    subprocess.run(["tmux", "bind", "-T", "copy-mode-vi", "MouseDragEnd1Pane", "send-keys", "-X", "copy-pipe-and-cancel", "pbcopy"])
    subprocess.run(["tmux", "set-window-option", "-t", session_name, "pane-border-style", "fg=colour240"])
    subprocess.run(["tmux", "set-window-option", "-t", session_name, "pane-active-border-style", "fg=colour245"])

# Setup signal handlers for graceful shutdown
def setup_signal_handlers() -> None:
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

# Handle shutdown signals
def handle_shutdown(signum, frame) -> None:
    print_shutdown_message()
    sys.exit(0)

# Parse command line arguments
def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Claude Code Tool Monitor')
    parser.add_argument('--project', type=str, default=None, help='Filter by project path')
    parser.add_argument('--mode', type=str, choices=['all', 'main', 'subagent'], default='all', help='Monitor mode: all, main, or subagent')
    return parser.parse_args()

# Print startup message
def print_startup_message(project_filter: Optional[str] = None, mode: str = 'all') -> None:
    logging.info("Monitor_CC started - Claude Code Tool Monitor")
    print("\033[38;5;35mMonitor_CC - Claude Code Tool Monitor\033[0m")

    if project_filter:
        logging.info(f"Monitoring project: {project_filter}")
        print(f"Monitoring project: {project_filter}")
    else:
        logging.info("Monitoring ~/.claude/projects for tool calls")
        print("Monitoring ~/.claude/projects for tool calls...")

    if mode != 'all':
        mode_label = 'MAIN AGENT' if mode == 'main' else 'SUBAGENT'
        logging.info(f"Mode: {mode}")
        print(f"Mode: {mode_label} only")

    print("Press Ctrl+C to stop\n")

# Print shutdown message
def print_shutdown_message() -> None:
    logging.info("Monitor stopped - shutdown signal received")
    print("\n\033[38;5;35mMonitor stopped\033[0m")

if __name__ == "__main__":
    main()
