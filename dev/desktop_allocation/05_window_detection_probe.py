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
    active_desktop = compute_active_desktop(space_map, active_space)

    print("=== Window Detection Probe 05 ===")
    print_active_space(active_space, active_desktop)
    print_spaces(space_map)
    print_reports()
    print()

    win_types      = [_WIN_TMUX, _WIN_OSC2, _WIN_COT]
    trial_schedule = compute_trial_schedule()

    all_results = assign_values()
    print_win_types(win_types, trial_schedule, cid, space_map, all_results)

    _print_summary(all_results)


# FUNCTIONS

def compute_active_desktop(space_map, active_space):
    return space_map.get(active_space, ("?", "?"))[1]


def print_active_space(active_space, active_desktop):
    print(f"  active_space={active_space}  desktop={active_desktop}")


def print_spaces(space_map):
    print(f"  spaces: {sorted(space_map.keys())}")


def print_reports():
    print(f"  reports: {_REPORTS_DIR}")


def compute_trial_schedule():
    return [(1, True), (2, True), (3, False)]


def assign_values():
    all_results: List[dict] = []
    return all_results


def print_win_types(win_types, trial_schedule, cid, space_map, all_results):
    for win_type in win_types:
        if win_type == _WIN_COT:
            print("--- coteditor: warm-launch check ---")
            _ensure_coteditor_running()
        print(f"--- {win_type} ---")
        for trial_n, foreground in trial_schedule:
            r = _run_trial(cid, space_map, win_type, trial_n, foreground)
            all_results.append(r)
        print()


if __name__ == "__main__":
    probe_workflow()
