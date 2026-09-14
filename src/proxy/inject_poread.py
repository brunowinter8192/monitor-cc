import hashlib
import re
import sys

from .payload_helpers import _walk_replace_marker_blocks

# INFRASTRUCTURE

POREAD_MAX_BYTES = 50_000
POREAD_HASH_LEN = 16
POREAD_MARKER_PREFIX = '<poread-export '
POREAD_NOTICE = (
    "The file's full content will arrive automatically on the next turn — do not read "
    "this file again until then."
)

_POREAD_HEADER_PREFIX = '--- poread: '

_POREAD_MARKER_RE = re.compile(
    r'<poread-export path="(?P<path>[^"]*)" bytes="(?P<bytes>\d+)" sha256="(?P<sha256>[0-9a-f]+)"\s*/>'
    r'\n' + re.escape(POREAD_NOTICE)
)


# ORCHESTRATOR

def _inject_poread_content(content):
    cache: dict = {}
    predicate = lambda text: _is_poread_marker_valid(text, cache)
    replace_fn = lambda text: _build_poread_replacement(text, cache)
    return _walk_replace_marker_blocks(content, predicate, replace_fn)


# FUNCTIONS

def _parse_poread_marker(text):
    stripped = text.strip()
    if not stripped.startswith(POREAD_MARKER_PREFIX):
        return None
    m = _POREAD_MARKER_RE.fullmatch(stripped)
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


def _is_poread_marker_valid(text, cache):
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
    cache[text] = data
    return True


def _build_poread_replacement(marker_text, cache):
    path, expected_bytes, _expected_hash = _parse_poread_marker(marker_text)
    data = cache.pop(marker_text)
    text = data.decode('utf-8', errors='replace')
    return f"{_POREAD_HEADER_PREFIX}{path} ({expected_bytes}B) ---\n{text}"
