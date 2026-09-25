# INFRASTRUCTURE
import time
from datetime import datetime
from typing import Callable, Dict, List, Tuple

from dev.session_launcher.space_lib import (
    desktop_methods,
    active_space,
    cg_arrow_hotkey,
    permission_state,
    return_home,
    space_ids,
    swipe_flavor_defaults,
    swipe_once,
    sysevents_arrow_hotkey,
    wait_active,
    write_report,
)

_TAP_SESSION = 1
_SETTLE_SECONDS = 1.2
_MAX_DESKTOP = 5


# ORCHESTRATOR

def main() -> None:
    home_space = active_space()
    ids = space_ids()
    home_idx = compute_home_idx(ids, home_space)
    near_idx, far_idx = _pick_targets(home_idx)
    state = assign_values()
    perms = permission_state()
    results = []
    run_variants_until_return_fails(home_idx, near_idx, far_idx, ids, state, home_space, results)
    path = write_report(__file__, _build_report(results, perms, home_idx))
    print_report(path)


# FUNCTIONS

def compute_home_idx(ids, home_space):
    return ids.index(home_space) + 1


def _pick_targets(home_idx: int) -> Tuple[int, int]:
    near = home_idx + 1 if home_idx < _MAX_DESKTOP else home_idx - 1
    far = 1 if abs(home_idx - 1) >= abs(_MAX_DESKTOP - home_idx) else _MAX_DESKTOP
    return near, far


def assign_values():
    state: Dict[str, object] = {'reversed': {}, 'preferred': ['a1', 'b']}
    return state


def run_variants_until_return_fails(home_idx, near_idx, far_idx, ids, state, home_space, results):
    for variant in _build_variants(home_idx, near_idx, far_idx, ids, state):
        result = _run_variant(variant, home_space, ids, state)
        results.append(result)
        print(_format_console(result), flush=True)
        if not result['returned']:
            print(f'ABORT: could not return to desktop {home_idx}, active is desktop {space_ids().index(active_space()) + 1}')
            break


def _build_variants(home_idx: int, near_idx: int, far_idx: int, ids: List[int], state: Dict[str, object]) -> List[dict]:
    variants = []
    for label, method in (('a1 CGEventPost session flags', 'a1'), ('a2 CGEventPost HID flags', 'a2'),
                          ('a3 CGEventPost session explicit ctrl', 'a3'), ('b System Events key code', 'b')):
        variants.append(_hotkey_variant(label, method, near_idx))
        variants.append(_hotkey_variant(label, method, far_idx))
    variants.append(_arrow_variant('d1 CGEventPost Ctrl+Arrow', home_idx, near_idx,
                                   lambda right: cg_arrow_hotkey(right, _TAP_SESSION)))
    variants.append(_arrow_variant('d2 System Events Ctrl+Arrow', home_idx, near_idx, sysevents_arrow_hotkey))
    for flavor in ('joshuarli', 'jurplel'):
        variants.append(_swipe_variant(flavor, home_idx, near_idx, state))
        variants.append(_swipe_variant(flavor, home_idx, far_idx, state))
    return variants


def _hotkey_variant(name: str, method: str, target_idx: int) -> dict:
    return {'name': f'{name} -> desktop {target_idx}', 'kind': 'target', 'target_idx': target_idx,
            'action': lambda: desktop_methods()[method](target_idx), 'method': method}


def _arrow_variant(name: str, home_idx: int, target_idx: int, fn: Callable[[bool], None]) -> dict:
    right = target_idx > home_idx
    return {'name': f'{name} -> desktop {target_idx}', 'kind': 'target', 'target_idx': target_idx,
            'action': lambda: fn(right), 'method': None}


def _swipe_variant(flavor: str, home_idx: int, target_idx: int, state: Dict[str, object]) -> dict:
    steps = abs(target_idx - home_idx)
    base = swipe_flavor_defaults(flavor)
    velocity = base * steps if flavor == 'jurplel' else base

    def action() -> None:
        right = _direction_right(home_idx, target_idx, flavor, state)
        for _ in range(steps):
            swipe_once(right, flavor, velocity)

    kind = 'calibrate' if steps == 1 and flavor not in state['reversed'] else 'target'
    return {'name': f'c_{flavor} {steps}-step -> desktop {target_idx}', 'kind': kind, 'target_idx': target_idx,
            'action': action, 'method': None, 'flavor': flavor, 'steps': steps}


def _direction_right(home_idx: int, target_idx: int, flavor: str, state: Dict[str, object]) -> bool:
    right = target_idx > home_idx
    if state['reversed'].get(flavor):
        return not right
    return right


def _run_variant(variant: dict, home_space: int, ids: List[int], state: Dict[str, object]) -> dict:
    target_space = ids[variant['target_idx'] - 1]
    origin = active_space()
    t0 = time.monotonic()
    variant['action']()
    ms = wait_active(target_space)
    observed_space = active_space()
    observed_idx = ids.index(observed_space) + 1 if observed_space in ids else None
    ok = ms is not None
    note = ''
    if variant['kind'] == 'calibrate' and not ok and observed_space != origin:
        state['reversed'][variant['flavor']] = True
        note = 'moved opposite direction, direction flag set for this flavor'
    elif variant['kind'] == 'calibrate' and ok:
        state['reversed'][variant['flavor']] = False
    if ok and variant['method'] and variant['method'] not in state['preferred']:
        state['preferred'].insert(0, variant['method'])
    time.sleep(_SETTLE_SECONDS)
    returned = return_home(home_space, state['preferred'])
    return {'name': variant['name'], 'target_idx': variant['target_idx'], 'ok': ok,
            'ms': ms, 'observed_idx': observed_idx, 'note': note, 'returned': returned,
            'total_s': time.monotonic() - t0}


def _format_console(result: dict) -> str:
    ms = f'{result["ms"]:.0f}ms' if result['ms'] is not None else 'no switch'
    return f'{result["name"]}: ok={result["ok"]} {ms} observed_desktop={result["observed_idx"]} returned={result["returned"]} {result["note"]}'


def _build_report(results: List[dict], perms: Dict[str, bool], home_idx: int) -> str:
    lines = [
        '# s1_switch_probe report',
        '',
        f'- time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        f'- home desktop: {home_idx}',
        f'- permissions of this process: {perms}',
        '- ms = time from posting the action until CGSGetActiveSpace equals the target space (poll 20 ms, timeout 3 s)',
        '',
        '| variant | works | ms | observed desktop | returned home | note |',
        '|---|---|---|---|---|---|',
    ]
    for r in results:
        ms = f'{r["ms"]:.0f}' if r['ms'] is not None else '-'
        lines.append(f'| {r["name"]} | {"yes" if r["ok"] else "no"} | {ms} | {r["observed_idx"]} | {r["returned"]} | {r["note"]} |')
    lines.append('')
    return '\n'.join(lines)


def print_report(path):
    print(f'report: {path}')


if __name__ == '__main__':
    main()
