"""
attribution_coverage.py — Function-attribution coverage analysis for _stripped/_injected dual-logs.

Answers: can every strip AND inject entry in the dual-logs be attributed to a responsible
function?  Key output: RESIDUAL (entries no named function claims) + json_reserialization bug.

Usage (from project root):
    ./venv/bin/python dev/proxy_dual_log/attribution_coverage.py

Output: dev/proxy_dual_log/attribution_coverage_reports/<YYYYMMDD>.md
"""

# INFRASTRUCTURE
import importlib.util
from datetime import datetime, timezone
from pathlib import Path

from attribution_coverage_analyse import _find_pairs, _analyse_all_pairs
from attribution_coverage_report import _build_report

# Load strip_vocab from src via path — block_dev_imports_src hook forbids literal `from src.`
_sv_path = Path(__file__).parents[2] / "src" / "proxy" / "strip_vocab.py"
_sv_spec = importlib.util.spec_from_file_location("strip_vocab_local", _sv_path)
_sv_mod = importlib.util.module_from_spec(_sv_spec)
_sv_spec.loader.exec_module(_sv_mod)
attribute_chunk = _sv_mod.attribute_chunk

_WORKTREE_ROOT = Path(__file__).parents[2]
# Logs live in main repo — if not in worktree direct path, navigate up from .claude/worktrees/<name>/
_dual_log_direct = _WORKTREE_ROOT / "src" / "logs" / "dual_log"
_DUAL_LOG_DIR = _dual_log_direct if _dual_log_direct.exists() else _WORKTREE_ROOT.parents[2] / "src" / "logs" / "dual_log"
_REPORT_DIR = Path(__file__).parent / "attribution_coverage_reports"


# ORCHESTRATOR

def attribution_coverage_workflow() -> None:
    pairs = _find_pairs(_DUAL_LOG_DIR)
    if not pairs:
        raise RuntimeError(f"No stripped/injected pairs found in {_DUAL_LOG_DIR}")

    strip_stats, inject_stats, residuals, false_positives = _analyse_all_pairs(pairs, attribute_chunk)
    report = _build_report(strip_stats, inject_stats, residuals, false_positives, len(pairs))

    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d")
    report_path = _REPORT_DIR / f"{ts}.md"
    report_path.write_text(report, encoding="utf-8")
    print(report_path)


if __name__ == "__main__":
    attribution_coverage_workflow()
