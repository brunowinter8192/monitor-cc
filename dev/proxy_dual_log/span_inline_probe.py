# INFRASTRUCTURE
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

_engine_path = Path(__file__).parents[2] / "src" / "proxy" / "diff_engine.py"
_spec = importlib.util.spec_from_file_location("diff_engine_probe", _engine_path)
diff_engine = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(diff_engine)
_diff_text = diff_engine._diff_text

from span_inline_probe_reconstruct import _load_jsonl, _reconstruct_chains, _match_requests
from span_inline_probe_blocks import _find_sys2_block, _find_sys3_block, _find_msg_wordlevel_block
from span_inline_probe_report import _build_report

LOG_DIR = Path(__file__).parents[5] / "src" / "logs" / "dual_log"
LOG_ID = "api_requests_opus_monitor_cc_1780517466"
REPORT_DIR = Path("dev/proxy_dual_log/span_inline_probe_reports")


# ORCHESTRATOR

def span_inline_probe_workflow() -> None:
    orig_path = LOG_DIR / f"{LOG_ID}_original.jsonl"
    fwd_path = LOG_DIR / f"{LOG_ID}_forwarded.jsonl"

    orig_entries = _load_jsonl(orig_path)
    fwd_entries = _load_jsonl(fwd_path)
    fwd_states = _reconstruct_chains(fwd_entries)
    matched = _match_requests(orig_entries, fwd_entries, fwd_states)

    b1 = _find_sys2_block(matched, _diff_text)
    b2 = _find_sys3_block(matched, _diff_text)
    b3 = _find_msg_wordlevel_block(matched, _diff_text)
    blocks = [b for b in [b1, b2, b3] if b is not None]

    lines = _build_report(blocks, LOG_ID)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    report_path = REPORT_DIR / f"{now.strftime('%Y%m%d')}.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    span_inline_probe_workflow()
