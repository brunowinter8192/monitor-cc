# INFRASTRUCTURE
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scenario_lib import Sim

_HOVER_ROWS = tuple(range(2, 32))
_EXPANDED_KEYS = (('req', 20), ('sys', 20), ('req', 60), ('req', 100), ('tools', 100), ('req', 140), ('req', 180), ('req', 220), ('req', 260))
_FULL = 10_000


# ORCHESTRATOR

def main():
    args = _parse_args()
    sim = Sim(args.root)
    try:
        sim.refresh({'forwarded': _FULL, 'response': _FULL, 'stripped': _FULL, 'injected': _FULL, 'original': 2})
        if args.scale > 1:
            sim.scale_up(args.scale)
        result = {'scale': args.scale, 'root': args.root, 'mode': args.mode, 'entries': len(sim.entries), 'turns': len(sim.turns), 'hover_rows': len(_HOVER_ROWS)}
        result['collapsed'] = _measure(sim, args.mode)
        for key in _EXPANDED_KEYS:
            sim.toggle(key)
        result['expanded'] = _measure(sim, args.mode)
    finally:
        sim.cleanup()
    Path(args.out).write_text(json.dumps(result, indent=1), encoding='utf-8')


# FUNCTIONS

def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--mode', choices=('block', 'pane'), required=True)
    parser.add_argument('--scale', type=int, default=1)
    parser.add_argument('--out', required=True)
    return parser.parse_args()


def _measure(sim, mode: str) -> dict:
    if mode == 'pane':
        _prepare_pane(sim)
    started = time.perf_counter()
    _render_once(sim, mode, 1)
    first_ms = (time.perf_counter() - started) * 1000
    samples = []
    for row in _HOVER_ROWS:
        started = time.perf_counter()
        _render_once(sim, mode, row)
        samples.append((time.perf_counter() - started) * 1000)
    return {'first_ms': round(first_ms, 2), 'median_ms': round(statistics.median(samples), 2), 'min_ms': round(min(samples), 2), 'max_ms': round(max(samples), 2)}


def _prepare_pane(sim) -> None:
    from src.proxy_display import pane
    pane.proxy_entries[:] = sim.entries
    pane._proxy_cache_turns = sim.turns
    pane._proxy_request_id_by_flow.clear()
    pane._proxy_request_id_by_flow.update(sim.rid_by_flow)
    pane.proxy_expand_states.clear()
    pane.proxy_expand_states.update(sim.expand)


def _render_once(sim, mode: str, row: int) -> None:
    if mode == 'block':
        sim.render_timed(row)
        return
    from src.proxy_display import pane
    pane.proxy_hover_row = row
    pane._proxy_session_start_ts = '2000-01-01T00:00:00Z'
    pane._build_proxy_output()


if __name__ == '__main__':
    main()
