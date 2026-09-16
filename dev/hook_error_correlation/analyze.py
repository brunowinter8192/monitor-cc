# INFRASTRUCTURE
import json
import os
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timezone

from analyze_report import format_report

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
MAIN_PROJECT = None  # resolved below by _resolve_main_project()
REPORT_DATE  = datetime.now(timezone.utc).strftime("%Y-%m-%d")

_HOOK_PATH_RE   = re.compile(r"src/hooks/(\w+)\.py")
_HOOK_SIGNAL_RE = re.compile(r"PreToolUse:\w+ hook error:")


# Resolve MAIN_PROJECT at import time via .git file traversal
def _resolve_main_project() -> str:
    p = SCRIPT_DIR
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


MAIN_PROJECT = _resolve_main_project()
HOOKS_DIR    = os.path.join(MAIN_PROJECT, "src", "hooks")
LOGS_DIR     = os.path.join(MAIN_PROJECT, "src", "logs")
REPORTS_DIR  = os.path.join(SCRIPT_DIR, "reports")
LOG_FIRES    = os.path.join(LOGS_DIR, "hook_firing.jsonl")
LOG_ERRORS   = os.path.join(LOGS_DIR, "tool_errors.jsonl")


# ORCHESTRATOR

# Load logs, overlay via proxy lookup, replay active hooks, write report
def analyze_workflow() -> None:
    raw_counts = load_raw_counts(LOG_ERRORS)
    errors     = load_hook_errors(LOG_ERRORS)
    fires      = load_fires(LOG_FIRES)
    stufe1     = build_stufe1(errors)
    stufe2     = build_stufe2(stufe1)
    report     = format_report(stufe1, stufe2, fires, raw_counts, REPORT_DATE)
    path       = write_report(report, REPORTS_DIR, REPORT_DATE)
    print(path)


# FUNCTIONS

# Count all (non-deduplicated) hook errors per hook name
def load_raw_counts(path: str) -> dict:
    counts = defaultdict(int)
    with open(path) as f:
        for line in f:
            e = json.loads(line)
            ef = e.get("error_full", "")
            if _HOOK_SIGNAL_RE.search(ef) and _HOOK_PATH_RE.search(ef):
                counts[_HOOK_PATH_RE.search(ef).group(1)] += 1
    return dict(counts)


# Load unique hook errors; return list enriched with hook_name + hook_status
def load_hook_errors(path: str) -> list:
    errors, seen = [], set()
    with open(path) as f:
        for line in f:
            e = json.loads(line)
            ef = e.get("error_full", "")
            if not (_HOOK_SIGNAL_RE.search(ef) and _HOOK_PATH_RE.search(ef)):
                continue
            e["hook_name"] = _HOOK_PATH_RE.search(ef).group(1)
            key = (e["hook_name"], e["tool_use_id"])
            if key in seen:
                continue
            seen.add(key)
            e["hook_status"] = classify_hook_status(e["hook_name"])
            errors.append(e)
    return errors


# Load fire log entries
def load_fires(path: str) -> list:
    with open(path) as f:
        return [json.loads(l) for l in f]


# Return status dict for a hook: active / disabled / removed
def classify_hook_status(hook_name: str) -> dict:
    py       = os.path.join(HOOKS_DIR, f"{hook_name}.py")
    disabled = os.path.join(HOOKS_DIR, f"{hook_name}.py.disabled")
    if os.path.exists(py):
        return {"status": "active", "stale_reason": None}
    if os.path.exists(disabled):
        return {"status": "disabled", "stale_reason": "block→disabled (.py.disabled exists; replaced by rewrite)"}
    return {"status": "removed", "stale_reason": "removed (file gone; errors show can't-open-file)"}


# Enrich each error with exact tool_input from proxy; return list with added fields
def build_stufe1(errors: list) -> list:
    result = []
    for e in errors:
        tool_input, lookup_status = lookup_command(
            e["proxy_file"], e["tool_use_id"], e["tool_name"]
        )
        e = dict(e)
        e["tool_input"]     = tool_input
        e["lookup_status"]  = lookup_status
        result.append(e)
    return result


# Locate tool_use_id in proxy JSONL raw_payload.messages; return (input_dict, status_str)
def lookup_command(proxy_file: str, tool_use_id: str, tool_name: str):
    proxy_path = os.path.join(LOGS_DIR, proxy_file)
    if not os.path.exists(proxy_path):
        return None, "proxy_missing"
    with open(proxy_path) as f:
        for line in f:
            if tool_use_id not in line:
                continue
            entry = json.loads(line)
            raw = entry.get("raw_payload", {})
            for msg in raw.get("messages", []):
                if msg.get("role") != "assistant":
                    continue
                for block in (msg.get("content") or []):
                    if isinstance(block, dict) and block.get("id") == tool_use_id:
                        return block.get("input", {}), "proxy-exact"
    return None, "not_found"


# Classify active hook errors via replay; return Stufe2 entries
def build_stufe2(stufe1: list) -> list:
    result = []
    for e in stufe1:
        hook     = e["hook_name"]
        status   = e["hook_status"]["status"]
        if status != "active":
            result.append({**e, "replay_exit": None, "classification": f"stale:{e['hook_status']['stale_reason']}"})
            continue
        if e["tool_input"] is None:
            # Hook is active but proxy file missing → can't verify; treat as unverified not stale
            result.append({**e, "replay_exit": None, "classification": "unverified:proxy_missing"})
            continue
        payload  = build_replay_payload(e["tool_name"], e["tool_input"])
        exit_code = replay_hook(hook, payload)
        cls       = "current" if exit_code == 2 else (
                    "stale:pattern-narrowed" if exit_code == 0 else f"stale:hook-error-{exit_code}"
        )
        result.append({**e, "replay_exit": exit_code, "classification": cls})
    return result


# Build stdin payload JSON for hook subprocess
def build_replay_payload(tool_name: str, tool_input: dict) -> str:
    return json.dumps({"tool_name": tool_name, "tool_input": tool_input, "session_id": "replay"})


# Run hook subprocess with cwd=MAIN_PROJECT; return exit code
def replay_hook(hook_name: str, payload: str) -> int:
    hook_path = os.path.join(MAIN_PROJECT, "src", "hooks", f"{hook_name}.py")
    r = subprocess.run(
        ["python3", hook_path],
        input=payload.encode(),
        capture_output=True,
        cwd=MAIN_PROJECT,
    )
    return r.returncode


# Write report to file; return path
def write_report(report: str, reports_dir: str, date: str) -> str:
    os.makedirs(reports_dir, exist_ok=True)
    path = os.path.join(reports_dir, f"{date}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    return path


if __name__ == "__main__":
    analyze_workflow()
