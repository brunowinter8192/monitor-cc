# INFRASTRUCTURE
import json
import os
from pathlib import Path

from ..proxy_display.forwarded_parser import _proxy_session_id_for_project

# CC keeps one directory per project cwd. The directory NAME is a lossy encoding of the path
# (a "-" may be a separator or a literal hyphen), but the transcript records inside carry the real
# absolute path in a "cwd" field — ground truth, no decoding heuristics needed.
_PROJECTS_ROOT = Path("~/.claude/projects").expanduser()
_CWD_SCAN_LINES = 40          # the first records are mode/permission-mode entries without a cwd
_TRANSCRIPTS_PER_DIR = 3      # newest first; stop at the first one that yields a cwd

# FUNCTIONS


# Project label as the main-session stems already spell it: basename with "-" collapsed to "_"
# (monitor-cc → monitor_cc, gh-cli → gh_cli). Same spelling on both sides is what lets ONE context
# filter term match a main session and its workers together.
def project_label(project_path: str) -> str:
    return os.path.basename(project_path.rstrip("/")).replace("-", "_")


# First "cwd" value in a transcript, or "" — fail-open, a broken transcript just contributes nothing
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


# {cwd: directory} — one entry per project CC has a transcript for. A dict rather than the set
# an earlier version returned, so a caller can walk back from a cwd to the actual directory it
# lives in (usage.py scopes a transcript search to it) instead of only knowing the cwd exists.
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


# One walk of the transcript store, in two shapes a caller can join stem parts against without
# re-walking: `cwd_to_dir` for a main stem's label match (`discovery.project_for_stem` filters
# every cwd whose `project_label` equals the stem's label), `sid_to_cwd` for a worker stem's sid8
# lookup — the proxy's own `md5(project_path)[:8]` hash, mapped here to the real PROJECT path
# rather than collapsed to a label (2026-09-10: `discovery.project_for_stem` prints this path
# directly as `sessions`' PROJECT column; `usage.py` additionally derives the worker's OWN
# worktree cwd from it by appending the worktree suffix).
def build_project_index(projects_root=None) -> dict:
    root = Path(projects_root) if projects_root else _PROJECTS_ROOT
    cwd_to_dir = _project_cwd_dirs(root)
    sid_to_cwd = {}
    for cwd in cwd_to_dir:
        sid_to_cwd.setdefault(_proxy_session_id_for_project(cwd), cwd)
    return {"cwd_to_dir": cwd_to_dir, "sid_to_cwd": sid_to_cwd}
