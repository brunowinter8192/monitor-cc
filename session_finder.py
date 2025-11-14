# INFRASTRUCTURE
import os
from pathlib import Path
from typing import List

CLAUDE_PROJECTS_DIR = Path.home() / '.claude' / 'projects'

# ORCHESTRATOR
def find_active_sessions() -> List[Path]:
    project_dirs = get_project_directories()
    jsonl_files = collect_jsonl_files(project_dirs)
    return sort_by_modification_time(jsonl_files)

# FUNCTIONS

# Get all project directories in ~/.claude/projects
def get_project_directories() -> List[Path]:
    if not CLAUDE_PROJECTS_DIR.exists():
        return []

    return [d for d in CLAUDE_PROJECTS_DIR.iterdir() if d.is_dir()]

# Collect all JSONL files from project directories
def collect_jsonl_files(project_dirs: List[Path]) -> List[Path]:
    jsonl_files = []

    for project_dir in project_dirs:
        files = list(project_dir.glob('*.jsonl'))
        jsonl_files.extend(files)

    return jsonl_files

# Sort files by modification time (newest first)
def sort_by_modification_time(files: List[Path]) -> List[Path]:
    return sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)

# Check if file has been modified since last check
def is_modified_since(filepath: Path, last_mtime: float) -> bool:
    current_mtime = filepath.stat().st_mtime
    return current_mtime > last_mtime

# Get current modification time of file
def get_modification_time(filepath: Path) -> float:
    return filepath.stat().st_mtime
