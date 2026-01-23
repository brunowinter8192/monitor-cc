# INFRASTRUCTURE
import logging
import os
from pathlib import Path
from typing import List, Optional

# From utils.py: ANSI colors and logging utility
from .utils import RESET, RED, GREEN, YELLOW, BLUE, log_tagged

log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

logger_discovery = logging.getLogger('session_finder.discovery')
discovery_handler = logging.FileHandler('src/logs/03_session_discovery.log')
discovery_handler.setFormatter(log_format)
logger_discovery.addHandler(discovery_handler)
logger_discovery.setLevel(logging.INFO)

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
        log_tagged(logger_discovery, "ACTIVE_SESS", GREEN, f"Active sessions changed: {len(sorted_files)} (was {_last_session_count})")
        _last_session_count = len(sorted_files)

    return sorted_files

# FUNCTIONS

# Get all project directories in ~/.claude/projects
def get_project_directories() -> List[Path]:
    global _project_dirs_logged

    if not CLAUDE_PROJECTS_DIR.exists():
        log_tagged(logger_discovery, "NO_PROJ_DIR", RED, f"Claude projects directory not found: {CLAUDE_PROJECTS_DIR}")
        return []

    project_dirs = [d for d in CLAUDE_PROJECTS_DIR.iterdir() if d.is_dir()]

    if not _project_dirs_logged:
        log_tagged(logger_discovery, "PROJ_DIRS", BLUE, f"Found {len(project_dirs)} project directories")
        _project_dirs_logged = True

    return project_dirs

# Collect all JSONL files from project directories
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
        log_tagged(logger_discovery, "TOTAL_JSONL", GREEN, f"Total JSONL files changed: {len(jsonl_files)} (was {_last_jsonl_count})")
        _last_jsonl_count = len(jsonl_files)

    return jsonl_files

# Check if project directory matches the filter path
def matches_project_filter(project_dir: Path, project_filter: str) -> bool:
    encoded_filter = encode_project_path(project_filter)
    matches = project_dir.name == encoded_filter
    return matches

# Encode project path to match Claude's directory naming convention
def encode_project_path(path: str) -> str:
    encoded = path.replace('/', '-').replace('_', '-')
    return encoded

# Sort files by modification time (newest first)
def sort_by_modification_time(files: List[Path]) -> List[Path]:
    sorted_files = sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)
    return sorted_files

# Check if file has been modified since last check
def is_modified_since(filepath: Path, last_mtime: float) -> bool:
    current_mtime = filepath.stat().st_mtime
    return current_mtime > last_mtime

# Get current modification time of file
def get_modification_time(filepath: Path) -> float:
    return filepath.stat().st_mtime
