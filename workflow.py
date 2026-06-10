# INFRASTRUCTURE
import os

# From src/startup.py: CLI argument parsing, signal handlers, startup messages
from src.startup import parse_arguments, setup_signal_handlers, print_startup_message

# From src/tmux_launcher.py: Launch tmux split-screen session; self-heal missing panes
from src.tmux_launcher import launch_split_screen, restart_panes

# From src/core/monitor.py: Run continuous monitoring loop
from src.core.monitor import run_monitor

# ORCHESTRATOR
def main() -> None:
    args = parse_arguments()
    if args.mode == 'all':
        launch_split_screen(args.project, os.path.abspath(__file__))
    elif args.mode == 'restart-panes':
        restart_panes(args.session, args.project, os.path.abspath(__file__))
    elif args.mode == 'menubar':
        from src.menubar import run
        run()
    elif args.mode == 'gpu':
        from src.gpu_pane.pane import run_gpu_loop
        run_gpu_loop()
    elif args.mode == 'news':
        from src.news_pane.pane import run_news_loop
        run_news_loop()
    elif args.mode == 'news-log':
        from src.news_pane.log_pane import run_news_log_loop
        run_news_log_loop()
    else:
        setup_signal_handlers()
        if args.mode not in ('warnings', 'tokens', 'workers'):
            print_startup_message(args.project, args.mode)
        run_monitor(args.project, args.mode)

if __name__ == "__main__":
    main()
