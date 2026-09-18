# INFRASTRUCTURE
import json
from datetime import datetime
from pathlib import Path
from typing import Dict

_SCRIPT_DIR  = Path(__file__).resolve().parent
_REPORTS_DIR = _SCRIPT_DIR / '03_reports'

# FUNCTIONS

def _write_report(payload: Dict) -> Path:
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = _REPORTS_DIR / f'{payload["tag"]}_{ts}.json'
    path.write_text(json.dumps(payload, indent=2, default=str), encoding='utf-8')
    return path
