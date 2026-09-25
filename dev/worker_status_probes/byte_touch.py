#!/usr/bin/env python3
# INFRASTRUCTURE
import sys
import os


# ORCHESTRATOR

def byte_touch_workflow():
    state_file = compute_state_file()
    bytecount_file = compute_bytecount_file()
    _init_files(state_file, bytecount_file)
    _read_loop(state_file, bytecount_file)


# FUNCTIONS

def compute_state_file():
    return sys.argv[1]


def compute_bytecount_file():
    return sys.argv[2]


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
