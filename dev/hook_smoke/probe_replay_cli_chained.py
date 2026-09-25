# INFRASTRUCTURE
import json
import os
import subprocess
import sys

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__)).replace("dev/hook_smoke", "src/hooks")
_NEW_HOOK = os.path.join(_HOOKS_DIR, "block_cli_chained.py")
_WORKTREE_FRAGMENT = ".claude/worktrees/"
_REPORT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "md",
                            "block_cli_chained_replay_report.md")

_OLD_HOOKS = [
    "block_gh_cli_chained",
    "block_rag_cli_chained",
    "block_worker_cli_read_chained",
    "block_websearch_scrape_chained",
    "block_duallog_chained",
    "block_linkedin_cli_isolated",
    "block_penny_cli_chained",
]


# ORCHESTRATOR

def probe_replay_cli_chained_workflow() -> None:
    log_path = _resolve_main_log_path()
    records = _load_block_records(log_path, _OLD_HOOKS)
    results = compute_results()
    process_records(records, results)

    total_block = compute_total_block(results)
    total_pass = compute_total_pass(results)
    print(f"Replayed {len(records)} historical block fires from {log_path}")
    print_old_hooks(results)
    print(f"TOTAL: {total_block} still block, {total_pass} now pass")

    _write_report(log_path, results, total_block, total_pass)
    print(f"Report: {_REPORT_PATH}")


# FUNCTIONS

def _resolve_main_log_path() -> str:
    here = os.path.abspath(__file__)
    idx = here.find(_WORKTREE_FRAGMENT)
    if idx == -1:
        main_root = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    else:
        main_root = here[:idx].rstrip("/")
    return os.path.join(main_root, "src", "logs", "hook_firing.jsonl")


def _load_block_records(log_path: str, old_hooks: list) -> list:
    records = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if entry.get("decision") == "block" and entry.get("hook") in old_hooks:
                records.append((entry["hook"], entry.get("command", "")))
    return records


def compute_results():
    return {hook: {"block": [], "pass": []} for hook in _OLD_HOOKS}


def process_records(records, results):
    for hook, command in records:
        exit_code = _replay(command)
        bucket = "block" if exit_code == 2 else "pass"
        results[hook][bucket].append(command)


def _replay(command: str) -> int:
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    result = subprocess.run(
        ["python3", _NEW_HOOK],
        input=payload.encode("utf-8"),
        capture_output=True,
    )
    return result.returncode


def compute_total_block(results):
    return sum(len(r["block"]) for r in results.values())


def compute_total_pass(results):
    return sum(len(r["pass"]) for r in results.values())


def print_old_hooks(results):
    for hook in _OLD_HOOKS:
        r = results[hook]
        print(f"  {hook}: {len(r['block'])} still block, {len(r['pass'])} now pass")


def _write_report(log_path: str, results: dict, total_block: int, total_pass: int) -> None:
    os.makedirs(os.path.dirname(_REPORT_PATH), exist_ok=True)
    lines = [
        "# block_cli_chained.py replay report",
        "",
        f"Source log: `{log_path}`",
        "",
        f"Total: {total_block} still block, {total_pass} now pass "
        f"(of {total_block + total_pass} historical block fires from the 7 replaced hooks).",
        "",
        "## Per-hook counts",
        "",
        "| old hook | still block | now pass |",
        "|---|---|---|",
    ]
    for hook in _OLD_HOOKS:
        r = results[hook]
        lines.append(f"| {hook} | {len(r['block'])} | {len(r['pass'])} |")
    lines.append("")
    lines.append("## Now-passing commands (previously blocked, non-truncating)")
    lines.append("")
    for hook in _OLD_HOOKS:
        passing = results[hook]["pass"]
        if not passing:
            continue
        lines.append(f"### {hook} ({len(passing)})")
        lines.append("")
        for cmd in passing:
            lines.append("```")
            lines.append(cmd)
            lines.append("```")
            lines.append("")
    with open(_REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    probe_replay_cli_chained_workflow()
