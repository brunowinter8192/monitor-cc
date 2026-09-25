# INFRASTRUCTURE
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scenario_lib import Sim, _FAR_FUTURE, _PAST

_FULL = 10_000
_HOVER_ROWS = (2, 5, 9, 14, 20, 27, 33, 41, 49)


# ORCHESTRATOR

def main():
    args = _parse_args()
    sim = Sim(args.root)
    try:
        steps = scenarios()[args.scenario](sim)
    finally:
        sim.cleanup()
    Path(args.out).write_text(json.dumps(steps), encoding='utf-8')


# FUNCTIONS

def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--scenario', required=True)
    parser.add_argument('--out', required=True)
    return parser.parse_args()


def scenarios():
    return {
        'hover': sc_hover,
        'grow_and_new_turn': sc_grow_and_new_turn,
        'late_response': sc_late_response,
        'late_overlay': sc_late_overlay,
        'expand_collapse': sc_expand_collapse,
        'search': sc_search,
        'width': sc_width,
        'copy_feedback': sc_copy_feedback,
        'reparse': sc_reparse,
        'unsorted_turns': sc_unsorted_turns,
        'tripwire': sc_tripwire,
    }


def sc_hover(sim) -> list:
    steps = []
    sim.refresh(_counts(_FULL))
    _step(steps, 'warm', 'warm', sim.render())
    sim.toggle(('req', 3))
    sim.toggle(('req', 50))
    sim.toggle(('sys', 50))
    _step(steps, 'expand', 'change', sim.render())
    _hovers(sim, steps)
    for scroll in (3, 30, 90, 0):
        sim.scroll = scroll
        _step(steps, f'scroll{scroll}', 'hover', sim.render(hover=12))
        _hovers(sim, steps, prefix=f'hover_s{scroll}')
    return steps


def _counts(n: int, lag_resp: int = 0, lag_strip: int = 0, lag_inj: int = 0) -> dict:
    return {'forwarded': n, 'response': max(0, n - lag_resp), 'stripped': max(0, n - lag_strip), 'injected': max(0, n - lag_inj), 'original': 2}


def _step(steps: list, label: str, kind: str, result: tuple) -> None:
    steps.append([label, kind, result[0], result[1]])


def _hovers(sim, steps: list, width: int = 80, prefix: str = 'hover') -> None:
    for row in _HOVER_ROWS:
        _step(steps, f'{prefix}@{row}', 'hover', sim.render(hover=row, width=width))


def sc_grow_and_new_turn(sim) -> list:
    steps = []
    sim.refresh(_counts(150))
    _step(steps, 'warm', 'warm', sim.render())
    for n in range(151, 181):
        sim.refresh(_counts(n))
        _step(steps, f'grow{n}', 'grow', sim.render(hover=10))
        _step(steps, f'hover{n}', 'hover', sim.render(hover=11))
    return steps


def sc_late_response(sim) -> list:
    steps = []
    sim.refresh(_counts(200, lag_resp=200))
    _step(steps, 'warm_noresp', 'warm', sim.render())
    _hovers(sim, steps, prefix='noresp')
    for n in (30, 90, 150, 197, 200):
        sim.refresh(_counts(200, lag_resp=200 - n))
        _step(steps, f'resp{n}', 'change', sim.render(hover=8))
        _hovers(sim, steps, prefix=f'after_resp{n}')
    return steps


def sc_late_overlay(sim) -> list:
    steps = []
    sim.refresh(_counts(200, lag_strip=60, lag_inj=60))
    for key in (('req', 10), ('req', 60), ('req', 120), ('sys', 120), ('req', 150), ('req', 170), ('req', 190), ('req', 197)):
        sim.toggle(key)
    _step(steps, 'warm', 'warm', sim.render())
    _hovers(sim, steps, prefix='lagged')
    for lag in (40, 20, 5, 0):
        sim.refresh(_counts(200, lag_strip=lag, lag_inj=lag))
        _step(steps, f'overlay_lag{lag}', 'change', sim.render(hover=8))
        _hovers(sim, steps, prefix=f'after_lag{lag}')
    sim.refresh(_counts(_FULL))
    _step(steps, 'overlay_full', 'change', sim.render(hover=8))
    _hovers(sim, steps, prefix='full')
    return steps


