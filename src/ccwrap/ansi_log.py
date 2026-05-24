# INFRASTRUCTURE

import re
import time
from pathlib import Path

# CSI: ESC [ <param-bytes: 0x20-0x3f> <final-byte: 0x40-0x7e>
_CSI_PAT = rb'\x1b\[([\x20-\x3f]*)[\x40-\x7e]'
# OSC: ESC ] <body> (BEL or ST=ESC\)
_OSC_PAT = rb'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)'
# ESC + single char (not [ or ])
_ESC2_PAT = rb'\x1b[^\[\]]'
# Named C0 single-byte controls worth logging
_C0_PAT = rb'[\x07\x08\x0d\x0e\x0f]'

_ANSI_RE = re.compile(
    _CSI_PAT + b'|' + _OSC_PAT + b'|' + _ESC2_PAT + b'|' + _C0_PAT,
    re.DOTALL,
)

_C0_NAMES: dict = {
    b'\x07': 'BEL',
    b'\x08': 'BS',
    b'\x0d': 'CR',
    b'\x0e': 'SO',
    b'\x0f': 'SI',
}

# FUNCTIONS


# Parse all ANSI control sequences from a byte chunk; return list of (name, raw_bytes)
def parse_sequences(data: bytes) -> list:
    result = []
    for m in _ANSI_RE.finditer(data):
        raw = m.group(0)
        if raw[:2] == b'\x1b[':                    # CSI
            seq = raw[2:].decode('ascii', errors='replace')
            name = f'CSI {seq}'
        elif raw[:2] == b'\x1b]':                  # OSC
            body = raw[2:].rstrip(b'\x07\x1b\\').decode('ascii', errors='replace')
            num = body.split(';')[0] if ';' in body else body
            name = f'OSC {num}'
        elif raw[:1] == b'\x1b':                   # ESC + char
            ch = raw[1:].decode('ascii', errors='replace')
            name = f'ESC {ch}'
        else:                                       # C0
            name = _C0_NAMES.get(raw, f'0x{raw.hex()}')
        result.append((name, raw))
    return result


# Delete oldest .bin/.ansi.log pairs beyond `keep` count
def rotate_logs(log_dir: Path, keep: int = 10) -> None:
    bins = sorted(log_dir.glob('*.bin'), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in bins[keep:]:
        old.unlink(missing_ok=True)
        ansi = old.with_name(old.stem + '.ansi.log')
        ansi.unlink(missing_ok=True)


# Open a .bin and .ansi.log file pair; return (bin_fh, ansi_fh)
def open_log_pair(log_dir: Path, ts: str, pid: int):
    stem = f'{ts}-{pid}'
    bin_fh = open(log_dir / f'{stem}.bin', 'wb')
    ansi_fh = open(log_dir / f'{stem}.ansi.log', 'w', encoding='utf-8')
    return bin_fh, ansi_fh


# Write parsed sequence records to the ansi.log file
def write_sequences(ansi_fh, seqs: list) -> None:
    if not seqs:
        return
    ts = f'{time.time():.3f}'
    for name, raw in seqs:
        ansi_fh.write(f'{ts}\t{name}\t{raw.hex()}\n')
    ansi_fh.flush()
