# INFRASTRUCTURE
from probe06_coteditor import _ensure_coteditor_running
from probe06_report import _print_headline, _print_result_table
from probe06_workflow import _load_primitive_symbols, _run_all_primitives, _setup_probe, _validate_preconditions

# ORCHESTRATOR

def probe_workflow() -> None:
    cid, ax, sc, space_map, active_space = _setup_probe()
    target_space = _validate_preconditions(cid, space_map, active_space)
    if target_space is None:
        return

    _ensure_coteditor_running()
    print()

    syms = _load_primitive_symbols()
    results = _run_all_primitives(cid, target_space, active_space, syms)

    _print_result_table(results)
    _print_headline(results, ax, sc)


if __name__ == '__main__':
    probe_workflow()
