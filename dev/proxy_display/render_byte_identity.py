# INFRASTRUCTURE
import hashlib
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

_MAIN_LOG_DIR = Path(os.environ.get(
    'RENDER_BYTE_IDENTITY_LOG_DIR',
    '/Users/brunowinter2000/Documents/ai/monitor-cc/src/logs/dual_log',
))
_PANE_WIDTHS = (60, 80, 100, 120)

# ORCHESTRATOR

def main():
    fwd_path = _newest_forwarded_log()
    entries = _load_entries(fwd_path)
    _attach_overlays(entries, fwd_path)
    expand_states = _grow_expand_states(entries)
    digest = hashlib.sha256()
    _hash_format_proxy_block(entries, expand_states, digest)
    _hash_section_functions(entries, expand_states, digest)
    print(f'source: {fwd_path.name}')
    print(f'entries: {len(entries)}')
    print(f'expand_states keys: {len(expand_states)}')
    print(f'HASH: {digest.hexdigest()}')


# FUNCTIONS

def _newest_forwarded_log() -> Path:
    files = sorted(_MAIN_LOG_DIR.glob('*_forwarded.jsonl'), key=lambda p: p.stat().st_mtime)
    if not files:
        raise SystemExit(f'no forwarded logs found under {_MAIN_LOG_DIR}')
    return files[-1]


def _load_entries(fwd_path: Path) -> list:
    from src.proxy_display.forwarded_parser import _parse_forwarded_log
    entries, _ = _parse_forwarded_log(fwd_path, 0, {}, keep_last=None)
    return entries


def _attach_overlays(entries: list, fwd_path: Path) -> None:
    from src.proxy_display.forwarded_parser import _infer_model_family
    from src.proxy_display.dual_log_accumulator import accumulate_dual_log, accumulate_original_tools
    from src.proxy_display.proxy_pane_shared import _attach_overlay_references
    stem = fwd_path.name[:-len('_forwarded.jsonl')]
    stripped_path = fwd_path.parent / f'{stem}_stripped.jsonl'
    injected_path = fwd_path.parent / f'{stem}_injected.jsonl'
    original_path = fwd_path.parent / f'{stem}_original.jsonl'
    acc_stripped, acc_injected, acc_original = {}, {}, {}
    accumulate_dual_log(stripped_path, 0, acc_stripped)
    accumulate_dual_log(injected_path, 0, acc_injected)
    accumulate_original_tools(original_path, 0, acc_original)
    _attach_overlay_references(entries, acc_stripped, acc_injected, _infer_model_family, acc_original)


def _grow_expand_states(entries: list) -> dict:
    from src.proxy_display.format import format_proxy_block
    from src.proxy_display.turn_cache import TurnCache
    expand_states = {}
    prev_count = -1
    while len(expand_states) != prev_count:
        prev_count = len(expand_states)
        for width in _PANE_WIDTHS:
            item_positions = {}
            format_proxy_block(entries, expand_states, None, None, 50, width, 0, None, item_positions, turn_cache=TurnCache())
            for key in item_positions:
                if key not in expand_states:
                    expand_states[key] = True
    return expand_states


def _hash_format_proxy_block(entries: list, expand_states: dict, digest) -> None:
    from src.proxy_display.format import format_proxy_block
    from src.proxy_display.turn_cache import TurnCache
    for width in _PANE_WIDTHS:
        item_positions = {}
        line_map = {}
        ansi, total_lines = format_proxy_block(
            entries, expand_states, line_map, None,
            pane_height=100000, pane_width=width, scroll_offset=0,
            turns=None, item_positions_out=item_positions, turn_cache=TurnCache(),
        )
        digest.update(f'fpb|{width}|{total_lines}|'.encode())
        digest.update(ansi.encode())


def _hash_section_functions(entries: list, expand_states: dict, digest) -> None:
    from src.proxy_display.format import _is_standalone_entry
    from src.proxy_display.render_turn import _resolve_prev_same_family
    from src.proxy_display.render_sections import render_tools
    from src.proxy_display.render_sections_system import render_system_blocks
    from src.proxy_display.render_messages import render_messages
    for entry_idx, entry in enumerate(entries):
        is_standalone = _is_standalone_entry(entry)
        prev_same = _resolve_prev_same_family(entries, entry_idx)
        ref = None if is_standalone else prev_same
        for width in _PANE_WIDTHS:
            s_lines, s_keys = render_system_blocks(entry_idx, entry, ref, expand_states, width)
            t_lines, t_keys = render_tools(entry_idx, entry, ref, expand_states, width)
            m_lines, m_keys = render_messages(entry_idx, entry, ref, entries, expand_states, width)
            digest.update(f'sys|{entry_idx}|{width}|'.encode())
            digest.update(repr((s_lines, s_keys)).encode())
            digest.update(f'tools|{entry_idx}|{width}|'.encode())
            digest.update(repr((t_lines, t_keys)).encode())
            digest.update(f'msgs|{entry_idx}|{width}|'.encode())
            digest.update(repr((m_lines, m_keys)).encode())


if __name__ == '__main__':
    main()
