"""
Byte-identity regression harness for src/panes/ (panes-split milestone — token_pane.py /
warnings_pane.py / warnings_render.py concern split).

(1) build_cache_turns fed incrementally (in growing file-line chunks, mirroring how the real
    pane polls a growing session JSONL) over a frozen 300-line prefix of a real session JSONL
    under ~/.claude/projects/, hashing the resulting turns after EVERY chunk (not just the final
    state) — this is what actually exercises the duplicate-call merge path the function's own
    LOC-split touches.
(2) _format_warnings_pane over a synthetic tool_errors list (4 errors: mixed expanded/collapsed,
    one carrying _pre_strip_text/_stripped_chunks, one with a search match) at two pane widths,
    hashing (rendered_string, line_map).
(3) format_cache_tracker output is already covered by the workers-pane byte-identity harness —
    skipped here, per the milestone's own scope note.

Usage (from project root):
    ./venv/bin/python dev/panes/render_byte_identity.py

Prints one HASH line. Run before and after the src/panes/ split; the hash must match. Never
commits a session-log snapshot — only reads (via a /tmp-pinned copy, see PANES_BYTE_IDENTITY_JSONL).
"""

# INFRASTRUCTURE
import hashlib
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
os.environ.setdefault('MONITOR_CC_ROOT', str(_ROOT))

_PROJECTS_DIR = Path.home() / '.claude' / 'projects'
_PREFIX_LINES = 300
_CHUNK_SIZE = 40  # lines appended per incremental build_cache_turns() feed step

# ORCHESTRATOR


def main():
    build_cache_turns, format_warnings_pane = _import_panes()
    digest = hashlib.sha256()
    _hash_cache_turns(digest, build_cache_turns)
    _hash_warnings_pane(digest, format_warnings_pane)
    print(f'HASH: {digest.hexdigest()}')


# FUNCTIONS

# Imported via a function (not a module-level `from src....` line) — dev/ scripts may not use a
# literal top-level `from src.` import (block_dev_imports_src).
def _import_panes():
    from src.panes.cache_turns import build_cache_turns
    from src.panes.warnings_render import _format_warnings_pane
    return build_cache_turns, _format_warnings_pane


# PANES_BYTE_IDENTITY_JSONL overrides the source session path — pin a real *.jsonl's frozen
# 300-line prefix to a fixed /tmp path once, then point both before/after runs at it via the env
# var, same convention as dev/proxy/pipeline_byte_identity.py's own override var.
def _session_jsonl() -> Path:
    override = os.environ.get('PANES_BYTE_IDENTITY_JSONL')
    if override:
        return Path(override)
    files = sorted(_PROJECTS_DIR.glob('*/*.jsonl'), key=lambda p: p.stat().st_mtime)
    if not files:
        raise SystemExit(f'no *.jsonl session logs found under {_PROJECTS_DIR}')
    return files[-1]


def _frozen_prefix_lines(source: Path) -> list:
    lines = []
    with open(source, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= _PREFIX_LINES:
                break
            lines.append(line)
    return lines


def _normalize_turns_for_hash(turns: list):
    return json.dumps(turns, default=str, sort_keys=True)


# Feeds the frozen prefix into build_cache_turns() in growing chunks (mirrors incremental polling
# of a real session file), hashing the resulting turns after EVERY chunk.
def _hash_cache_turns(digest, build_cache_turns) -> None:
    import tempfile
    source = _session_jsonl()
    lines = _frozen_prefix_lines(source)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False, encoding='utf-8') as f:
        tmp_path = Path(f.name)
    try:
        last_position = 0
        turns: list = []
        written = 0
        while written < len(lines):
            chunk = lines[written:written + _CHUNK_SIZE]
            with open(tmp_path, 'a', encoding='utf-8') as f:
                f.writelines(chunk)
            written += len(chunk)
            turns, last_position = build_cache_turns(tmp_path, last_position, turns)
            digest.update(f'cache_turns|{written}|'.encode())
            digest.update(_normalize_turns_for_hash(turns).encode())
    finally:
        tmp_path.unlink(missing_ok=True)


# 4 synthetic tool_errors: [0] collapsed no-match, [1] expanded no-match with a strip overlay
# (_pre_strip_text/_stripped_chunks), [2] collapsed WITH a search match, [3] expanded WITH a
# search match (exercises both the collapsed-container-mark and expanded-substring-highlight
# paths in the same call).
def _make_tool_errors() -> list:
    return [
        {'timestamp': '10:00:00', 'tool_name': 'Bash', 'summary': 'boom one', 'full_text': 'boom one',
         'tool_call_input': {'command': 'ls -la'}, 'worker_name': ''},
        {'timestamp': '10:01:00', 'tool_name': 'Grep', 'summary': 'boom two', 'full_text': 'line1\nline2\nline3',
         'tool_call_input': {'pattern': 'x'}, 'worker_name': 'w1',
         '_pre_strip_text': 'line1\n[STRIPPED]\nline3', '_stripped_chunks': ['line2']},
        {'timestamp': '10:02:00', 'tool_name': 'Read', 'summary': 'unique_marker_q one', 'full_text': 'unique_marker_q one',
         'tool_call_input': {'file_path': '/tmp/unique_marker_q.txt'}, 'worker_name': ''},
        {'timestamp': '10:03:00', 'tool_name': 'Edit', 'summary': 'has unique_marker_q too', 'full_text': 'has unique_marker_q too',
         'tool_call_input': {'old_string': 'unique_marker_q'}, 'worker_name': 'w2'},
    ]


def _hash_warnings_pane(digest, format_warnings_pane) -> None:
    tool_errors = _make_tool_errors()
    error_expand_states = {0: False, 1: True, 2: False, 3: True}
    search_match_set = {2, 3}
    for pane_width in (40, 100):
        output, line_map = format_warnings_pane(
            tool_errors, error_expand_states, None, 0, 30, pane_width,
            header='search: _\n[r]efresh',
            copy_feedback={}, copy_rows_out=set(), header_lines=2,
            search_match_set=search_match_set, search_current_key=3,
            search_query='unique_marker_q',
        )
        digest.update(f'warnings|{pane_width}|'.encode())
        digest.update(output.encode())
        digest.update(json.dumps(line_map, sort_keys=True, default=str).encode())


if __name__ == '__main__':
    main()
