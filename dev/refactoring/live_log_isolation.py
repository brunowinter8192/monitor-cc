# INFRASTRUCTURE
import atexit
import os
import shutil
import tempfile
from pathlib import Path

FIRING_LOG_ENV = 'MONITOR_CC_HOOK_FIRING_LOG'
HOME_ENV = 'HOME'
MONITOR_ROOT_ENV = 'MONITOR_CC_ROOT'


# FUNCTIONS

def isolate_hook_firing_log(prefix: str) -> str:
    path = str(Path(make_temp_dir(prefix)) / 'hook_firing.jsonl')
    os.environ[FIRING_LOG_ENV] = path
    return path


def isolate_home(prefix: str, real_files: tuple = ()) -> str:
    real_home = Path.home()
    home = make_temp_dir(prefix)
    copy_real_files(real_home, Path(home), real_files)
    os.environ[HOME_ENV] = home
    return home


def isolate_monitor_root(prefix: str) -> str:
    root = make_temp_dir(prefix)
    os.environ[MONITOR_ROOT_ENV] = root
    return root


def copy_real_files(real_home: Path, home: Path, relative_paths: tuple) -> None:
    for relative in relative_paths:
        source = real_home / relative
        if source.is_file():
            (home / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(source, home / relative)


def make_temp_dir(prefix: str) -> str:
    path = tempfile.mkdtemp(prefix=prefix)
    atexit.register(shutil.rmtree, path, True)
    return path
