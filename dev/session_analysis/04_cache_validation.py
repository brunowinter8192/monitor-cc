#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import json
import sys
from pathlib import Path

_MODULE_DOCSTRING = """Validate proxy cache breakpoint placement and stability.

Reads a proxy JSONL log and shows per-request:
- Our breakpoint positions (system, tools, messages)
- Which messages were modified by proxy rules
- Whether breakpoints are stable between consecutive requests
- Comparison with original CC breakpoints

Usage:
    python3 dev/session_analysis/04_cache_validation.py <proxy_log.jsonl> [--limit N]
"""


# ORCHESTRATOR

def main():
    parser = argparse.ArgumentParser(description=_MODULE_DOCSTRING, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("log_file", help="Path to proxy JSONL log file")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of requests to show (0=all)")
    parser.add_argument("--rebuilds-only", action="store_true", help="Only show requests with mods before breakpoint")
    args = parser.parse_args()

    log_path = Path(args.log_file)
    if not log_path.exists():
        print_error(log_path)
        sys.exit(1)

    entries = _load_entries(log_path)

    print_requests_with_messages(entries)
    print()
    print_msgs()
    print_output()

    total_at_risk = _print_request_rows(entries, args.limit, args.rebuilds_only)

    print()
    print_total_requests(entries)
    print_at_risk_mods(total_at_risk, entries)


# FUNCTIONS

def print_error(log_path):
    print(f"Error: {log_path} not found", file=sys.stderr)


def _load_entries(log_path: Path) -> list:
    entries = []
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            raw = entry.get("raw_payload", {})
            if raw.get("messages"):
                entries.append(entry)
    return entries


def print_requests_with_messages(entries):
    print(f"Requests with messages: {len(entries)}")


def print_msgs():
    print(f"{'#':>4} {'msgs':>4} {'tools':>3} {'mods':>3} {'CC BPs':>30}  {'mods_before_bp':>20}  {'flag':>10}")


def print_output():
    print("-" * 100)


def _print_request_rows(entries: list, limit: int, rebuilds_only: bool) -> int:
    prev = None
    shown = 0
    total_at_risk = 0
    for i, entry in enumerate(entries):
        result = analyze_request(entry, prev)
        prev = entry

        if rebuilds_only and not result["mods_before_bp"]:
            if result["mods_before_bp"]:
                total_at_risk += 1
            continue

        if result["mods_before_bp"]:
            total_at_risk += 1

        flag = ""
        if result["mods_before_bp"]:
            flag = "AT RISK"

        bp_str = ", ".join(result["cc_breakpoints"])
        mod_bp_str = str(result["mods_before_bp"]) if result["mods_before_bp"] else "-"

        print(
            f"{i:>4} {result['msg_count']:>4} {result['tool_count']:>3} "
            f"{len(result['modifications']):>3} {bp_str:>30}  {mod_bp_str:>20}  {flag:>10}"
        )

        shown += 1
        if limit and shown >= limit:
            break
    return total_at_risk


def analyze_request(entry: dict, prev_entry: dict | None) -> dict:
    raw = entry.get("raw_payload", {})
    messages = raw.get("messages", [])
    system = raw.get("system", [])
    tools = raw.get("tools", [])
    mods = entry.get("modifications", [])

    cc_bps = _find_cc_breakpoints(system, tools, messages)
    mod_indices = _find_modifiable_indices(messages)

    last_msg_bp = None
    for bp in cc_bps:
        if bp.startswith("m["):
            idx = int(bp.split("[")[1].split("]")[0])
            last_msg_bp = idx

    mods_before_bp = [i for i in mod_indices if last_msg_bp and i < last_msg_bp]

    return {
        "msg_count": len(messages),
        "tool_count": len(tools),
        "cc_breakpoints": cc_bps,
        "modifications": mods,
        "mod_indices": mod_indices,
        "mods_before_bp": mods_before_bp,
        "last_msg_bp": last_msg_bp,
        "timestamp": entry.get("timestamp", ""),
    }


def _find_cc_breakpoints(system: list, tools: list, messages: list) -> list:
    cc_bps = []
    for i, b in enumerate(system):
        if isinstance(b, dict) and b.get("cache_control"):
            cc_bps.append(f"sys[{i}]")
    for i, t in enumerate(tools):
        if isinstance(t, dict) and t.get("cache_control"):
            cc_bps.append(f"t[{i}]")
    for i, m in enumerate(messages):
        if m.get("cache_control"):
            cc_bps.append(f"m[{i}]top")
        content = m.get("content", "")
        if isinstance(content, list):
            for j, b in enumerate(content):
                if isinstance(b, dict) and b.get("cache_control"):
                    cc_bps.append(f"m[{i}]")
    return cc_bps


def _find_modifiable_indices(messages: list) -> list:
    mod_indices = []
    for i, m in enumerate(messages):
        if m.get("role") != "user":
            continue
        content = m.get("content", "")
        text = ""
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
        if "Plan mode is active" in text or "task tools haven" in text or "<task-notification>" in text:
            mod_indices.append(i)
    return mod_indices


def print_total_requests(entries):
    print(f"Total requests: {len(entries)}")


def print_at_risk_mods(total_at_risk, entries):
    print(f"At risk (mods before BP): {total_at_risk} ({total_at_risk/len(entries)*100:.1f}%)" if entries else "")


if __name__ == "__main__":
    main()
