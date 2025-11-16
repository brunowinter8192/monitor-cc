# INFRASTRUCTURE
import logging
import signal
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
    setup_signal_handlers()
    project_filter = parse_project_filter()
    print_startup_message(project_filter)
    run_monitor(project_filter)

# FUNCTIONS

# Setup signal handlers for graceful shutdown
def setup_signal_handlers() -> None:
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

# Handle shutdown signals
def handle_shutdown(signum, frame) -> None:
    print_shutdown_message()
    sys.exit(0)

# Parse project filter from command line arguments
def parse_project_filter() -> Optional[str]:
    if len(sys.argv) > 1:
        return sys.argv[1]
    return None

# Print startup message
def print_startup_message(project_filter: Optional[str] = None) -> None:
    logging.info("Monitor_CC started - Claude Code Tool Monitor")
    if project_filter:
        logging.info(f"Monitoring project: {project_filter}")
        print("\033[38;5;35mMonitor_CC - Claude Code Tool Monitor\033[0m")
        print(f"Monitoring project: {project_filter}")
    else:
        logging.info("Monitoring ~/.claude/projects for tool calls")
        print("\033[38;5;35mMonitor_CC - Claude Code Tool Monitor\033[0m")
        print("Monitoring ~/.claude/projects for tool calls...")
    print("Press Ctrl+C to stop\n")

# Print shutdown message
def print_shutdown_message() -> None:
    logging.info("Monitor stopped - shutdown signal received")
    print("\n\033[38;5;35mMonitor stopped\033[0m")

if __name__ == "__main__":
    main()
