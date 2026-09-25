# INFRASTRUCTURE
import os
from src.startup import parse_arguments, setup_signal_handlers, print_startup_message
from src.tmux_launcher import launch_split_screen, restart_panes
from src.core.monitor import run_monitor

# ORCHESTRATOR

def main() -> None:
    args = parse_arguments()
    if args.mode == 'all':
        launch_split_screen(args.project, os.path.abspath(__file__))
    elif args.mode == 'restart-panes':
        restart_panes(args.session, args.project, os.path.abspath(__file__))
    elif args.mode == 'menubar':
        _run_menubar()
    elif args.mode == 'gpu':
        _run_gpu()
    elif args.mode == 'news':
        _run_news()
    elif args.mode == 'news-log':
        _run_news_log()
    else:
        _run_monitor_mode(args)

# FUNCTIONS

def _run_menubar() -> None:
    from src.menubar import run
    run()

def _run_gpu() -> None:
    from src.gpu_pane.pane import run_gpu_loop
    run_gpu_loop()

def _run_news() -> None:
    from src.news_pane.pane import run_news_loop
    run_news_loop()

def _run_news_log() -> None:
    from src.news_pane.log_pane import run_news_log_loop
    run_news_log_loop()

def _run_monitor_mode(args) -> None:
    setup_signal_handlers()
    if args.mode not in ('warnings', 'tokens', 'worker-tokens'):
        print_startup_message(args.project, args.mode)
    run_monitor(args.project, args.mode)

if __name__ == "__main__":
    main()
