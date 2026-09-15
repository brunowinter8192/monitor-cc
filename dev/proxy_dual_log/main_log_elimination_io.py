# INFRASTRUCTURE
import json
import os
import sys
from pathlib import Path

# FUNCTIONS

# Resolve project root from env or __file__
def _resolve_root() -> Path:
    env = os.environ.get("MONITOR_CC_ROOT")
    if env:
        return Path(env)
    return Path(__file__).parent.parent.parent


# Build all log file paths for the session
def _resolve_paths(root: Path, session: str) -> dict:
    logs = root / "src" / "logs"
    dual = logs / "dual_log"
    return {
        "main": logs / f"api_requests_{session}.jsonl",
        "orig": dual / f"api_requests_{session}_original.jsonl",
        "fwd": dual / f"api_requests_{session}_forwarded.jsonl",
        "stripped": dual / f"api_requests_{session}_stripped.jsonl",
        "injected": dual / f"api_requests_{session}_injected.jsonl",
        "tool_errors": logs / "tool_errors.jsonl",
    }


# Fail-fast if any required log file is missing
def _check_paths(paths: dict) -> None:
    for key in ("main", "orig", "fwd"):
        p = paths[key]
        if not p.exists():
            print(f"ERROR: {key} log not found: {p}", file=sys.stderr)
            sys.exit(1)


# Load JSONL, skip blank lines and bad JSON
def _load_jsonl(path: Path) -> list:
    entries = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"  [warn] {path.name}:{lineno} — {e}", file=sys.stderr)
    return entries


# Load main log — return only request entries (no type field), preserving order
def _load_main_log(path: Path) -> list:
    all_entries = _load_jsonl(path)
    return [e for e in all_entries if "type" not in e]


# Load tool_errors.jsonl — filter by proxy_file containing session suffix
def _load_tool_errors(path: Path, session: str) -> list:
    if not path.exists():
        return []
    all_records = _load_jsonl(path)
    return [r for r in all_records if session in r.get("proxy_file", "")]
