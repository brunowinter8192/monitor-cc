#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from proxy.tool_error_log import (
    LOG_FILE,
    _build_tu_id_map, _get_block_text, _extract_error_summary,
    _extract_exit_code, _get_command_preview,
    read_all, read_today, write,
)


# ORCHESTRATOR

def main():
    parser = argparse.ArgumentParser(prog='cc-errors', description='Query/scan tool_use_error log')
    parser.add_argument('--today', action='store_true', help='filter to today (default behavior)')
    parser.add_argument('--verbose', action='store_true', help='per-entry listing (use with --today)')
    parser.add_argument('--by', choices=['tool', 'project', 'summary'],
                        help='group ALL errors by field with counts')
    parser.add_argument('--scan-history', action='store_true', dest='scan_history',
                        help='scan all proxy JSONLs and backfill global log')
    parser.add_argument('subcommand', nargs='?', choices=['backfill'],
                        help='alias for --scan-history')
    args = parser.parse_args()

    if args.scan_history or args.subcommand == 'backfill':
        cmd_scan_history()
    elif args.by:
        cmd_by(args.by)
    elif args.today and args.verbose:
        cmd_today_verbose()
    else:
        cmd_default()


# FUNCTIONS

# Default: today's error count grouped by tool_name + first-3-words-of-summary
def cmd_default():
    entries = read_today()
    if not entries:
        print("Today's errors: 0")
        return
    groups = Counter()
    for e in entries:
        key = (e.get("tool_name", "?"), _first_3_words(e.get("error_summary", "")))
        groups[key] += 1
    print(f"Today's errors: {len(entries)}")
    for (tool, summary_key), count in groups.most_common():
        print(f"  {tool} · \"{summary_key}\" — {count}")


# --today --verbose: per-entry listing with timestamp, tool, project/worker, summary
def cmd_today_verbose():
    entries = read_today()
    if not entries:
        print("Today's errors: 0")
        return
    print(f"Today's errors: {len(entries)}")
    for e in entries:
        ts = e.get("ts", "")
        hms = ts[11:19] if len(ts) >= 19 else ts
        tool = e.get("tool_name", "?")
        project = Path(e.get("project", "?")).name
        worker = e.get("worker")
        proj_str = f"{project}/{worker}" if worker else project
        summary = (e.get("error_summary") or "")[:80]
        print(f"  {hms}  {tool:<8}  {proj_str:<30}  {summary}")


# --by tool|project|summary: group ALL logged errors by field with counts
def cmd_by(field: str):
    entries = read_all()
    if not entries:
        print("No errors logged.")
        return
    groups = Counter()
    for e in entries:
        if field == "tool":
            key = e.get("tool_name", "?")
        elif field == "project":
            key = Path(e.get("project", "?")).name
        else:  # summary
            key = _first_3_words(e.get("error_summary", ""))
        groups[key] += 1
    print(f"All errors: {len(entries)} — grouped by {field}")
    for key, count in groups.most_common():
        print(f"  {count:4d}  {key}")


# --scan-history / backfill: scan all api_requests_*.jsonl, extract errors, append unique entries
def cmd_scan_history():
    logs_dir = LOG_FILE.parent
    files = sorted(logs_dir.glob("api_requests_*.jsonl"))
    if not files:
        print(f"No api_requests_*.jsonl files found in {logs_dir}")
        return
    project = str(logs_dir.parent.parent)  # src/logs/ → src/ → Monitor_CC root

    # Pre-load existing entries for dedup
    existing = read_all()
    seen: set[tuple] = {
        (e.get("ts", ""), e.get("session_id", ""),
         e.get("tool_name", ""), (e.get("error_summary") or "")[:80])
        for e in existing
    }

    total_files = len(files)
    extracted = 0
    written = 0

    for file_idx, path in enumerate(files, 1):
        size_mb = path.stat().st_size / (1024 * 1024)
        print(f"Scanning file {file_idx:2d}/{total_files}: {path.name} ({size_mb:.0f}MB)", flush=True)

        # Derive session_id and worker from filename
        # api_requests_{log_id}.jsonl — log_id is e.g. "opus_monitor_cc_1746820038"
        # or "worker_abc12345_myworker_1746820100"
        stem = path.stem
        log_id = stem[len("api_requests_"):]
        worker = None
        if log_id.startswith("worker_"):
            parts = log_id.split("_")
            # format: worker_{8char_session_id}_{name_parts...}_{epoch}
            worker = "_".join(parts[2:-1]) if len(parts) >= 4 else None

        try:
            with open(path, "rb") as fh:
                for raw in fh:
                    # Byte pre-scan: skip lines without error markers (avoids JSON parsing ~67% of lines)
                    if (b'"is_error": true' not in raw
                            and b'"is_error":true' not in raw
                            and b'<tool_use_error>' not in raw):
                        continue
                    try:
                        entry = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    # Skip non-REQ entries (latency_update, sent_meta, schema_warning)
                    if entry.get("type"):
                        continue
                    raw_payload = entry.get("raw_payload")
                    if not raw_payload:
                        continue
                    messages = raw_payload.get("messages", [])
                    if not messages:
                        continue

                    # first_diff_index slicing: process only messages new in this REQ.
                    # Prevents re-extracting the same error from every subsequent REQ
                    # that carries it in its cumulative message history.
                    diff = entry.get("diff_from_prev") or {}
                    first_diff = diff.get("first_diff_index", 0)
                    if first_diff < 0:
                        continue
                    new_messages = messages[first_diff:]
                    ts = entry.get("timestamp", "")

                    # Build id-map from ALL messages (tool_use may precede first_diff)
                    tu_map = _build_tu_id_map(messages)

                    for msg in new_messages:
                        if msg.get("role") != "user":
                            continue
                        content = msg.get("content", [])
                        if not isinstance(content, list):
                            continue
                        for blk in content:
                            if blk.get("type") != "tool_result":
                                continue
                            is_err = blk.get("is_error", False)
                            text = _get_block_text(blk)
                            has_tag = "<tool_use_error>" in text
                            if not is_err and not has_tag:
                                continue
                            tool_use_id = blk.get("tool_use_id", "")
                            tool_name, tool_input = tu_map.get(tool_use_id, ("?", {}))
                            command_preview = _get_command_preview(tool_input)
                            error_summary = _extract_error_summary(text)
                            exit_code = _extract_exit_code(text) if tool_name == "Bash" else None
                            extracted += 1
                            dedup_key = (ts, log_id, tool_name, error_summary[:80])
                            if dedup_key in seen:
                                continue
                            seen.add(dedup_key)
                            write(ts, log_id, project, worker, tool_name,
                                  command_preview, error_summary, exit_code)
                            written += 1
        except (IOError, OSError) as exc:
            print(f"  [skip] {path.name}: {exc}", file=sys.stderr)

    skipped = extracted - written
    print(f"Done. Scanned {total_files} files, extracted {extracted} errors, "
          f"{written} new (deduplicated {skipped} existing)")


# First 3 words of a string joined by space — used as summary group key
def _first_3_words(text: str) -> str:
    return " ".join(text.split()[:3])


if __name__ == "__main__":
    main()
