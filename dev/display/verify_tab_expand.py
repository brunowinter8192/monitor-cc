"""
Verify that tab expansion fix eliminates terminal-wrap in render_messages output.

Usage (from repo root):
    ./venv/bin/python dev/display/verify_tab_expand.py

Loads entry 17 from the opus_monitor_cc log, renders it expanded, and counts
lines whose real terminal cell width exceeds pane_width=150. Exits 1 if any found.
"""
import re
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from pathlib import Path
from src.proxy_display.parser import _parse_log_file
from src.proxy_display.render_messages import render_messages
from src.utils import _cell_width, truncate_visible

# INFRASTRUCTURE

LOGFILE = Path('/Users/brunowinter2000/Documents/ai/Monitor_CC/src/logs/api_requests_opus_monitor_cc_1776783075.jsonl')
PANE_WIDTH = 150
ENTRY_IDX = 17
ANSI = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')


# Real terminal cell count accounting for tab expansion at tab stops
def real_cells(s, tab_size=8):
    s = ANSI.sub('', s)
    out = 0
    for ch in s:
        if ch == '\t':
            out += tab_size - (out % tab_size)
        else:
            out += _cell_width(ch)
    return out


# ORCHESTRATOR

def verify():
    entries, _ = _parse_log_file(LOGFILE, 0)
    if len(entries) <= ENTRY_IDX:
        print(f'FAIL: only {len(entries)} entries, need at least {ENTRY_IDX + 1}')
        sys.exit(1)

    entry = entries[ENTRY_IDX]
    prev_entry = entries[ENTRY_IDX - 1] if ENTRY_IDX > 0 else None
    expand_states = {ENTRY_IDX: True}

    lines, _ = render_messages(entry, prev_entry, entries, expand_states, PANE_WIDTH)

    # Apply truncate_visible as format.py does before checking for over-wide lines
    overwide = []
    for i, line in enumerate(lines):
        trunc = truncate_visible(line, PANE_WIDTH)
        rc = real_cells(trunc)
        if rc > PANE_WIDTH:
            overwide.append((i, rc, trunc[:80]))

    print(f'Rendered {len(lines)} lines from entry {ENTRY_IDX} at pane_width={PANE_WIDTH}')
    print(f'Over-wide lines (real_cells > {PANE_WIDTH}): {len(overwide)}')

    if overwide:
        for i, rc, preview in overwide[:10]:
            print(f'  line[{i}] real_cells={rc}: {repr(preview)}')
        sys.exit(1)
    else:
        print('OK — no over-wide lines found')
        sys.exit(0)


if __name__ == '__main__':
    verify()
