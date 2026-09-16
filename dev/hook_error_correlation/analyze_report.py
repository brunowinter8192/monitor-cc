# INFRASTRUCTURE
import re
from collections import defaultdict


# FUNCTIONS

def _compute_hook_stats(stufe1, stufe2, fires):
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
    return fire_hooks, unique_counts, current_counts, stale_counts, unverified_counts, all_hooks


def _build_hook_errors(stufe1):
    hook_errors = defaultdict(list)
    for e in stufe1:
        hook_errors[e["hook_name"]].append(e)
    return hook_errors


def _render_q1_section(raw_counts, unique_counts, current_counts, stale_counts, unverified_counts, fire_hooks, all_hooks, stufe2):
    lines = ["## Q1 — Zählung: historisch (Stufe 1) vs current-config (Stufe 2)", ""]
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
    return lines


def _render_join_analysis_section():
    return [
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


def _render_q2_section(all_hooks, hook_errors):
    lines = ["## Q2 — Error-Muster pro Hook (error_full)", ""]
    for h in all_hooks:
        example = hook_errors[h][0]
        ef = example["error_full"]
        msg_match = re.search(r"\.py\]: (.+)", ef, re.DOTALL)
        msg = msg_match.group(1).strip() if msg_match else ef.strip()
        lines += [f"### `{h}`", "", f"```", msg[:400], "```", ""]
    return lines


def _render_stufe1_section(all_hooks, hook_errors):
    lines = ["## Stufe 1 — Vollständige Ereignisliste (21 unique Events)", ""]
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
    return lines


def _render_stale_table(all_hooks, stale_entries):
    lines = ["### Stale (kann unter aktueller Config nicht vorkommen)", ""]
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
    return lines


def _render_unverified_list(unverified_entries):
    lines = []
    if unverified_entries:
        lines += ["### Unverified (Hook aktiv, aber Proxy-File fehlt — kein Replay möglich)", ""]
        for e in unverified_entries:
            lines.append(f"- `{e['hook_name']}` | `{e['ts'][:19]}` | proxy: `{e['proxy_file']}`")
        lines += [""]
    return lines


def _render_q3_section(all_hooks, current_entries):
    lines = []
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
    return lines


def _render_stufe2_section(all_hooks, stufe2):
    lines = ["## Stufe 2 — Reachability-Filter", ""]

    stale_entries      = [e for e in stufe2 if e["classification"].startswith("stale:")]
    current_entries    = [e for e in stufe2 if e["classification"] == "current"]
    unverified_entries = [e for e in stufe2 if e["classification"].startswith("unverified:")]

    lines += _render_stale_table(all_hooks, stale_entries)
    lines += _render_unverified_list(unverified_entries)
    lines += _render_q3_section(all_hooks, current_entries)
    return lines


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


def format_report(stufe1: list, stufe2: list, fires: list, raw_counts: dict, report_date: str) -> str:
    lines = [f"# Hook Error Correlation — {report_date}", ""]

    fire_hooks, unique_counts, current_counts, stale_counts, unverified_counts, all_hooks = _compute_hook_stats(stufe1, stufe2, fires)
    hook_errors = _build_hook_errors(stufe1)

    lines += _render_q1_section(raw_counts, unique_counts, current_counts, stale_counts, unverified_counts, fire_hooks, all_hooks, stufe2)
    lines += _render_join_analysis_section()
    lines += _render_q2_section(all_hooks, hook_errors)
    lines += _render_stufe1_section(all_hooks, hook_errors)
    lines += _render_stufe2_section(all_hooks, stufe2)

    lines.append("")
    return "\n".join(lines)
