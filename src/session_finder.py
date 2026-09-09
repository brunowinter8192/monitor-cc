# INFRASTRUCTURE
import os
from pathlib import Path
from typing import List, Optional

from .colors import RESET, RED, GREEN, YELLOW, BLUE

CLAUDE_PROJECTS_DIR = Path.home() / '.claude' / 'projects'

_last_session_count: Optional[int] = None
_last_jsonl_count: Optional[int] = None
_project_dirs_logged: bool = False

# ORCHESTRATOR
def find_active_sessions(project_filter: Optional[str] = None) -> List[Path]:
    global _last_session_count

    project_dirs = get_project_directories()
    jsonl_files = collect_jsonl_files(project_dirs, project_filter)
    sorted_files = sort_by_modification_time(jsonl_files)

    if _last_session_count != len(sorted_files):
        _last_session_count = len(sorted_files)

    return sorted_files

# FUNCTIONS

def get_project_directories() -> List[Path]:
    global _project_dirs_logged

    if not CLAUDE_PROJECTS_DIR.exists():
        return []

    project_dirs = [d for d in CLAUDE_PROJECTS_DIR.iterdir() if d.is_dir()]

    if not _project_dirs_logged:
        _project_dirs_logged = True

    return project_dirs

def collect_jsonl_files(project_dirs: List[Path], project_filter: Optional[str] = None) -> List[Path]:
    global _last_jsonl_count

    jsonl_files = []

    for project_dir in project_dirs:
        if project_filter and not matches_project_filter(project_dir, project_filter):
            continue
        files = list(project_dir.glob('*.jsonl'))
        files.extend(project_dir.glob('*/subagents/agent-*.jsonl'))
        jsonl_files.extend(files)

    if _last_jsonl_count != len(jsonl_files):
        _last_jsonl_count = len(jsonl_files)

    return jsonl_files

def matches_project_filter(project_dir: Path, project_filter: str) -> bool:
    encoded_filter = encode_project_path(project_filter)
    matches = project_dir.name.lower() == encoded_filter.lower()
    return matches

def encode_project_path(path: str) -> str:
    encoded = path.replace('/', '-').replace('_', '-').replace('.', '-')
    return encoded

def sort_by_modification_time(files: List[Path]) -> List[Path]:
    sorted_files = sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)
    return sorted_files

def is_modified_since(filepath: Path, last_mtime: float) -> bool:
    current_mtime = filepath.stat().st_mtime
    return current_mtime > last_mtime

def get_modification_time(filepath: Path) -> float:
    return filepath.stat().st_mtime
