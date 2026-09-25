# INFRASTRUCTURE
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from case_strands import case_runners, report_case, run_case_strands
from src.panes.log_janitor import cleanup_old_jsonl

_now = datetime.now(timezone.utc)

_TS_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
_OLD    = json.dumps({'ts': (_now - timedelta(days=8)).strftime(_TS_FORMAT),  'hook': 'x', 'decision': 'block'})
_RECENT = json.dumps({'ts': (_now - timedelta(days=1)).strftime(_TS_FORMAT),  'hook': 'x', 'decision': 'rewrite'})
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
    sys.exit(run_case_strands(globals(), __file__, case_runners(CASES, _check_case)))


# FUNCTIONS

def _check_case(case: tuple) -> None:
    desc, input_lines, expected = case
    result, ok = _run_case(input_lines, expected)
    report_case(desc, ok, '' if ok else f'\n           want: {expected}\n           got:  {result}')


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
