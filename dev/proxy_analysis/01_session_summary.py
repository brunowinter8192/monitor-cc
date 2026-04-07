# INFRASTRUCTURE
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

RED = "\033[31m"
YELLOW = "\033[33m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

LARGE_JUMP_THRESHOLD = 0.20


# ORCHESTRATOR

def session_summary_workflow(session_id: str | None) -> None:
    logs_dir = _find_logs_dir()
    log_file = _resolve_log_file(logs_dir, session_id)
    entries = _load_entries(log_file)
    if not entries:
        print(f"No entries found in {log_file}")
        sys.exit(1)

    _print_overview(log_file, entries)
    _print_anomalies(entries)
    _print_timeline(entries)


# FUNCTIONS

# Locate src/logs/ — checks MONITOR_CC_ROOT env, then script-relative, then cwd-relative
def _find_logs_dir() -> Path:
    if root := os.environ.get("MONITOR_CC_ROOT"):
        return Path(root) / "src" / "logs"
    script_relative = Path(__file__).parent.parent.parent / "src" / "logs"
    if script_relative.exists():
        return script_relative
    return Path.cwd() / "src" / "logs"


# Resolve log file from session_id or auto-discover most recent
def _resolve_log_file(logs_dir: Path, session_id: str | None) -> Path:
    if session_id:
        path = logs_dir / f"api_requests_{session_id}.jsonl"
        if not path.exists():
            print(f"Log file not found: {path}")
            sys.exit(1)
        return path
    candidates = sorted(
        logs_dir.glob("api_requests_*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        print(f"No proxy log files found in {logs_dir}")
        sys.exit(1)
    return candidates[0]


# Load and parse all JSONL entries from file
def _load_entries(log_file: Path) -> list:
    entries = []
    with open(log_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


# Convert UTC ISO timestamp string to local time display string
def _to_local(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%H:%M:%S")
    except ValueError:
        return ts


# Format chars count as human-readable (5c, 114k, 2.1M)
def _fmt_chars(n: int) -> str:
    if n < 1000:
        return f"{n}c"
    if n < 1_000_000:
        return f"{n / 1000:.0f}k"
    return f"{n / 1_000_000:.1f}M"


# Shorten model name for display (claude-opus-4-6 → opus-4-6)
def _short_model(model: str) -> str:
    return model.removeprefix("claude-")


# Return True if model is not an opus variant
def _is_non_opus(model: str) -> bool:
    return "opus" not in model.lower()


# Print section 1: overview
def _print_overview(log_file: Path, entries: list) -> None:
    session_id = log_file.stem.removeprefix("api_requests_")
    first_ts = _to_local(entries[0]["timestamp"])
    last_ts = _to_local(entries[-1]["timestamp"])

    model_counts: dict[str, int] = {}
    for e in entries:
        m = _short_model(e.get("model", "unknown"))
        model_counts[m] = model_counts.get(m, 0) + 1
    model_str = ", ".join(f"{m}: {c}" for m, c in sorted(model_counts.items()))

    print(f"\n{BOLD}=== Overview ==={RESET}")
    print(f"  Session ID : {session_id}")
    print(f"  Log file   : {log_file}")
    print(f"  Requests   : {len(entries)}")
    print(f"  Timespan   : {first_ts} → {last_ts}")
    print(f"  Models     : {model_str}")


# Print section 2: anomalies
def _print_anomalies(entries: list) -> None:
    print(f"\n{BOLD}=== Anomalies ==={RESET}")

    haiku_calls = []
    cache_rebuilds = []
    compression_events = []
    large_jumps = []

    prev_first_diff = None
    prev_chars = None

    for i, e in enumerate(entries):
        req_num = i + 1
        model = e.get("model", "")
        ts = _to_local(e["timestamp"])
        chars = e.get("total_input_chars", 0)
        msg_count = e.get("message_count", 0)
        diff = e.get("diff_from_prev", {})
        first_diff = diff.get("first_diff_index", -1)
        removed = diff.get("messages_removed", 0)
        modified = diff.get("messages_modified", 0)

        if _is_non_opus(model):
            haiku_calls.append((req_num, ts, model, chars, msg_count))

        if prev_first_diff is not None and first_diff >= 0 and first_diff < prev_first_diff:
            cache_rebuilds.append((req_num, ts, prev_first_diff, first_diff, removed, modified))

        if removed > 0:
            compression_events.append((req_num, ts, removed, chars))

        if prev_chars is not None and prev_chars > 0:
            change = abs(chars - prev_chars) / prev_chars
            if change > LARGE_JUMP_THRESHOLD:
                direction = "+" if chars > prev_chars else "-"
                large_jumps.append((req_num, ts, prev_chars, chars, direction, change))

        if first_diff >= 0:
            prev_first_diff = first_diff
        prev_chars = chars

    _print_anomaly_section("Non-Opus Calls", haiku_calls, _fmt_haiku)
    _print_anomaly_section("Cache Rebuilds", cache_rebuilds, _fmt_rebuild)
    _print_anomaly_section("Compression Events", compression_events, _fmt_compression)
    _print_anomaly_section("Large Input Jumps (>20%)", large_jumps, _fmt_jump)


# Print a named anomaly group with formatted lines
def _print_anomaly_section(title: str, items: list, fmt_fn) -> None:
    if not items:
        print(f"  {DIM}{title}: none{RESET}")
    else:
        print(f"  {BOLD}{title} ({len(items)}):{RESET}")
        for item in items:
            print(f"    {fmt_fn(item)}")


# Format a non-opus call anomaly line
def _fmt_haiku(item: tuple) -> str:
    req_num, ts, model, chars, msg_count = item
    return f"{RED}#{req_num:>3}  {ts}  {_short_model(model):<20}  {msg_count:>3} msgs  {_fmt_chars(chars):>6}{RESET}"


# Format a cache rebuild anomaly line
def _fmt_rebuild(item: tuple) -> str:
    req_num, ts, old_diff, new_diff, removed, modified = item
    parts = []
    if removed:
        parts.append(f"-{removed} msgs")
    if modified:
        parts.append(f"{modified} modified")
    detail = ", ".join(parts) if parts else ""
    return (
        f"{YELLOW}#{req_num:>3}  {ts}  first_diff {old_diff} → {new_diff}"
        + (f"  [{detail}]" if detail else "")
        + RESET
    )


# Format a compression event anomaly line
def _fmt_compression(item: tuple) -> str:
    req_num, ts, removed, chars = item
    return f"{YELLOW}#{req_num:>3}  {ts}  -{removed} messages removed  total: {_fmt_chars(chars)}{RESET}"


# Format a large input jump anomaly line
def _fmt_jump(item: tuple) -> str:
    req_num, ts, prev_chars, chars, direction, pct = item
    return (
        f"{YELLOW}#{req_num:>3}  {ts}  {_fmt_chars(prev_chars)} → {_fmt_chars(chars)}"
        f"  ({direction}{pct:.0%}){RESET}"
    )


# Print section 3: compact one-line-per-request timeline
def _print_timeline(entries: list) -> None:
    print(f"\n{BOLD}=== Request Timeline ==={RESET}")
    for i, e in enumerate(entries):
        req_num = i + 1
        ts = _to_local(e["timestamp"])
        model = _short_model(e.get("model", ""))
        msg_count = e.get("message_count", 0)
        chars = e.get("total_input_chars", 0)
        cache_bp = e.get("cache_breakpoints", [])
        diff = e.get("diff_from_prev", {})
        diff_summary = diff.get("summary", "")

        color = RED if _is_non_opus(e.get("model", "")) else ""
        reset = RESET if color else ""

        line = (
            f"  {color}#{req_num:<3}  {ts}  {model:<22}  {msg_count:>3} msgs"
            f"  {_fmt_chars(chars):>6}  cache:{cache_bp}  {diff_summary}{reset}"
        )
        print(line)
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Proxy log session summary")
    parser.add_argument("session_id", nargs="?", help="Session ID (auto-discovers most recent if omitted)")
    args = parser.parse_args()
    session_summary_workflow(args.session_id)
