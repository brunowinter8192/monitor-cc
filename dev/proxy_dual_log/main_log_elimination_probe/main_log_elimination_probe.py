# INFRASTRUCTURE
import argparse

from main_log_elimination_io import (
    _resolve_root, _resolve_paths, _check_paths, _load_jsonl, _load_main_log, _load_tool_errors,
)
from main_log_elimination_questions import _run_question_a, _run_question_b
from main_log_elimination_report import _write_report


# ORCHESTRATOR

def main():
    args = _cli()
    main_log_elimination_probe_workflow(args.session)


# FUNCTIONS

def _cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe: can _forwarded quartet replace the main log?"
    )
    parser.add_argument(
        "session",
        nargs="?",
        default="opus_monitor_cc_1780602018",
        help="Log session suffix, e.g. opus_monitor_cc_1780602018",
    )
    return parser.parse_args()


def main_log_elimination_probe_workflow(session: str) -> None:
    root = _resolve_root()
    paths = _resolve_paths(root, session)
    _check_paths(paths)

    main_entries = _load_main_log(paths["main"])
    fwd_entries = _load_jsonl(paths["fwd"])
    orig_entries = _load_jsonl(paths["orig"])
    tool_errors = _load_tool_errors(paths["tool_errors"], session)

    a_results = _run_question_a(main_entries, fwd_entries)
    b_results = _run_question_b(orig_entries, tool_errors)

    report_path = _write_report(session, paths, a_results, b_results)
    print(report_path)


if __name__ == '__main__':
    main()
