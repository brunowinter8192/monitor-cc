# INFRASTRUCTURE
import os

# From src/startup.py: CLI argument parsing, signal handlers, startup messages
from src.startup import parse_arguments, setup_signal_handlers, print_startup_message

# From src/tmux_launcher.py: Launch tmux split-screen session
from src.tmux_launcher import launch_split_screen

# From src/monitor.py: Run continuous monitoring loop
from src.monitor import run_monitor

# ORCHESTRATOR
def main() -> None:
    args = parse_arguments()
    if args.mode == 'all':
        launch_split_screen(args.project, args.ui, os.path.abspath(__file__))
    else:
        setup_signal_handlers()
        if args.mode not in ('rules', 'warnings', 'hooks', 'tokens', 'workers', 'subagents'):
            print_startup_message(args.project, args.mode)
        run_monitor(args.project, args.mode, args.ui)

if __name__ == "__main__":
    main()
