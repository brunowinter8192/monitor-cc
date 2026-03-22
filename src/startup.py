# INFRASTRUCTURE
import argparse
import logging
import signal
import sys
from typing import Optional

# From utils.py: ANSI colors and logging utility
from .utils import RESET, RED, GREEN, MAGENTA, log_tagged

log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

logger_startup = logging.getLogger('startup.startup')
startup_handler = logging.FileHandler('src/logs/01_startup.log')
startup_handler.setFormatter(log_format)
logger_startup.addHandler(startup_handler)
logger_startup.setLevel(logging.INFO)

# ORCHESTRATOR
def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Claude Code Tool Monitor')
    parser.add_argument('--project', type=str, default=None, help='Filter by project path')
    parser.add_argument('--mode', type=str, choices=['all', 'main', 'subagent', 'rules', 'warnings', 'hooks'], default='all', help='Monitor mode: all, main, subagent, rules, warnings, or hooks')
    parser.add_argument('--ui', action='store_true', help='Enable collapsible UI mode (subagent only)')
    args = parser.parse_args()
    log_tagged(logger_startup, "ARGPARSE", MAGENTA, f"Arguments parsed: mode={args.mode}, project={args.project}, ui={args.ui}")
    return args

# FUNCTIONS

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

# Print startup message
def print_startup_message(project_filter: Optional[str] = None, mode: str = 'all') -> None:
    log_tagged(logger_startup, "MONITOR_START", GREEN, "Monitor_CC started - Claude Code Tool Monitor")
    print("\033[38;5;35mMonitor_CC - Claude Code Tool Monitor\033[0m")

    if project_filter:
        print(f"Monitoring project: {project_filter}")
    else:
        print("Monitoring ~/.claude/projects for tool calls...")

    mode_labels = {'main': 'MAIN AGENT', 'subagent': 'SUBAGENT', 'rules': 'RULES', 'warnings': 'WARNINGS', 'hooks': 'HOOKS'}
    if mode in mode_labels:
        print(f"Mode: {mode_labels[mode]} only")

    print("Press Ctrl+C to stop\n")

# Print shutdown message
def print_shutdown_message() -> None:
    print("\n\033[38;5;35mMonitor stopped\033[0m")
