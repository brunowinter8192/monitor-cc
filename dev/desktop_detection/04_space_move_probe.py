# INFRASTRUCTURE
from probe04_workflow import _check_preconditions, _init_probe, _print_probe_header, _run_move_trial, _run_restore_phase, _write_final_summary

# ORCHESTRATOR

def probe_workflow() -> None:
    cid, ts = _init_probe()
    state = _check_preconditions(cid)
    if state is None:
        return
    _print_probe_header(state)
    trial = _run_move_trial(cid, ts, state)
    restore = _run_restore_phase(cid, ts, state)
    _write_final_summary(ts, state, trial, restore)


if __name__ == '__main__':
    probe_workflow()
