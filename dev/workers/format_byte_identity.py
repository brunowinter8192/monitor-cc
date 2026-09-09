"""
Byte-identity regression harness for src.workers.worker_format.format_workers_block.

Builds a synthetic 3-worker list (varied status/tokens/context_pct/purpose), expands one of
them with turns from a real worker JSONL under ~/.claude/projects/ if one exists (else synthetic
turns), renders across a matrix of (frozen, selected_name, copy_feedback, search) argument
combinations at two pane widths (os.get_terminal_size() monkeypatched — format_workers_block
detects width internally, no width parameter), and hashes every rendered (all_lines, line_keys,
regions_out) triple.

Usage (from project root):
    ./venv/bin/python dev/workers/format_byte_identity.py

Prints one HASH line. Run before and after a worker_format.py refactor; the hash must match.
"""

# INFRASTRUCTURE
import hashlib
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

_PANE_WIDTHS = (80, 120)

# ORCHESTRATOR

def main():
    workers = _build_synthetic_workers()
    worker_turns = {workers[0]['name']: _load_real_or_synthetic_turns()}
    digest = hashlib.sha256()
    _hash_all_variants(workers, worker_turns, digest)
    print(f'HASH: {digest.hexdigest()}')


# FUNCTIONS

def _build_synthetic_workers() -> list:
    return [
        {
            'name': 'alpha', 'status': 'working', 'spawned': '10:00',
            'purpose': 'refactor the pane split', 'model': 'sonnet',
            'tokens': {'output': 15234}, 'context_pct': 72, 'session': 'sess-alpha',
        },
        {
            'name': 'beta', 'status': 'idle', 'spawned': '09:45',
            'purpose': 'investigate a flaky test that only fails on CI under load',
            'model': 'opus', 'tokens': {'output': 890}, 'context_pct': 34, 'session': 'sess-beta',
        },
        {
            'name': 'gamma', 'status': 'exited', 'spawned': '', 'purpose': '',
            'model': '', 'tokens': {}, 'context_pct': None, 'session': 'sess-gamma',
        },
    ]


# WORKERS_BYTE_IDENTITY_JSONL overrides the source JSONL path — needed to pin a before/after
# comparison to the exact same bytes, since the "newest" file under ~/.claude/projects/ can be
# THIS very agent's own actively-growing transcript (same pitfall documented for
# dev/proxy_display/render_byte_identity.py's RENDER_BYTE_IDENTITY_LOG_DIR — see that module's
# own Gotcha). Snapshot a real JSONL to a fixed path once, then point both runs at it.
def _find_real_worker_jsonl():
    override = os.environ.get('WORKERS_BYTE_IDENTITY_JSONL')
    if override:
        path = Path(override)
        return path if path.exists() else None
    projects_dir = Path.home() / '.claude' / 'projects'
    if not projects_dir.exists():
        return None
    candidates = [
        f for d in projects_dir.iterdir() if d.is_dir()
        for f in d.glob('*.jsonl') if not f.name.startswith('agent-')
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda f: f.stat().st_mtime)


def _load_real_or_synthetic_turns() -> list:
    from src.jsonl import read_new_lines, parse_jsonl_lines, extract_cache_turns
    jsonl_path = _find_real_worker_jsonl()
    if jsonl_path is not None:
        lines = read_new_lines(jsonl_path, 0)
        lines = lines[:200]  # bounded, fixed-size prefix — stable even if the source file grows
        messages, _ = parse_jsonl_lines(lines)
        turns = extract_cache_turns(messages)
        if turns:
            return turns[:10]
    return _synthetic_turns()


def _synthetic_turns() -> list:
    return [
        {
            'timestamp': f'2026-04-21T10:{i:02d}:00Z', 'prompt': f'turn {i}',
            'api_calls': [{
                'cache_read': 1000 * (i + 1), 'cache_creation': 200, 'direct': 0,
                'output_tokens': 50 + i,
                'content_blocks': [{'type': 'text', 'preview': f'call {i} preview', 'chars': 20}],
            }],
        }
        for i in range(4)
    ]


def _render_variants() -> list:
    a_name, b_name = 'alpha', 'beta'
    return [
        dict(frozen=False, selected_name=None, copy_feedback=None,
             search_match_set=None, search_current_key=None, search_query=''),
        dict(frozen=True, selected_name=b_name, copy_feedback={a_name: 1e18},
             search_match_set=None, search_current_key=None, search_query=''),
        dict(frozen=False, selected_name=a_name, copy_feedback=None,
             search_match_set={b_name, (a_name, 0, 0)}, search_current_key=(a_name, 0, 0),
             search_query='call'),
    ]


def _hash_all_variants(workers: list, worker_turns: dict, digest) -> None:
    from src.workers.worker_format import format_workers_block
    expand_states = {workers[0]['name']: True}
    scroll_offsets = {}
    cache_expand_states = {workers[0]['name']: {(0, 0): True}}
    variants = _render_variants()
    orig_terminal_size = os.get_terminal_size
    try:
        for width in _PANE_WIDTHS:
            os.get_terminal_size = lambda w=width: os.terminal_size((w, 40))
            for v_idx, variant in enumerate(variants):
                regions_out = {}
                all_lines, line_keys = format_workers_block(
                    workers, expand_states, worker_turns, scroll_offsets, cache_expand_states,
                    regions_out=regions_out, **variant,
                )
                digest.update(f'w{width}|v{v_idx}|'.encode())
                digest.update(repr((all_lines, line_keys, regions_out)).encode())
    finally:
        os.get_terminal_size = orig_terminal_size


if __name__ == '__main__':
    main()
