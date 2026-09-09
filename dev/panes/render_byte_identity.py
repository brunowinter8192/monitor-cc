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
(3) format_cache_tracker (src.format.token_format) over a synthetic 1-turn/2-call list with
    response_rid_map populated (rate-limit headers: utilization+reset for both 5h/7d windows,
    plus a non-'allowed' status and a non-'allowed' overage), expand_states all True, a
    copy_feedback entry with a future expiry, and a search query matching the turn/call — added
    for the tokens-data-render-helpers milestone (2026-09) specifically to cover the `rl:`/warn
    lines and the expanded content-blocks loop, which the workers-pane harness's own synthetic
    fixtures never populate.

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
    build_cache_turns, format_warnings_pane, format_cache_tracker = _import_panes()
    digest = hashlib.sha256()
    _hash_cache_turns(digest, build_cache_turns)
    _hash_warnings_pane(digest, format_warnings_pane)
    _hash_format_cache_tracker(digest, format_cache_tracker)
    print(f'HASH: {digest.hexdigest()}')


# FUNCTIONS

# Imported via a function (not a module-level `from src....` line) — dev/ scripts may not use a
# literal top-level `from src.` import (block_dev_imports_src).
def _import_panes():
    from src.panes.cache_turns import build_cache_turns
    from src.panes.warnings_render import _format_warnings_pane
    from src.format import format_cache_tracker
    return build_cache_turns, _format_warnings_pane, format_cache_tracker


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


# 1 turn / 2 calls, both with request_ids matched in response_rid_map — call 0 carries every
# usage-extras group (ttl/web/meta/iterations) plus rate-limit headers with a non-'allowed'
# status AND a non-'allowed' overage (exercises both the `rl:` line and the YELLOW warn line);
# call 1 has a plain content_blocks set (tool_use/thinking/text) with no rate-limit headers.
# Fixed (not "now"-relative) reset epochs so the same-day/other-day _fmt_rl_reset_time branch
# taken doesn't depend on which day this harness happens to run.
def _make_rate_limit_turns() -> tuple:
    call_0 = {
        'cache_read': 5000, 'cache_creation': 200, 'direct': 0, 'output_tokens': 120,
        'request_id': 'req-rl-1',
        'cache_creation_ttl': {'ephemeral_5m_input_tokens': 100, 'ephemeral_1h_input_tokens': 50},
        'server_tool_use': {'web_search_requests': 2, 'web_fetch_requests': 1},
        'service_tier': 'standard', 'speed': 'fast', 'inference_geo': 'us',
        'iterations': [{'n': 1}, {'n': 2}],
        'content_blocks': [
            {'type': 'tool_use', 'tool_name': 'Bash', 'preview': {'command': 'ls -la'}},
            {'type': 'thinking', 'sig_chars': 9000},
            {'type': 'text', 'preview': 'investigating the rate limit issue'},
        ],
    }
    call_1 = {
        'cache_read': 1200, 'cache_creation': 0, 'direct': 300, 'output_tokens': 40,
        'request_id': 'req-rl-2',
        'content_blocks': [{'type': 'text', 'preview': 'follow-up'}],
    }
    turn = {
        'timestamp': '2026-04-21T10:00:00Z', 'prompt': 'investigate the rate limit issue',
        'api_calls': [call_0, call_1],
    }
    response_rid_map = {
        'req-rl-1': {
            'anthropic-ratelimit-unified-5h-utilization': '0.82',
            'anthropic-ratelimit-unified-5h-reset': '1893456000',   # 2030-01-01, fixed
            'anthropic-ratelimit-unified-7d-utilization': '0.55',
            'anthropic-ratelimit-unified-7d-reset': '1893542400',   # 2030-01-02, fixed
            'anthropic-ratelimit-unified-status': 'rejected',
            'anthropic-ratelimit-unified-overage-status': 'disabled',
            'anthropic-ratelimit-unified-overage-disabled-reason': 'exceeded plan limit',
        },
    }
    return [turn], response_rid_map


def _hash_format_cache_tracker(digest, format_cache_tracker) -> None:
    turns, response_rid_map = _make_rate_limit_turns()
    expand_states = {(0, 0): True, (0, 1): True}
    copy_feedback = {(0, 0): 9999999999.0}   # far-future expiry -> is_flash branch
    nav_out = {}
    for pane_width in (40, 100):
        result = format_cache_tracker(
            turns, expand_states=expand_states, pane_height=30, pane_width=pane_width,
            scroll_offset=0, response_rid_map=response_rid_map, copy_feedback=copy_feedback,
            search_match_set={(0, 0), ('turn', 0)}, search_current_key=(0, 0),
            search_query='rate limit', nav_out=nav_out,
        )
        digest.update(f'cache_tracker|{pane_width}|'.encode())
        digest.update(json.dumps(result, default=str, sort_keys=True).encode())
        nav_out_str_keys = {str(k): v for k, v in nav_out.items()}
        digest.update(json.dumps(nav_out_str_keys, default=str, sort_keys=True).encode())


if __name__ == '__main__':
    main()
