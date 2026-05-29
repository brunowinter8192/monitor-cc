# INFRASTRUCTURE
import json
import os
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timezone

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
    report     = format_report(stufe1, stufe2, fires, raw_counts)
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


# Format markdown report answering Q1/Q2/Q3 + join analysis
def format_report(stufe1: list, stufe2: list, fires: list, raw_counts: dict) -> str:
    lines = [f"# Hook Error Correlation — {REPORT_DATE}", ""]

    # --- Q1: summary table ---
    lines += ["## Q1 — Zählung: historisch (Stufe 1) vs current-config (Stufe 2)", ""]
    fire_hooks = defaultdict(int)
    for f in fires:
        fire_hooks[f["hook"]] += 1

    unique_counts = defaultdict(int)
    for e in stufe1:
        unique_counts[e["hook_name"]] += 1

    current_counts    = defaultdict(int)
    stale_counts      = defaultdict(int)
    unverified_counts = defaultdict(int)
    for e in stufe2:
        h = e["hook_name"]
        cls = e["classification"]
        if cls == "current":
            current_counts[h] += 1
        elif cls.startswith("unverified:"):
            unverified_counts[h] += 1
        else:
            stale_counts[h] += 1

    all_hooks = sorted(set(e["hook_name"] for e in stufe1),
                       key=lambda h: -unique_counts[h])

    lines.append("| Hook | Raw | Unique | Current | Stale | Unverified | Fire-Log |")
    lines.append("|------|-----|--------|---------|-------|------------|----------|")
    for h in all_hooks:
        stale_detail = ", ".join(sorted(set(
            e["classification"].replace("stale:", "")
            for e in stufe2 if e["hook_name"] == h and e["classification"].startswith("stale:")
        ))) or "—"
        lines.append(
            f"| `{h}` | {raw_counts.get(h, 0)} | {unique_counts[h]} "
            f"| {current_counts[h]} | {stale_counts[h]} ({stale_detail})"
            f" | {unverified_counts[h]} | {fire_hooks.get(h, 0)} |"
        )

    totals = (sum(raw_counts.values()), sum(unique_counts.values()),
              sum(current_counts.values()), sum(stale_counts.values()), sum(unverified_counts.values()))
    lines.append(f"| **Total** | **{totals[0]}** | **{totals[1]}** | **{totals[2]}** | **{totals[3]}** | **{totals[4]}** | |")
    lines += [""]

    # --- Join analysis ---
    lines += [
        "## Join-Analyse: warum kein Session-Match",
        "",
        "Alle 59 rohen Errors stammen aus zwei Sessions; keine davon taucht im fire_log auf:",
        "",
        "| Session (8-char) | Proxy-Pattern | Grund |",
        "|------------------|--------------|-------|",
        "| `f93afc17` | `api_requests_opus_monitor_cc_*` / `worker_f93afc17_*` | **Vor fire_log**: Errors datieren von 2026-05-24 vor dem `_fire_log.py`-Commit; die Hooks hatten noch keinen `log_fire()`-Call. |",
        "| `8e6b2517` | `api_requests_opus_rag_*` | **Anderes Projekt**: RAG-Session nutzt global registrierte Monitor_CC-Hooks; fire_log ist Monitor_CC-spezifisch. |",
        "",
        "**Command-Quelle**: statt Fire-Log-Join → `proxy_file + tool_use_id` → `raw_payload.messages[assistant][id=tuid].input`.",
        f"17/21 unique Events proxy-verfügbar; 4 fehlen (proxy-Dateien gelöscht: `audit-logging` + `cleanup-deploy` Worker-Logs).",
        "",
    ]

    # --- Q2: error text examples per hook ---
    lines += ["## Q2 — Error-Muster pro Hook (error_full)", ""]
    hook_errors = defaultdict(list)
    for e in stufe1:
        hook_errors[e["hook_name"]].append(e)

    for h in all_hooks:
        example = hook_errors[h][0]
        ef = example["error_full"]
        # Extract the message after the hook path
        msg_match = re.search(r"\.py\]: (.+)", ef, re.DOTALL)
        msg = msg_match.group(1).strip() if msg_match else ef.strip()
        lines += [f"### `{h}`", "", f"```", msg[:400], "```", ""]

    # --- Stufe 1 full list ---
    lines += ["## Stufe 1 — Vollständige Ereignisliste (21 unique Events)", ""]
    for h in all_hooks:
        entries = hook_errors[h]
        hook_s  = entries[0]["hook_status"]
        lines.append(f"### `{h}` ({len(entries)} Events — status: {hook_s['status']})")
        if hook_s["stale_reason"]:
            lines.append(f"> Stale: {hook_s['stale_reason']}")
        lines.append("")
        for e in entries:
            cmd = _fmt_cmd(e["tool_name"], e.get("tool_input"))
            lines.append(f"- `{e['ts'][:19]}` | `{e['tool_name']}` | session={e['session_id']} | lookup={e['lookup_status']}")
            lines.append(f"  - **Command**: `{cmd}`")
        lines.append("")

    # --- Stufe 2 ---
    lines += ["## Stufe 2 — Reachability-Filter", ""]

    stale_entries      = [e for e in stufe2 if e["classification"].startswith("stale:")]
    current_entries    = [e for e in stufe2 if e["classification"] == "current"]
    unverified_entries = [e for e in stufe2 if e["classification"].startswith("unverified:")]

    lines += ["### Stale (kann unter aktueller Config nicht vorkommen)", ""]
    stale_by_hook = defaultdict(list)
    for e in stale_entries:
        stale_by_hook[e["hook_name"]].append(e)
    lines.append("| Hook | Unique Events | Mechanismus |")
    lines.append("|------|--------------|-------------|")
    for h in all_hooks:
        if h in stale_by_hook:
            reason = stale_by_hook[h][0]["classification"].replace("stale:", "")
            lines.append(f"| `{h}` | {len(stale_by_hook[h])} | {reason} |")
    lines += [""]

    if unverified_entries:
        lines += ["### Unverified (Hook aktiv, aber Proxy-File fehlt — kein Replay möglich)", ""]
        for e in unverified_entries:
            lines.append(f"- `{e['hook_name']}` | `{e['ts'][:19]}` | proxy: `{e['proxy_file']}`")
        lines += [""]

    lines += ["### Q3 — Current-Config-Relevant (Grundlage legit/FP-Beurteilung)", ""]
    if not current_entries:
        lines.append("_(keine current-config-relevanten Einträge nach Replay)_")
    else:
        cur_by_hook = defaultdict(list)
        for e in current_entries:
            cur_by_hook[e["hook_name"]].append(e)
        for h in all_hooks:
            if h not in cur_by_hook:
                continue
            lines.append(f"#### `{h}` ({len(cur_by_hook[h])} Events)")
            for e in cur_by_hook[h]:
                cmd = _fmt_cmd(e["tool_name"], e.get("tool_input"))
                ef  = e["error_full"]
                msg_m = re.search(r"\.py\]: (.+)", ef, re.DOTALL)
                msg = (msg_m.group(1).strip() if msg_m else ef.strip())[:200]
                lines.append(f"")
                lines.append(f"**{e['ts'][:19]}** | session `{e['session_id']}` | tool `{e['tool_name']}`")
                lines.append(f"- Command: `{cmd}`")
                lines.append(f"- Error: {msg[:200]}")
            lines.append("")

    lines.append("")
    return "\n".join(lines)


# Format a command for display: truncate to 120 chars
def _fmt_cmd(tool_name: str, tool_input) -> str:
    if tool_input is None:
        return "(unavailable)"
    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        return cmd[:120].replace("`", "'") + ("…" if len(cmd) > 120 else "")
    if tool_name in ("Write", "Edit"):
        fp   = tool_input.get("file_path", "?")
        key  = "content" if tool_name == "Write" else "new_string"
        size = len(tool_input.get(key, ""))
        return f"{fp} ({size} chars)"
    if tool_name == "Read":
        return tool_input.get("file_path", "?")
    return str(tool_input)[:80]


# Write report to file; return path
def write_report(report: str, reports_dir: str, date: str) -> str:
    os.makedirs(reports_dir, exist_ok=True)
    path = os.path.join(reports_dir, f"{date}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    return path


if __name__ == "__main__":
    analyze_workflow()
