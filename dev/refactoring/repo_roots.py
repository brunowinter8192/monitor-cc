# INFRASTRUCTURE
import os
import subprocess
from pathlib import Path


# FUNCTIONS
def resolve_main_project(start_dir: str) -> str:
    p = start_dir
    while p != os.path.dirname(p):
        git = os.path.join(p, ".git")
        if os.path.isfile(git):
            content = open(git).read().strip()
            if content.startswith("gitdir:"):
                gitdir = content[len("gitdir:"):].strip()
                return os.path.dirname(os.path.dirname(os.path.dirname(gitdir)))
        elif os.path.isdir(git):
            return p
        p = os.path.dirname(p)
    raise RuntimeError("Cannot find main project root")


def resolve_repo_root(script_file: str):
    if 'MONITOR_CC_ROOT' in os.environ:
        return Path(os.environ['MONITOR_CC_ROOT'])
    candidate = Path(script_file).parent.parent.parent
    if (candidate / 'src' / 'logs').is_dir():
        return candidate
    try:
        git_common = subprocess.run(
            ['git', 'rev-parse', '--git-common-dir'],
            capture_output=True, text=True, cwd=str(candidate),
        ).stdout.strip()
        if git_common:
            main_root = Path(git_common).resolve().parent
            if (main_root / 'src' / 'logs').is_dir():
                return main_root
    except Exception:
        pass
    return candidate
