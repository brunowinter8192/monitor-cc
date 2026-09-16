# INFRASTRUCTURE
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, ".")

from groundtruth_spans_cases import (
    get_bug_case, get_text_block_replace_case, get_bg_exit_replace_case, get_multi_chunk_case,
)
from groundtruth_spans_report import (
    run_case, emit_summary_table, emit_case_detail, emit_fidelity_summary,
    emit_phantom_summary, emit_recording_gaps, emit_conclusion,
)

_AREA_ROOT = Path(__file__).resolve().parent
while _AREA_ROOT.name != 'proxy_dual_log':
    _AREA_ROOT = _AREA_ROOT.parent
REPORT_DIR = _AREA_ROOT / "groundtruth_message_spans_probe_reports"

# FUNCTIONS

def _emit_intro(emit) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    emit(f"# Ground-Truth Message Spans Probe — {ts}")
    emit()
    emit("Validates `build_message_spans(orig_text, fwd_text, stripped_chunks)` against")
    emit("`diff_text_word` (current production blind-diff) on real log data.")
    emit()
    emit("**Data source:** option (b) — re-run `apply_modification_rules` on `_original`")
    emit("dual-log payloads. Chunks come from `stripped_msg_removed` returned by rules.")
    emit("Mod payload vs forwarded payload match is verified per case (`mod_matches_fwd`).")
    emit()
    emit("**Block text level:** `_get_inner_text(block)` — `block[\"text\"]` for text blocks,")
    emit("`block[\"content\"]` for tool_result blocks. This is the level the proxy actually")
    emit("operates on. Production diff_engine uses `json.dumps(block)` for tool_result blocks;")
    emit("GT algorithm avoids JSON-escape mismatch by working at the inner content level.")


def _load_cases(emit) -> list:
    cases_raw = []
    try:
        cases_raw.append(get_bug_case())
    except Exception as ex:
        emit(f"\n⚠️ ERROR loading bug case: {ex}")
    try:
        cases_raw.append(get_text_block_replace_case())
    except Exception as ex:
        emit(f"\n⚠️ ERROR loading text_replace case: {ex}")
    try:
        cases_raw.append(get_bg_exit_replace_case())
    except Exception as ex:
        emit(f"\n⚠️ ERROR loading bg_replace case: {ex}")
    try:
        cases_raw.append(get_multi_chunk_case())
    except Exception as ex:
        emit(f"\n⚠️ ERROR loading large_sr case: {ex}")
    return cases_raw


# ORCHESTRATOR

def groundtruth_message_spans_probe_workflow():
    REPORT_DIR.mkdir(exist_ok=True)

    lines = []

    def emit(*parts):
        lines.append("".join(str(p) for p in parts) + "\n")

    _emit_intro(emit)
    cases_raw = _load_cases(emit)
    results = [run_case(c) for c in cases_raw]

    emit_summary_table(emit, results)
    for r in results:
        emit_case_detail(emit, r)
    emit_fidelity_summary(emit, results)
    emit_phantom_summary(emit, results)
    emit_recording_gaps(emit, results)
    emit_conclusion(emit)

    ts_file = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    report_path = REPORT_DIR / f"groundtruth_spans_{ts_file}.md"
    with open(report_path, "w") as fout:
        fout.writelines(lines)

    print(f"Report: {report_path}")


if __name__ == "__main__":
    groundtruth_message_spans_probe_workflow()
