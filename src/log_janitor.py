# INFRASTRUCTURE
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

_RETENTION = 7 * 86400


# FUNCTIONS

# Drop records older than 7 days from a JSONL file by 'ts' field; exception-safe; rewrites atomically
def cleanup_old_jsonl(path: Path) -> None:
    try:
        if not path.exists():
            return
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=_RETENTION)
        lines = path.read_text(encoding='utf-8').splitlines(keepends=True)
        kept = []
        for line in lines:
            if not line.strip():
                continue
            try:
                ts_raw = json.loads(line).get('ts', '')
                if ts_raw:
                    ts_dt = datetime.fromisoformat(ts_raw.replace('Z', '+00:00'))
                    if ts_dt < cutoff:   # TypeError if naive ts → caught below → keep
                        continue
            except Exception:  # unparseable ts or naive/aware mismatch → keep (fail-safe)
                pass
            kept.append(line)
        path.write_text(''.join(kept), encoding='utf-8')
    except Exception:  # janitor must never raise into the monitor event loop
        pass
