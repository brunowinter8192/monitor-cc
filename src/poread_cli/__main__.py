# INFRASTRUCTURE
import hashlib
import os
import sys

from ..constants import POREAD_MAX_BYTES, POREAD_HASH_LEN, POREAD_MARKER_PREFIX, POREAD_NOTICE

# ORCHESTRATOR

def main(argv: list) -> int:
    path = _parse_args(argv)
    if path is None:
        print("usage: poread <path>", file=sys.stderr)
        return 2
    return _emit_marker(path)

# FUNCTIONS

def _parse_args(argv: list):
    if len(argv) != 1:
        return None
    return argv[0]

def _resolve_path(path: str) -> str:
    return os.path.realpath(os.path.expanduser(path))

def _check_size(abs_path: str):
    if not os.path.isfile(abs_path):
        return None, f"poread: not a file: {abs_path}"
    try:
        size = os.path.getsize(abs_path)
    except OSError as e:
        return None, f"poread: cannot stat {abs_path}: {e}"
    if size > POREAD_MAX_BYTES:
        return None, (
            f"poread: {abs_path} is {size} bytes, over the {POREAD_MAX_BYTES}-byte poread "
            "ceiling — refusing to export; no truncated or partial export is produced"
        )
    return size, None

def _read_file(abs_path: str):
    try:
        with open(abs_path, 'rb') as f:
            return f.read(), None
    except OSError as e:
        return None, f"poread: cannot read {abs_path}: {e}"

def _emit_marker(path: str) -> int:
    abs_path = _resolve_path(path)
    _size, err = _check_size(abs_path)
    if err:
        print(err, file=sys.stderr)
        return 1
    data, err = _read_file(abs_path)
    if err:
        print(err, file=sys.stderr)
        return 1
    digest = hashlib.sha256(data).hexdigest()[:POREAD_HASH_LEN]
    print(f'{POREAD_MARKER_PREFIX}path="{abs_path}" bytes="{len(data)}" sha256="{digest}"/>')
    print(POREAD_NOTICE)
    return 0

if __name__ == "__main__":
    exit_code = 0
    try:
        exit_code = main(sys.argv[1:])
        sys.stdout.flush()
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        exit_code = 0
    sys.exit(exit_code)
