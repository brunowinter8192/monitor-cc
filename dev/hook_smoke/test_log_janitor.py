# INFRASTRUCTURE
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

# add src/ to path so log_janitor is importable without 'from src.' prefix
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))
from log_janitor import cleanup_old_jsonl  # noqa: E402

_now = datetime.now(timezone.utc)

def _ts(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')

# Case payloads — written as JSON lines, compared after cleanup
_OLD    = json.dumps({'ts': _ts(_now - timedelta(days=8)),  'hook': 'x', 'decision': 'block'})
_RECENT = json.dumps({'ts': _ts(_now - timedelta(days=1)),  'hook': 'x', 'decision': 'rewrite'})
_EMPTY  = json.dumps({'ts': '',                             'hook': 'x', 'decision': 'block'})
# Naive ts: 9 days old but no timezone suffix → fromisoformat returns naive datetime →
# comparison with UTC-aware cutoff raises TypeError → keep (fail-safe)
_NAIVE  = json.dumps({'ts': (_now - timedelta(days=9)).strftime('%Y-%m-%dT%H:%M:%S'), 'hook': 'x', 'decision': 'block'})

# (description, input_lines, expected_kept_lines)
CASES = [
    ('old record >7 days → dropped',       [_OLD],    []),
    ('recent record <7 days → kept',       [_RECENT], [_RECENT]),
    ('empty ts → kept (fail-safe)',        [_EMPTY],  [_EMPTY]),
    ('naive ts no TZ → kept (fail-safe)',  [_NAIVE],  [_NAIVE]),
]


# ORCHESTRATOR

# Run all cases and print results; exit 1 if any fail
def test_log_janitor_workflow() -> None:
    failures = []
    for desc, input_lines, expected in CASES:
        result, ok = _run_case(input_lines, expected)
        status = "OK  " if ok else "FAIL"
        print(f"  [{status}] {desc}")
        if not ok:
            print(f"           want: {expected}")
            print(f"           got:  {result}")
            failures.append(desc)
    print()
    if failures:
        print(f"FAILED: {len(failures)} case(s):")
        for desc in failures:
            print(f"  - {desc}")
        sys.exit(1)
    print(f"All {len(CASES)} tests passed.")


# FUNCTIONS

# Write input_lines to a temp file, run cleanup_old_jsonl, return (kept_lines, ok)
def _run_case(input_lines: list, expected: list) -> tuple:
    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.jsonl', delete=False, encoding='utf-8'
    ) as fh:
        tmp = Path(fh.name)
        for rec in input_lines:
            fh.write(rec + '\n')
    try:
        cleanup_old_jsonl(tmp)
        kept = [ln for ln in tmp.read_text(encoding='utf-8').splitlines() if ln.strip()]
        return kept, kept == expected
    finally:
        tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    test_log_janitor_workflow()