def sc_expand_collapse(sim) -> list:
    steps = []
    sim.refresh(_counts(_FULL))
    _step(steps, 'warm', 'warm', sim.render())
    for key in (('req', 20), ('sys', 20), ('tools', 20), ('beta', 20), ('fields', 20), ('req', 120), ('req', 121), ('tools', 121)):
        sim.toggle(key)
        _step(steps, f'toggle{key}', 'change', sim.render(hover=6))
        _step(steps, f'hover_after{key}', 'hover', sim.render(hover=9))
    for key in (('req', 20), ('req', 120)):
        sim.toggle(key)
        _step(steps, f'collapse{key}', 'change', sim.render(hover=6))
        _hovers(sim, steps, prefix=f'collapsed{key}')
    sim.refresh(_counts(_FULL))
    _step(steps, 'refresh_strip_inactive', 'change', sim.render(hover=6))
    return steps


def sc_search(sim) -> list:
    steps = []
    sim.refresh(_counts(_FULL))
    _step(steps, 'warm', 'warm', sim.render())
    for query in ('tool', 'system-reminder'):
        sim.search(query)
        _step(steps, f'search[{query}]', 'change', sim.render(hover=7))
        _hovers(sim, steps, prefix=f'search[{query}]')
        for n in range(1, min(4, len(sim.search_matches))):
            sim.search_current = n
            sim.just_expanded = ('req', sim.search_matches[n])
            _step(steps, f'jump{n}[{query}]', 'change', sim.render(hover=7))
    sim.clear_search()
    _step(steps, 'search_cleared', 'change', sim.render(hover=7))
    _hovers(sim, steps, prefix='cleared')
    return steps


def sc_width(sim) -> list:
    steps = []
    sim.refresh(_counts(_FULL))
    _step(steps, 'warm', 'warm', sim.render())
    for width in (60, 80, 100, 120, 80, 60):
        _step(steps, f'width{width}', 'change', sim.render(hover=7, width=width))
        _hovers(sim, steps, width=width, prefix=f'w{width}')
    return steps


def sc_copy_feedback(sim) -> list:
    steps = []
    sim.refresh(_counts(_FULL))
    sim.toggle(('req', 20))
    _step(steps, 'warm', 'warm', sim.render())
    _step(steps, 'flash_req5', 'change', sim.render(feedback={5: _FAR_FUTURE}))
    _step(steps, 'flash_req5_hover', 'hover', sim.render(hover=9, feedback={5: _FAR_FUTURE}))
    _step(steps, 'flash_msg20', 'change', sim.render(feedback={5: _FAR_FUTURE, ('msg', 20, 0): _FAR_FUTURE}))
    _step(steps, 'flash_expired', 'change', sim.render(feedback={5: _PAST, ('msg', 20, 0): _PAST}))
    _step(steps, 'flash_expired_hover', 'hover', sim.render(hover=9, feedback={5: _PAST, ('msg', 20, 0): _PAST}))
    _step(steps, 'flash_empty', 'change', sim.render(feedback={}))
    _step(steps, 'feedback_none', 'change', _render_no_feedback(sim))
    return steps


def _render_no_feedback(sim) -> tuple:
    sim.feedback, saved = None, sim.feedback
    try:
        return sim.render()
    finally:
        sim.feedback = saved


def sc_reparse(sim) -> list:
    steps = []
    sim.refresh(_counts(150))
    sim.toggle(('req', 30))
    _step(steps, 'warm', 'warm', sim.render())
    sim.reset_state()
    sim.refresh(_counts(100))
    _step(steps, 'after_reset', 'change', sim.render(hover=6))
    _hovers(sim, steps, prefix='after_reset')
    sim.refresh(_counts(_FULL))
    _step(steps, 'after_refill', 'change', sim.render(hover=6))
    _hovers(sim, steps, prefix='after_refill')
    return steps


def sc_unsorted_turns(sim) -> list:
    steps = []
    sim.refresh(_counts(_FULL))
    _step(steps, 'warm', 'warm', sim.render())
    sim.swap_turn_timestamps(5)
    _step(steps, 'swapped', 'change', sim.render(hover=7))
    _hovers(sim, steps, prefix='swapped')
    sim.rebuild_turns()
    sim.turn_dicts[5] = None
    sim.turn_dicts[6] = None
    sim.rebuild_turns()
    _step(steps, 'sorted_again', 'change', sim.render(hover=7))
    _hovers(sim, steps, prefix='sorted_again')
    return steps


def sc_tripwire(sim) -> list:
    sim.refresh(_counts(60))
    sim.render()
    steps = []
    for bad in (('weird',), ('a', 'b'), 'text'):
        sim.expand[bad] = True
        try:
            sim.render()
            outcome = 'no-raise'
        except ValueError:
            outcome = 'ValueError'
        except Exception as exc:
            outcome = type(exc).__name__
        del sim.expand[bad]
        steps.append([f'bad_key{bad!r}', 'tripwire', outcome, 0])
    return steps


if __name__ == '__main__':
    main()
