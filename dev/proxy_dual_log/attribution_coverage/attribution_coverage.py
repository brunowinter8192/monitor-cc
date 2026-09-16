# INFRASTRUCTURE
import importlib.util
from datetime import datetime, timezone
from pathlib import Path

from attribution_coverage_analyse import _find_pairs, _analyse_all_pairs
from attribution_coverage_report import _build_report

_AREA_ROOT = Path(__file__).resolve().parent
while _AREA_ROOT.name != 'proxy_dual_log':
    _AREA_ROOT = _AREA_ROOT.parent
_PROJECT_ROOT = _AREA_ROOT.parent.parent


def _main_checkout_root(project_root: Path) -> Path:
    parts = project_root.parts
    if len(parts) >= 3 and parts[-3] == '.claude' and parts[-2] == 'worktrees':
        return Path(*parts[:-3])
    return project_root


_sv_path = _PROJECT_ROOT / "src" / "proxy" / "strip_vocab.py"
_sv_spec = importlib.util.spec_from_file_location("strip_vocab_local", _sv_path)
_sv_mod = importlib.util.module_from_spec(_sv_spec)
_sv_spec.loader.exec_module(_sv_mod)
attribute_chunk = _sv_mod.attribute_chunk

_dual_log_direct = _PROJECT_ROOT / "src" / "logs" / "dual_log"
_DUAL_LOG_DIR = _dual_log_direct if _dual_log_direct.exists() else _main_checkout_root(_PROJECT_ROOT) / "src" / "logs" / "dual_log"
_REPORT_DIR = _AREA_ROOT / "attribution_coverage_reports"


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
