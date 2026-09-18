# INFRASTRUCTURE
import time
from pathlib import Path
from typing import Dict, Optional

from probe04_bridge import _CG
from probe04_detection import _build_space_map, _ghostty_wids_all, _on_screen_wids, _spaces_for_wid
from probe04_move import _bridged_move, _take_screenshot

_REPORTS_DIR = Path(__file__).parent / "04_reports"

# FUNCTIONS

def _init_probe():
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts  = time.strftime("%Y%m%d_%H%M%S")
    cid = _CG.CGSMainConnectionID()
    return cid, ts

def _check_preconditions(cid: int) -> Optional[Dict]:
    space_map, active_space = _build_space_map(cid)
    active_desktop = space_map.get(active_space, ('?', '?'))[1]

    if len(space_map) < 2:
        print(f"PRECONDITION NOT MET: only {len(space_map)} Mission Control space — need >= 2")
        return None

    all_ghostty = _ghostty_wids_all()
    if not all_ghostty:
        print("PRECONDITION NOT MET: no named layer-0 Ghostty windows found")
        return None

    onscreen_before    = _on_screen_wids()
    off_screen_ghostty = all_ghostty - onscreen_before

    if not off_screen_ghostty:
        print("PRECONDITION NOT MET: all Ghostty windows are on active space — "
              "move a Ghostty window to a different desktop and retry")
        return None

    target_wid        = min(off_screen_ghostty)
    original_spaces   = _spaces_for_wid(cid, target_wid)
    original_space_id = original_spaces[0] if original_spaces else None
    original_desktop  = space_map.get(original_space_id, ('?', '?'))[1] if original_space_id else '?'

    return {
        'space_map': space_map, 'active_space': active_space, 'active_desktop': active_desktop,
        'target_wid': target_wid, 'original_space_id': original_space_id,
        'original_desktop': original_desktop, 'onscreen_before': onscreen_before,
    }

def _print_probe_header(state: Dict) -> None:
    print("=== Space-Move Probe (SLSBridgedMoveWindowsToManagedSpaceOperation) ===")
    print(f"  active_space  : {state['active_space']}  desktop {state['active_desktop']}")
    print(f"  target_wid    : {state['target_wid']}")
    print(f"  orig_space    : {state['original_space_id']}  desktop {state['original_desktop']}")
    print(f"  direction     : space {state['original_space_id']} -> {state['active_space']}"
          f"  (non-active -> active)")
    print(f"  all_spaces    : {sorted(state['space_map'].keys())}")
    print()

def _run_move_trial(cid: int, ts: str, state: Dict) -> Dict:
    target_wid       = state['target_wid']
    active_space     = state['active_space']
    onscreen_before  = state['onscreen_before']

    in_before   = target_wid in onscreen_before
    path_before = _REPORTS_DIR / f"04_before_move_{ts}.png"
    _take_screenshot(path_before)
    print(f"[BEFORE] wid {target_wid} in on-screen list : {in_before}  (expected: False)")
    print(f"[BEFORE] screenshot : {path_before.name}")

    print(f"\n  calling _bridged_move([{target_wid}], space={active_space}) ...")
    _bridged_move([target_wid], active_space)
    time.sleep(0.5)

    onscreen_after = _on_screen_wids()
    in_after       = target_wid in onscreen_after
    path_after     = _REPORTS_DIR / f"04_after_move_{ts}.png"
    _take_screenshot(path_after)
    print(f"[AFTER]  wid {target_wid} in on-screen list : {in_after}  (expected: True)")
    print(f"[AFTER]  screenshot : {path_after.name}")
    print(f"[AFTER]  on-screen delta: added={sorted(onscreen_after - onscreen_before)}")

    move_ok = (not in_before) and in_after
    print()
    if move_ok:
        print(f"RESULT: PASS -- wid {target_wid} absent-before={not in_before} present-after={in_after}")
    else:
        print(f"RESULT: FAIL -- wid {target_wid} absent-before={not in_before} present-after={in_after} "
              f"(expected both True)")

    return {
        'in_before': in_before, 'in_after': in_after,
        'path_before': path_before, 'path_after': path_after,
        'onscreen_after': onscreen_after, 'move_ok': move_ok,
    }

def _run_restore_phase(cid: int, ts: str, state: Dict) -> Dict:
    target_wid        = state['target_wid']
    original_space_id = state['original_space_id']

    print()
    restored     = False
    path_restore = None
    if original_space_id is not None:
        print(f"  restoring wid {target_wid} -> space {original_space_id} ...")
        _bridged_move([target_wid], original_space_id)
        time.sleep(0.5)
        onscreen_restore = _on_screen_wids()
        in_restore       = target_wid in onscreen_restore
        restored         = not in_restore
        path_restore     = _REPORTS_DIR / f"04_after_restore_{ts}.png"
        _take_screenshot(path_restore)
        print(f"[RESTORE] wid {target_wid} in on-screen list : {in_restore}  (expected: False)")
        print(f"[RESTORE] screenshot : {path_restore.name}")
        print(f"[RESTORE] window returned to original space  : {restored}")
    else:
        print("WARNING: original_space_id unknown -- window left on active space")

    return {'restored': restored, 'path_restore': path_restore}

def _write_final_summary(ts: str, state: Dict, trial: Dict, restore: Dict) -> None:
    print()
    print("=== Summary ===")
    print(f"  RESULT        : {'PASS' if trial['move_ok'] else 'FAIL'}")
    print(f"  on-screen     : before={trial['in_before']} -> after={trial['in_after']}")
    print(f"  screenshots   : {trial['path_before'].name}  {trial['path_after'].name}")
    print(f"  restored      : {restore['restored']}")

    dump_path = _REPORTS_DIR / f"04_onscreen_dump_{ts}.txt"
    dump_path.write_text(
        f"active_space={state['active_space']}  target_wid={state['target_wid']}"
        f"  orig_space={state['original_space_id']}\n"
        f"before ({len(state['onscreen_before'])} wids): {sorted(state['onscreen_before'])}\n"
        f"after  ({len(trial['onscreen_after'])} wids): {sorted(trial['onscreen_after'])}\n"
        f"delta  added={sorted(trial['onscreen_after'] - state['onscreen_before'])}"
        f"  removed={sorted(state['onscreen_before'] - trial['onscreen_after'])}\n",
        encoding="utf-8",
    )
    print(f"  dump          : {dump_path.name}")
