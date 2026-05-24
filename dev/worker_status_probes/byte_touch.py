#!/usr/bin/env python3
"""Stdin byte counter helper for probe_b pipe-pane.

Usage (invoked by tmux pipe-pane, not directly):
    python3 byte_touch.py <state_file> <bytecount_file>

On every non-empty stdin read: touches state_file mtime, overwrites bytecount_file
with cumulative byte total. probe_b.py polls both files every 1s.
"""

# INFRASTRUCTURE
import sys
import os

# ORCHESTRATOR


def byte_touch_workflow():
    state_file = sys.argv[1]
    bytecount_file = sys.argv[2]
    _init_files(state_file, bytecount_file)
    _read_loop(state_file, bytecount_file)


# FUNCTIONS


def _init_files(state_file, bytecount_file):
    open(state_file, "a").close()
    with open(bytecount_file, "w") as f:
        f.write("0\n")


def _read_loop(state_file, bytecount_file):
    total = 0
    fd = sys.stdin.fileno()
    while True:
        try:
            chunk = os.read(fd, 4096)
        except OSError:
            break
        if not chunk:
            break
        os.utime(state_file, None)
        total += len(chunk)
        with open(bytecount_file, "w") as f:
            f.write(f"{total}\n")


if __name__ == "__main__":
    byte_touch_workflow()
