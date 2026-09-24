# INFRASTRUCTURE
import argparse
import subprocess
import time
from datetime import datetime
from typing import Dict, List, Optional

from dev.session_launcher.space_lib import (
    DESKTOP_METHODS,
    active_space,
    ghostty_window_ids,
    permission_state,
    return_home,
    space_ids,
    spaces_for_window,
    wait_active,
    write_report,
)

_CYCLES = 5
_VARIANTS = ('no_activate', 'activate')
_SETTLE_SECONDS = 1.0
_WINDOW_TIMEOUT = 5.0
_POLL_INTERVAL = 0.02

# ORCHESTRATOR

def main() -> None:
    args = _parse_args()
    home_space = active_space()
    ids = space_ids()
    home_idx = ids.index(home_space) + 1
    targets = _target_sequence(home_idx, args.cycles)
    perms = permission_state()
    results = []
    for variant in _VARIANTS:
        for cycle, target_idx in enumerate(targets, start=1):
            result = _run_cycle(variant, cycle, target_idx, home_space, ids, args.method)
            results.append(result)
            print(_format_console(result), flush=True)
            if not result['closed'] or not result['returned']:
                print(f'ABORT: closed={result["closed"]} returned={result["returned"]} new_window={result["new_wid"]}')
                path = write_report(__file__, _build_report(results, perms, home_idx, args.method))
                print(f'report: {path}')
                return
    path = write_report(__file__, _build_report(results, perms, home_idx, args.method))
    print(f'report: {path}')

# FUNCTIONS

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument('--method', required=True, choices=sorted(DESKTOP_METHODS))
    p.add_argument('--cycles', type=int, default=_CYCLES)
    return p.parse_args()

def _target_sequence(home_idx: int, cycles: int) -> List[int]:
    others = [d for d in range(1, 6) if d != home_idx]
    return [others[i % len(others)] for i in range(cycles)]

def _new_window_script(variant: str) -> str:
    activate = '  activate\n' if variant == 'activate' else ''
    return (
        'tell application "Ghostty"\n'
        f'{activate}'
        '  set win to new window\n'
        '  return id of win\n'
        'end tell'
    )

def _create_window(variant: str) -> Optional[str]:
    r = subprocess.run(['osascript', '-e', _new_window_script(variant)], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=15)
    if r.returncode != 0:
        return None
    return r.stdout.strip()

def _wait_new_cg_window(before: List[int]) -> Optional[int]:
    t0 = time.monotonic()
    while time.monotonic() - t0 < _WINDOW_TIMEOUT:
        new = [w for w in ghostty_window_ids() if w not in before]
        if new:
            return new[0]
        time.sleep(_POLL_INTERVAL)
    return None

def _close_window(as_id: str, cg_wid: Optional[int]) -> bool:
    script = f'tell application "Ghostty" to close (first window whose id is "{as_id}")'
    subprocess.run(['osascript', '-e', script], capture_output=True, text=True,
                   encoding='utf-8', errors='replace', timeout=15)
    if cg_wid is None:
        return False
    t0 = time.monotonic()
    while time.monotonic() - t0 < _WINDOW_TIMEOUT:
        if cg_wid not in ghostty_window_ids():
            return True
        time.sleep(_POLL_INTERVAL)
    return False

def _desktop_of_space(space: int, ids: List[int]) -> Optional[int]:
    return ids.index(space) + 1 if space in ids else None

def _observe_window(cg_wid: int, ids: List[int]) -> Dict[str, object]:
    spaces = spaces_for_window(cg_wid)
    return {
        'window_desktops': [_desktop_of_space(s, ids) for s in spaces],
        'onscreen': cg_wid in ghostty_window_ids(onscreen_only=True),
    }

def _run_cycle(variant: str, cycle: int, target_idx: int, home_space: int, ids: List[int], method: str) -> dict:
    target_space = ids[target_idx - 1]
    DESKTOP_METHODS[method](target_idx)
    switch_ms = wait_active(target_space)
    time.sleep(_SETTLE_SECONDS)
    before = ghostty_window_ids()
    t0 = time.monotonic()
    as_id = _create_window(variant)
    script_ms = (time.monotonic() - t0) * 1000
    active_after_script = _desktop_of_space(active_space(), ids)
    cg_wid = _wait_new_cg_window(before) if as_id is not None else None
    visible_ms = (time.monotonic() - t0) * 1000 if cg_wid is not None else None
    observed = _observe_window(cg_wid, ids) if cg_wid is not None else {'window_desktops': None, 'onscreen': None}
    time.sleep(_SETTLE_SECONDS)
    active_after_settle = _desktop_of_space(active_space(), ids)
    closed = _close_window(as_id, cg_wid) if as_id is not None else True
    returned = return_home(home_space, [method])
    return {'variant': variant, 'cycle': cycle, 'target_idx': target_idx, 'switch_ms': switch_ms,
            'as_id': as_id, 'new_wid': cg_wid, 'script_ms': script_ms, 'visible_ms': visible_ms,
            'window_desktops': observed['window_desktops'], 'onscreen': observed['onscreen'],
            'active_after_script': active_after_script, 'active_after_settle': active_after_settle,
            'closed': closed, 'returned': returned}

def _format_console(r: dict) -> str:
    return (f'{r["variant"]} #{r["cycle"]} target={r["target_idx"]} switch_ms={r["switch_ms"]} new_wid={r["new_wid"]} '
            f'window_desktops={r["window_desktops"]} active_after_script={r["active_after_script"]} '
            f'closed={r["closed"]} returned={r["returned"]}')

def _fmt_ms(v: Optional[float]) -> str:
    return f'{v:.0f}' if v is not None else '-'

def _build_report(results: List[dict], perms: Dict[str, bool], home_idx: int, method: str) -> str:
    lines = [
        '# s2_ghostty_window_probe report',
        '',
        f'- time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        f'- home desktop: {home_idx}',
        f'- switch method: {method}',
        f'- permissions of this process: {perms}',
        '- window desktop: CGSCopySpacesForWindows of the new CG window mapped to desktop index',
        '- hit = window desktop equals target desktop and window is on screen',
        '',
        '| variant | # | target | switch ms | script ms | visible ms | window desktop | onscreen | hit | active after script | active after settle | closed | returned |',
        '|---|---|---|---|---|---|---|---|---|---|---|---|---|',
    ]
    for r in results:
        hit = r['window_desktops'] == [r['target_idx']] and r['onscreen'] is True
        lines.append(
            f'| {r["variant"]} | {r["cycle"]} | {r["target_idx"]} | {_fmt_ms(r["switch_ms"])} | {_fmt_ms(r["script_ms"])} '
            f'| {_fmt_ms(r["visible_ms"])} | {r["window_desktops"]} | {r["onscreen"]} | {"yes" if hit else "no"} '
            f'| {r["active_after_script"]} | {r["active_after_settle"]} | {r["closed"]} | {r["returned"]} |')
    lines.append('')
    return '\n'.join(lines)

if __name__ == '__main__':
    main()
