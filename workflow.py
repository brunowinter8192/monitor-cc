# INFRASTRUCTURE
import logging
import os

# From src/utils.py: ANSI colors and logging utility
from src.utils import MAGENTA, log_tagged

log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

logger_startup = logging.getLogger('workflow.startup')
startup_handler = logging.FileHandler('src/logs/01_startup.log')
startup_handler.setFormatter(log_format)
logger_startup.addHandler(startup_handler)
logger_startup.setLevel(logging.INFO)

# From src/startup.py: CLI argument parsing, signal handlers, startup messages
from src.startup import parse_arguments, setup_signal_handlers, print_startup_message

# From src/tmux_launcher.py: Launch tmux split-screen session
from src.tmux_launcher import launch_split_screen

# From src/monitor.py: Run continuous monitoring loop
from src.monitor import run_monitor

# ORCHESTRATOR
def main() -> None:
    args = parse_arguments()
    log_tagged(logger_startup, "MAIN_ENTRY", MAGENTA, f"main() called with args: mode={args.mode}, project={args.project}, ui={args.ui}")
    if args.mode == 'all':
        launch_split_screen(args.project, args.ui, os.path.abspath(__file__))
    else:
        setup_signal_handlers()
        if args.mode not in ('rules', 'warnings', 'hooks'):
            print_startup_message(args.project, args.mode)
        run_monitor(args.project, args.mode, args.ui)

if __name__ == "__main__":
    main()
