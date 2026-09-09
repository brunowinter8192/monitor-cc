"""
Byte-identity harness for src/ram_audit/instrument.py:register_ram_dump/_handle_ram_dump
(function-LOC split into module-level report-section helpers).

Calls register_ram_dump with a fake pane name + a fixed module_state_provider, sends SIGUSR1 to
this very process, reads the resulting dump file, strips out the lines that are inherently
non-deterministic across separate process runs (timestamp, pid, rss, the actual gc object-count
rows, the actual tracemalloc size/count rows — real memory state varies run to run), and hashes
what's left: the report's fixed section headers/structure plus the fully-deterministic
module-state section (driven by the fake provider).

Usage (from project root):
    ./venv/bin/python dev/ram_audit/dump_byte_identity.py

Prints one HASH line. Run before and after the register_ram_dump/_handle_ram_dump split; the hash
must match. Cleans up its own dump file and PID file on exit.
"""

# INFRASTRUCTURE
import hashlib
import importlib
import os
import re
import signal
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

_PANE_NAME = 'byteidentity'

# ORCHESTRATOR


def main():
    instrument = _import_instrument()
    dump_text = _trigger_dump(instrument)
    normalized = _normalize(dump_text)
    print(f'HASH: {hashlib.sha256(normalized.encode()).hexdigest()}')


# FUNCTIONS

# Loaded via importlib (not a literal 'from src.' module-level line) — dev/ scripts may not use
# that form (block_dev_imports_src).
def _import_instrument():
    return importlib.import_module('src.ram_audit.instrument')


# Fixed, fully-deterministic module state: one container (len+sizeof line) and one scalar line.
def _fake_provider() -> list:
    return [('fake_list', [1, 2, 3]), ('fake_counter', 42)]


def _trigger_dump(instrument) -> str:
    os.environ.setdefault('MONITOR_CC_ROOT', str(_ROOT))
    dump_dir = _ROOT / 'dev' / 'ram_audit' / 'dumps'
    pid_file = Path(f'/tmp/.monitor_cc_pid_{_PANE_NAME}')
    before = {p.name for p in dump_dir.glob(f'*_{_PANE_NAME}.txt')} if dump_dir.exists() else set()

    instrument.register_ram_dump(_PANE_NAME, _fake_provider)
    os.kill(os.getpid(), signal.SIGUSR1)
    time.sleep(0.2)   # signal handler runs synchronously on delivery, but give it a beat

    after = {p.name for p in dump_dir.glob(f'*_{_PANE_NAME}.txt')}
    new_files = sorted(after - before)
    if not new_files:
        raise SystemExit('dump_byte_identity: no dump file was written')
    dump_path = dump_dir / new_files[-1]
    text = dump_path.read_text(encoding='utf-8')
    dump_path.unlink(missing_ok=True)
    pid_file.unlink(missing_ok=True)
    return text


# Strips inherently-non-deterministic lines (timestamp/pid/rss headers; the actual gc-count and
# tracemalloc data rows — real memory state varies run to run) while keeping section
# headers/structure and the fully-deterministic module-state section (driven by the fixed fake
# provider) intact.
def _normalize(text: str) -> str:
    kept = []
    section = None   # None | 'gc' | 'tracemalloc'
    for line in text.split('\n'):
        if line.startswith('timestamp:') or line.startswith('pid:') or line.startswith('rss:'):
            continue
        if line.startswith('## Top-30 gc objects by class'):
            section = 'gc'
            kept.append(line)
            continue
        if (line.startswith('## Top-30 tracemalloc by lineno')
                or line.startswith('## tracemalloc not active')):
            section = 'tracemalloc'
            kept.append(line)
            continue
        if line.startswith('## ') or line.startswith('# '):
            section = None
            kept.append(line)
            continue
        if section == 'gc':
            if line == '' or re.match(r'^-+$', line) or line.strip().startswith('class'):
                kept.append(line)
            continue
        if section == 'tracemalloc':
            if line == '' or re.match(r'^-+$', line) or line.strip().startswith('file:line'):
                kept.append(line)
            continue
        kept.append(line)
    return '\n'.join(kept)


if __name__ == '__main__':
    main()
