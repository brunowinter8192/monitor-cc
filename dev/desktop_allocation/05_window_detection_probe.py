# INFRASTRUCTURE
from typing import List

from probe05_bridge import _CG
from probe05_detection import _WIN_COT, _WIN_OSC2, _WIN_TMUX, _build_space_map
from probe05_lifecycle import _ensure_coteditor_running
from probe05_trial import _REPORTS_DIR, _print_summary, _run_trial

# ORCHESTRATOR

def probe_workflow() -> None:
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    cid = _CG.CGSMainConnectionID()
    space_map, active_space = _build_space_map(cid)
    active_desktop = space_map.get(active_space, ("?", "?"))[1]

    print("=== Window Detection Probe 05 ===")
    print(f"  active_space={active_space}  desktop={active_desktop}")
    print(f"  spaces: {sorted(space_map.keys())}")
    print(f"  reports: {_REPORTS_DIR}")
    print()

    win_types      = [_WIN_TMUX, _WIN_OSC2, _WIN_COT]
    trial_schedule = [(1, True), (2, True), (3, False)]

    all_results: List[dict] = []
    for win_type in win_types:
        if win_type == _WIN_COT:
            print("--- coteditor: warm-launch check ---")
            _ensure_coteditor_running()
        print(f"--- {win_type} ---")
        for trial_n, foreground in trial_schedule:
            r = _run_trial(cid, space_map, win_type, trial_n, foreground)
            all_results.append(r)
        print()

    _print_summary(all_results)


if __name__ == "__main__":
    probe_workflow()
