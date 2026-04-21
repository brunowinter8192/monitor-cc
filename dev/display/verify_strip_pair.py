"""
Verify that render_messages produces len(lines) == len(keys) for entries with stripped messages.

Usage (from repo root):
    ./venv/bin/python dev/display/verify_strip_pair.py

Finds entries with non-empty stripped_msg_indices in the opus_monitor_cc log,
calls render_messages with expand_states={entry_idx: True}, and asserts exact pairing.
Exits 1 if any mismatch found.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from pathlib import Path
from src.proxy_display.parser import _parse_log_file
from src.proxy_display.render_messages import render_messages

# INFRASTRUCTURE

LOGFILE = Path('/Users/brunowinter2000/Documents/ai/Monitor_CC/src/logs/api_requests_opus_monitor_cc_1776783075.jsonl')


# ORCHESTRATOR

def verify():
    entries, _ = _parse_log_file(LOGFILE, 0)

    stripped_entries = [(i, e) for i, e in enumerate(entries) if e.get('stripped_msg_indices')]
    if not stripped_entries:
        print('SKIP: no entries with stripped_msg_indices found in log')
        sys.exit(0)

    print(f'Found {len(stripped_entries)} entries with stripped messages')

    failures = []
    for entry_idx, entry in stripped_entries:
        prev = entries[entry_idx - 1] if entry_idx > 0 else None
        expand_states = {entry_idx: True}
        lines, keys = render_messages(entry, prev, entries, expand_states, 150)
        if len(lines) != len(keys):
            failures.append((entry_idx, len(lines), len(keys), entry.get('stripped_msg_indices')))
            print(f'  FAIL entry[{entry_idx}]: lines={len(lines)} keys={len(keys)} stripped={entry.get("stripped_msg_indices")}')
        else:
            print(f'  OK   entry[{entry_idx}]: {len(lines)} lines/keys matched, stripped={entry.get("stripped_msg_indices")}')

    print()
    if failures:
        print(f'RESULT: {len(failures)} mismatch(es) found — FAIL')
        sys.exit(1)
    else:
        print(f'RESULT: OK — all {len(stripped_entries)} stripped entries have len(lines) == len(keys)')
        sys.exit(0)


if __name__ == '__main__':
    verify()
