# INFRASTRUCTURE
from datetime import datetime
from pathlib import Path

# FUNCTIONS

def report_root(log_path: Path, root: Path, source: str) -> None:
    line = f'{datetime.now().isoformat(timespec="seconds")} [paths] PROJECT_ROOT resolved: source={source} root={root}\n'
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, 'a') as fh:
            fh.write(line)
    except OSError:
        pass
