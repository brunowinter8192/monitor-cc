# INFRASTRUCTURE
import argparse
import signal
import sys
from typing import Optional

# From constants.py: Colors
from .constants import RESET, RED, GREEN, MAGENTA

# ORCHESTRATOR
def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Claude Code Tool Monitor')
    parser.add_argument('--project', type=str, default=None, help='Filter by project path')
    parser.add_argument('--mode', type=str, choices=['all', 'main', 'subagent', 'rules', 'warnings', 'hooks', 'tokens', 'workers', 'proxy', 'metadata'], default='all', help='Monitor mode: all, main, subagent, rules, warnings, hooks, tokens, workers, proxy, or metadata')
    parser.add_argument('--ui', action='store_true', help='Enable collapsible UI mode (subagent only)')
    args = parser.parse_args()
    return args

# FUNCTIONS

# Setup signal handlers for graceful shutdown
def setup_signal_handlers() -> None:
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

# Handle shutdown signals
def handle_shutdown(signum, frame) -> None:
    print_shutdown_message()
    sys.exit(0)

# Print startup message
def print_startup_message(project_filter: Optional[str] = None, mode: str = 'all') -> None:
    print(f"{GREEN}Monitor_CC - Claude Code Tool Monitor{RESET}")

    if project_filter:
        print(f"Monitoring project: {project_filter}")
    else:
        print("Monitoring ~/.claude/projects for tool calls...")

    mode_labels = {'main': 'MAIN AGENT', 'subagent': 'SUBAGENT', 'rules': 'RULES', 'warnings': 'WARNINGS', 'hooks': 'HOOKS', 'tokens': 'TOKENS'}
    if mode in mode_labels:
        print(f"Mode: {mode_labels[mode]} only")

    print("Press Ctrl+C to stop\n")

# Print shutdown message
def print_shutdown_message() -> None:
    print(f"\n{GREEN}Monitor stopped{RESET}")
