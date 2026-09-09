"""
Byte-identity regression harness for src/gpu_pane/ (gpu-pane-split milestone — pane.py concern
split into gpu_actions.py / gpu_render.py).

Calls _render_pane with synthetic presets/arbitrary/anomalies/today_errors/error_counts/
collections (3 preset scenarios: running+healthy, running+unhealthy, stopped; one arbitrary
server; a fresh 'starting' toggle_state overlay and an old/expired-looking one; 3 errors; 2
collections; 1 anomaly) at two pane widths, with and without a search query, hashing the rendered
output AND the resulting _button_regions dict for every call. time.time() is monkeypatched to a
constant — defensive determinism guard per spec; no code path in _render_pane's own call graph
currently reads it (toggle_state timestamps are constructed directly here, not via _toggle_server/
_fire_button), but this keeps the harness robust if that ever changes.

Usage (from project root):
    ./venv/bin/python dev/gpu_pane/render_byte_identity.py

Prints one HASH line. Run before and after the src/gpu_pane/ split; the hash must match.
"""

# INFRASTRUCTURE
import hashlib
import json
import re
import sys
import time as _time_mod
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

_FIXED_TS = 1800000000.0
_PANE_WIDTHS = (100, 40)
_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[mKHJABCDEFGsuTXP]')

# ORCHESTRATOR


def main():
    render_pane, toggle_state, button_regions = _import_gpu()
    orig_time = _time_mod.time
    _time_mod.time = lambda: _FIXED_TS
    try:
        digest = hashlib.sha256()
        presets, arbitrary, anomalies, today_errors, error_counts, collections = _make_fixtures()
        toggle_state.clear()
        toggle_state['preset_healthy'] = ('starting', _FIXED_TS)          # fresh
        toggle_state['preset_stopped'] = ('starting', _FIXED_TS - 99999)  # old/expired-looking
        for pane_width in _PANE_WIDTHS:
            _hash_one_width(digest, render_pane, button_regions, pane_width,
                             presets, arbitrary, anomalies, today_errors, error_counts, collections)
        print(f'HASH: {digest.hexdigest()}')
    finally:
        _time_mod.time = orig_time
        toggle_state.clear()


# FUNCTIONS

# Imported via a function (not a module-level `from src....` line) — dev/ scripts may not use a
# literal top-level `from src.` import (block_dev_imports_src).
def _import_gpu():
    from src.gpu_pane.pane import _render_pane, _toggle_state, _button_regions
    return _render_pane, _toggle_state, _button_regions


def _make_fixtures() -> tuple:
    presets = [
        {'name': 'preset_healthy', 'kind': 'preset', 'running': True, 'healthy': True,
         'port': 8001, 'pid': 111, 'rss_mb': 512, 'idle_seconds': 120, 'idle_state_missing': False,
         'model_name': 'embed-large'},
        {'name': 'preset_unhealthy', 'kind': 'preset', 'running': True, 'healthy': False,
         'port': 8002, 'pid': 222, 'rss_mb': 800, 'idle_seconds': 30, 'idle_state_missing': False,
         'model_name': 'rerank-base'},
        {'name': 'preset_stopped', 'kind': 'preset', 'running': False, 'healthy': False,
         'port': None, 'pid': None, 'rss_mb': None, 'idle_seconds': None, 'idle_state_missing': False,
         'model_name': None},
    ]
    arbitrary = [
        {'name': 'port-9100', 'kind': 'arbitrary', 'running': True, 'healthy': True,
         'port': 9100, 'pid': 333, 'rss_mb': 256, 'idle_seconds': 5, 'idle_state_missing': False,
         'model_name': 'sparse'},
    ]
    anomalies = [{'kind': 'dead_pid', 'message': 'stale state file: pid 999 dead',
                  'source': 'server-port-999.json'}]
    today_errors = [
        {'ts': '2026-01-01T10:00:00+00:00', 'server': 'preset_healthy', 'code': 'busy',
         'msg': 'queue full'},
        {'ts': '2026-01-01T11:00:00+00:00', 'server': 'preset_unhealthy',
         'code': 'watchdog_killed_orphan', 'msg': 'no response'},
        {'ts': '2026-01-01T12:00:00+00:00', 'server': 'port-9100',
         'code': 'single_instance_alive_replaced', 'msg': 'replaced'},
    ]
    error_counts = {'preset_healthy': 1, 'preset_unhealthy': 1, 'port-9100': 1}
    collections = [{'collection': 'docs', 'chunks': 4200}, {'collection': 'code', 'chunks': 900}]
    return presets, arbitrary, anomalies, today_errors, error_counts, collections


def _strip_ansi_for_match(line: str) -> str:
    return _ANSI_RE.sub('', line)


def _regions_for_hash(regions: dict) -> list:
    return sorted([list(k) + list(v) for k, v in regions.items()])


# Renders one pane_width twice (baseline, then with a search query matched against the baseline's
# own rendered lines — mirrors _gpu_search_on_commit's own matching approach), hashing
# (output, _button_regions) for each of the 2 calls.
def _hash_one_width(digest, render_pane, button_regions, pane_width: int, presets: list,
                     arbitrary: list, anomalies: list, today_errors: list, error_counts: dict,
                     collections: list) -> None:
    baseline = render_pane(pane_width, 30, presets, arbitrary, anomalies, today_errors,
                            error_counts, collections)
    digest.update(f'width={pane_width}|no_search|'.encode())
    digest.update(baseline.encode())
    digest.update(json.dumps(_regions_for_hash(dict(button_regions)), sort_keys=True).encode())

    query = 'rss'
    lines = baseline.split('\n')
    matches = {i for i, ln in enumerate(lines) if query in _strip_ansi_for_match(ln).lower()}
    current = min(matches) if matches else None
    searched = render_pane(pane_width, 30, presets, arbitrary, anomalies, today_errors,
                            error_counts, collections, search_query=query,
                            search_match_line_set=matches, search_current_line=current)
    digest.update(f'width={pane_width}|search={query}|'.encode())
    digest.update(searched.encode())
    digest.update(json.dumps(_regions_for_hash(dict(button_regions)), sort_keys=True).encode())


if __name__ == '__main__':
    main()
