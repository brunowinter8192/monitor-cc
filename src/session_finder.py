# INFRASTRUCTURE
import logging
import os
from pathlib import Path
from typing import List, Optional

# ANSI Colors
RESET = '\033[0m'
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'

logging.basicConfig(
    filename='src/logs/03_session_discovery.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Tagged logging helper
def log_tagged(tag: str, color: str, message: str) -> None:
    colored_tag = f"{color}[{tag}]{RESET}"
    logging.info(f"{colored_tag} {message}")

CLAUDE_PROJECTS_DIR = Path.home() / '.claude' / 'projects'

# ORCHESTRATOR
def find_active_sessions(project_filter: Optional[str] = None) -> List[Path]:
    log_tagged("FIND_SESS", BLUE, f"find_active_sessions called with filter: {project_filter}")
    project_dirs = get_project_directories()
    jsonl_files = collect_jsonl_files(project_dirs, project_filter)
    sorted_files = sort_by_modification_time(jsonl_files)
    log_tagged("ACTIVE_SESS", GREEN, f"Found {len(sorted_files)} active sessions")
    return sorted_files

# FUNCTIONS

# Get all project directories in ~/.claude/projects
def get_project_directories() -> List[Path]:
    if not CLAUDE_PROJECTS_DIR.exists():
        log_tagged("NO_PROJ_DIR", RED, f"Claude projects directory not found: {CLAUDE_PROJECTS_DIR}")
        return []

    project_dirs = [d for d in CLAUDE_PROJECTS_DIR.iterdir() if d.is_dir()]
    log_tagged("PROJ_DIRS", BLUE, f"Found {len(project_dirs)} project directories: {[d.name for d in project_dirs]}")
    return project_dirs

# Collect all JSONL files from project directories
def collect_jsonl_files(project_dirs: List[Path], project_filter: Optional[str] = None) -> List[Path]:
    log_tagged("COLLECT_JSONL", BLUE, f"Collecting JSONL files from {len(project_dirs)} directories, filter={project_filter}")
    jsonl_files = []

    for project_dir in project_dirs:
        if project_filter and not matches_project_filter(project_dir, project_filter):
            log_tagged("FILTER_SKIP", YELLOW, f"Skipping {project_dir.name} (filter mismatch)")
            continue
        files = list(project_dir.glob('*.jsonl'))
        log_tagged("JSONL_FOUND", BLUE, f"Found {len(files)} JSONL files in {project_dir.name}: {[f.name for f in files]}")
        jsonl_files.extend(files)

    log_tagged("TOTAL_JSONL", GREEN, f"Collected {len(jsonl_files)} total JSONL files")
    return jsonl_files

# Check if project directory matches the filter path
def matches_project_filter(project_dir: Path, project_filter: str) -> bool:
    encoded_filter = encode_project_path(project_filter)
    matches = project_dir.name == encoded_filter
    log_tagged("FILTER_MATCH", BLUE, f"Filter match: {project_dir.name} vs {encoded_filter} = {matches}")
    return matches

# Encode project path to match Claude's directory naming convention
def encode_project_path(path: str) -> str:
    encoded = path.replace('/', '-').replace('_', '-')
    log_tagged("PATH_ENCODE", BLUE, f"Encoded path: '{path}' -> '{encoded}'")
    return encoded

# Sort files by modification time (newest first)
def sort_by_modification_time(files: List[Path]) -> List[Path]:
    sorted_files = sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)
    if sorted_files:
        log_tagged("SORT_FILES", BLUE, f"Sorted {len(sorted_files)} files, newest: {sorted_files[0].name}")
    return sorted_files

# Check if file has been modified since last check
def is_modified_since(filepath: Path, last_mtime: float) -> bool:
    current_mtime = filepath.stat().st_mtime
    return current_mtime > last_mtime

# Get current modification time of file
def get_modification_time(filepath: Path) -> float:
    return filepath.stat().st_mtime
