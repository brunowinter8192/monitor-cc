# INFRASTRUCTURE
import os

# ORCHESTRATOR

def main() -> None:
    _extend_path()
    _run_menubar()

# FUNCTIONS

def _extend_path() -> None:
    os.environ['PATH'] = '/opt/homebrew/bin:/usr/local/bin:' + os.environ.get('PATH', '/usr/bin:/bin')

def _run_menubar() -> None:
    from src.menubar import run
    run()

main()
