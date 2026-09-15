# INFRASTRUCTURE
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

_SCRIPT_DIR  = Path(__file__).resolve().parent
_REPORTS_DIR = _SCRIPT_DIR / '02_reports'

# FUNCTIONS

# Write report JSON to _REPORTS_DIR/<tag>_<YYYYMMDD_HHMMSS>.json
def _write_report(
    tag: str, ctx: Dict, tcc: Dict, det: Dict, raw: List[Dict]
) -> Path:
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = _REPORTS_DIR / f'{tag}_{ts}.json'
    path.write_text(
        json.dumps({'tag': tag, 'timestamp': datetime.now().isoformat(),
                    'context_diagnostics': ctx, 'tcc_state': tcc,
                    'detection_result': det, 'raw_windows': raw},
                   indent=2, default=str),
        encoding='utf-8')
    return path
