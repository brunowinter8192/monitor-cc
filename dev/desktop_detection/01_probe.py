# INFRASTRUCTURE
from probe01_bridge import _CG
from probe01_pipeline import _collect_session_rows, _ghostty_pid, _read_cwd_uuid_map
from probe01_report import _print_detection_summary, _print_session_table, _print_space_overview

# ORCHESTRATOR

def probe_workflow() -> None:
    cwd_uuid = _read_cwd_uuid_map()
    if cwd_uuid is None:
        print("WARNING: ghostty_cwd_uuid.json missing — Menubar not running. "
              "Start Menubar and wait ~3s for map to populate.")
        return
    if not cwd_uuid:
        print("WARNING: ghostty_cwd_uuid.json is empty — no active Main sessions found.")
        return

    ghostty_pid_int = _ghostty_pid()
    if not ghostty_pid_int:
        print("ERROR: Ghostty not running.")
        return

    cid = _CG.CGSMainConnectionID()
    rows, space_map, active_space = _collect_session_rows(cid, cwd_uuid, ghostty_pid_int)

    _print_session_table(rows)
    _print_space_overview(space_map, active_space)
    _print_detection_summary(rows)


if __name__ == '__main__':
    probe_workflow()
