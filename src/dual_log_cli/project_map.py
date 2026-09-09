# INFRASTRUCTURE
import json
import os
from pathlib import Path

from ..proxy_display.forwarded_parser import _proxy_session_id_for_project

_PROJECTS_ROOT = Path("~/.claude/projects").expanduser()
_CWD_SCAN_LINES = 40
_TRANSCRIPTS_PER_DIR = 3

# FUNCTIONS


def project_label(project_path: str) -> str:
    return os.path.basename(project_path.rstrip("/")).replace("-", "_")


def _first_cwd(transcript: Path) -> str:
    try:
        with open(transcript, encoding="utf-8") as fh:
            for index, line in enumerate(fh):
                if index >= _CWD_SCAN_LINES:
                    break
                if '"cwd"' not in line:
                    continue
                cwd = json.loads(line).get("cwd")
                if isinstance(cwd, str) and cwd:
                    return cwd
    except Exception:
        return ""
    return ""


def _project_cwd_dirs(projects_root: Path) -> dict:
    dirs = {}
    try:
        entries = sorted(projects_root.iterdir())
    except Exception:
        return dirs
    for entry in entries:
        if not entry.is_dir():
            continue
        try:
            transcripts = sorted(
                (p for p in entry.iterdir() if p.suffix == ".jsonl"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except Exception:
            continue
        for transcript in transcripts[:_TRANSCRIPTS_PER_DIR]:
            cwd = _first_cwd(transcript)
            if cwd:
                dirs[cwd] = entry
                break
    return dirs


def build_project_index(projects_root=None) -> dict:
    root = Path(projects_root) if projects_root else _PROJECTS_ROOT
    cwd_to_dir = _project_cwd_dirs(root)
    sid_to_cwd = {}
    for cwd in cwd_to_dir:
        sid_to_cwd.setdefault(_proxy_session_id_for_project(cwd), cwd)
    return {"cwd_to_dir": cwd_to_dir, "sid_to_cwd": sid_to_cwd}
