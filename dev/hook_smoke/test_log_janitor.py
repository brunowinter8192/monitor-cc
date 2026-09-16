# INFRASTRUCTURE
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src' / 'panes'))
from log_janitor import cleanup_old_jsonl

_now = datetime.now(timezone.utc)

def _ts(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')

_OLD    = json.dumps({'ts': _ts(_now - timedelta(days=8)),  'hook': 'x', 'decision': 'block'})
_RECENT = json.dumps({'ts': _ts(_now - timedelta(days=1)),  'hook': 'x', 'decision': 'rewrite'})
_EMPTY  = json.dumps({'ts': '',                             'hook': 'x', 'decision': 'block'})
_NAIVE  = json.dumps({'ts': (_now - timedelta(days=9)).strftime('%Y-%m-%dT%H:%M:%S'), 'hook': 'x', 'decision': 'block'})

CASES = [
    ('old record >7 days → dropped',       [_OLD],    []),
    ('recent record <7 days → kept',       [_RECENT], [_RECENT]),
    ('empty ts → kept (fail-safe)',        [_EMPTY],  [_EMPTY]),
    ('naive ts no TZ → kept (fail-safe)',  [_NAIVE],  [_NAIVE]),
]


# ORCHESTRATOR

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
