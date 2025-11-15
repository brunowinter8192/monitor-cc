# INFRASTRUCTURE
import logging
import signal
import sys

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
    print_startup_message()
    run_monitor()

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
def print_startup_message() -> None:
    logging.info("Monitor_CC started - Claude Code Tool Monitor")
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
