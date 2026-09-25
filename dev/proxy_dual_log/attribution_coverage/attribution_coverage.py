# INFRASTRUCTURE
import importlib.util
from datetime import datetime, timezone
from pathlib import Path

from attribution_coverage_analyse import _find_pairs, _analyse_all_pairs
from attribution_coverage_report import _build_report

_AREA_ROOT = next(p for p in Path(__file__).resolve().parents if p.name == 'proxy_dual_log')
_PROJECT_ROOT = _AREA_ROOT.parent.parent

_PROJECT_PARTS = _PROJECT_ROOT.parts
_MAIN_CHECKOUT_ROOT = Path(*_PROJECT_PARTS[:-3]) if len(_PROJECT_PARTS) >= 3 and _PROJECT_PARTS[-3] == '.claude' and _PROJECT_PARTS[-2] == 'worktrees' else _PROJECT_ROOT

_sv_path = _PROJECT_ROOT / "src" / "proxy" / "strip_vocab.py"
_sv_spec = importlib.util.spec_from_file_location("strip_vocab_local", _sv_path)
_sv_mod = importlib.util.module_from_spec(_sv_spec)
_sv_spec.loader.exec_module(_sv_mod)
attribute_chunk = _sv_mod.attribute_chunk

_dual_log_direct = _PROJECT_ROOT / "src" / "logs" / "dual_log"
_DUAL_LOG_DIR = _dual_log_direct if _dual_log_direct.exists() else _MAIN_CHECKOUT_ROOT / "src" / "logs" / "dual_log"
_REPORT_DIR = _AREA_ROOT / "attribution_coverage_reports"


# ORCHESTRATOR

def attribution_coverage_workflow() -> None:
    pairs = _find_pairs(_DUAL_LOG_DIR)
    if not pairs:
        raise_no_pairs_found()

    strip_stats, inject_stats, residuals, false_positives = _analyse_all_pairs(pairs, attribute_chunk)
    report = _build_report(strip_stats, inject_stats, residuals, false_positives, len(pairs))

    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d")
    report_path = compute_report_path(ts)
    report_path.write_text(report, encoding="utf-8")
    print(report_path)


# FUNCTIONS

def raise_no_pairs_found():
    raise RuntimeError(f"No stripped/injected pairs found in {_DUAL_LOG_DIR}")


def compute_report_path(ts):
    return _REPORT_DIR / f"{ts}.md"


if __name__ == "__main__":
    attribution_coverage_workflow()
