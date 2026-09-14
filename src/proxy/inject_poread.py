import hashlib
import os
import re
import sys
from pathlib import Path

from .payload_helpers import _walk_replace_marker_blocks

_src_dir = os.path.join(os.environ.get("MONITOR_CC_ROOT", str(Path(__file__).parent.parent.parent)), "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)
from constants import POREAD_MAX_BYTES, POREAD_HASH_LEN, POREAD_MARKER_PREFIX

# INFRASTRUCTURE

_POREAD_HEADER_PREFIX = '--- poread: '

_POREAD_MARKER_RE = re.compile(
    r'<poread-export path="(?P<path>[^"]*)" bytes="(?P<bytes>\d+)" sha256="(?P<sha256>[0-9a-f]+)"\s*/>'
)


# ORCHESTRATOR

def _inject_poread_content(content):
    return _walk_replace_marker_blocks(content, _is_poread_marker_valid, _build_poread_replacement)


# FUNCTIONS

def _parse_poread_marker(text):
    stripped = text.lstrip()
    if not stripped.startswith(POREAD_MARKER_PREFIX):
        return None
    m = _POREAD_MARKER_RE.match(stripped)
    if not m:
        return None
    return m.group('path'), int(m.group('bytes')), m.group('sha256')


def _read_validated_poread_source(path, expected_bytes, expected_hash):
    if expected_bytes > POREAD_MAX_BYTES:
        return None
    try:
        with open(path, 'rb') as f:
            data = f.read()
    except OSError:
        return None
    if len(data) != expected_bytes:
        return None
    if hashlib.sha256(data).hexdigest()[:POREAD_HASH_LEN] != expected_hash:
        return None
    return data


def _is_poread_marker_valid(text):
    parsed = _parse_poread_marker(text)
    if parsed is None:
        return False
    path, expected_bytes, expected_hash = parsed
    if expected_bytes > POREAD_MAX_BYTES:
        print(f"[proxy_addon] poread: marker declares {expected_bytes}B, over the {POREAD_MAX_BYTES}B ceiling — refusing to inject: {path}", file=sys.stderr)
        return False
    data = _read_validated_poread_source(path, expected_bytes, expected_hash)
    if data is None:
        print(f"[proxy_addon] poread: source changed or unavailable, refusing to inject: {path}", file=sys.stderr)
        return False
    return True


def _build_poread_replacement(marker_text):
    path, expected_bytes, expected_hash = _parse_poread_marker(marker_text)
    data = _read_validated_poread_source(path, expected_bytes, expected_hash)
    text = data.decode('utf-8', errors='replace')
    return f"{_POREAD_HEADER_PREFIX}{path} ({expected_bytes}B) ---\n{text}"
