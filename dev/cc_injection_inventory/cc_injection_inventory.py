# INFRASTRUCTURE
import argparse
import glob as globmod
from pathlib import Path

from cc_injection_extraction import _process_file
from cc_injection_aggregation import _finalize_pending_user_text
from cc_injection_report import _build_report, _write_report, _print_console_summary

_SCRIPT_DIR = Path(__file__).resolve().parent
_WORKTREE_ROOT = _SCRIPT_DIR.parents[1]

_DEFAULT_GLOB = "api_requests_*_original.jsonl"

_WORKER_LOG_PREFIX = "api_requests_worker_"

_MODULE_DESCRIPTION = """
cc_injection_inventory.py — complete inventory of every distinguishable text class present
in raw Claude Code request payloads, as captured in the proxy dual-logs.

INVENTORY, not a filter: every class found gets a row, however rare or small. Each class is
labelled COVERED (existing strip rule handles it), KEEP (audited + deliberately preserved),
INJECTED (text the PROXY ITSELF adds — e.g. a background-task wake-up replacement, which then
round-trips back into a LATER request's history since CC persists what was actually sent), OURS
(our own content — bash/tool output, user prompts, assistant text), or UNCLASSIFIED (CC-authored
framing/notices no rule touches and no prior audit judged).

Usage (from project root):
    ./venv/bin/python dev/cc_injection_inventory/cc_injection_inventory.py

Output: dev/cc_injection_inventory/md/<YYYYMMDD>_injection_inventory.md
"""


# ORCHESTRATOR

def inventory_workflow() -> None:
    args = _parse_args()
    log_files, excluded_files = _resolve_log_files(args.logs_glob)
    if not log_files:
        raise RuntimeError(f"No log files matched: {args.logs_glob}")

    registry: dict = {}
    pending_user_text: dict = {}
    dedup_seen: dict = {}
    file_stats = []
    counters = {"raw_segments": 0, "distinct_segments": 0, "raw_messages": 0, "distinct_messages": 0}
    msg_dedup_seen: set = set()

    for path in log_files:
        stats = _process_file(path, registry, pending_user_text, dedup_seen, counters, args.max_entries,
                               msg_dedup_seen)
        file_stats.append(stats)

    _finalize_pending_user_text(pending_user_text, registry)

    report = _build_report(registry, file_stats, counters, log_files, excluded_files)
    out_path = _write_report(report, args.out_name)
    _print_console_summary(registry, counters, out_path)


# FUNCTIONS

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=_MODULE_DESCRIPTION)
    p.add_argument("--logs-glob", default=None,
                   help=f"Glob for input files (default: <dual_log_dir>/{_DEFAULT_GLOB})")
    p.add_argument("--out-name", default=None, help="Override report filename (under md/)")
    p.add_argument("--max-entries", type=int, default=None,
                   help="Debug: cap entries processed per file")
    return p.parse_args()


def _default_log_dir() -> Path:
    local = _WORKTREE_ROOT / "src" / "logs" / "dual_log"
    if local.exists():
        return local
    fallback = _WORKTREE_ROOT.parents[2] / "src" / "logs" / "dual_log"
    if fallback.exists():
        return fallback
    raise RuntimeError(f"dual_log directory not found at {local} or {fallback}")


def _current_task_name() -> str | None:
    parent = _WORKTREE_ROOT.parent
    if parent.name == "worktrees" and parent.parent.name == ".claude":
        return _WORKTREE_ROOT.name
    return None


def _is_own_live_session_log(path: Path, task_name: str | None) -> bool:
    if task_name is None:
        return False
    return path.name.startswith(_WORKER_LOG_PREFIX) and task_name in path.name


def _resolve_log_files(logs_glob: str | None) -> tuple:
    if logs_glob:
        return sorted(Path(p) for p in globmod.glob(logs_glob)), []
    all_files = sorted(_default_log_dir().glob(_DEFAULT_GLOB))
    task_name = _current_task_name()
    included, excluded = [], []
    for f in all_files:
        (excluded if _is_own_live_session_log(f, task_name) else included).append(f)
    return included, excluded


if __name__ == "__main__":
    inventory_workflow()
