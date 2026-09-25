# INFRASTRUCTURE
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

_MAIN_ERRORS_LOG = Path('/Users/brunowinter2000/Documents/ai/monitor-cc/src/logs/api_errors.jsonl')
_REAL_LINES = 5

# ORCHESTRATOR


def main():
    with tempfile.TemporaryDirectory() as tmp_root:
        os.environ['MONITOR_CC_ROOT'] = tmp_root
        os.environ['PROXY_LOG_ID'] = 'ts_probe_0'
        os.environ['PROXY_PROJECT_PATH'] = ''
        _check_writer_ts(Path(tmp_root))
        _check_janitor_real_lines(Path(tmp_root))
        _check_janitor_mixed(Path(tmp_root))
    print('PASS')


# FUNCTIONS

class _Headers(dict):
    def get(self, k, default=None):
        return super().get(k.lower(), default) if isinstance(k, str) else default


class _Req:
    pretty_url = 'https://api.anthropic.com/v1/messages'
    headers = _Headers()
    content = b'{"model": "x"}'


class _Resp:
    status_code = 429
    content = b'{"type": "error"}'


class _Flow:
    request = _Req()
    response = _Resp()
    id = 'flow-err'


def _check_writer_ts(root: Path) -> None:
    from src.proxy.addon_dual_log import _log_4xx_error
    errors_file = root / 'src' / 'logs' / 'dual_log' / 'x_errors.jsonl'
    _log_4xx_error(_Flow(), errors_file)
    written = (root / 'src' / 'logs' / 'api_errors.jsonl').read_text().splitlines()
    assert len(written) == 1, written
    ts = json.loads(written[0])['ts']
    parsed = datetime.fromisoformat(ts)
    assert parsed.utcoffset() == timedelta(0), ts
    print(f'writer ts parses: {ts}')


def _recorder(sink: list):
    return lambda name, msg: sink.append(msg)


def _real_lines() -> list:
    lines = []
    with open(_MAIN_ERRORS_LOG, 'r', encoding='utf-8') as f:
        for raw in f:
            lines.append(raw)
            if len(lines) == _REAL_LINES:
                break
    assert lines and all(json.loads(l)['ts'].endswith('+00:00Z') for l in lines)
    return lines


def _check_janitor_real_lines(root: Path) -> None:
    from src.panes import log_janitor
    lines = _real_lines()
    far_future = datetime.now(timezone.utc) + timedelta(days=3650)
    far_past = datetime.now(timezone.utc) - timedelta(days=3650)
    kept, unparsable, legacy = log_janitor._partition_lines(lines, far_future)
    assert (kept, unparsable, legacy) == ([], 0, _REAL_LINES), (len(kept), unparsable, legacy)
    kept, unparsable, legacy = log_janitor._partition_lines(lines, far_past)
    assert (len(kept), unparsable, legacy) == (_REAL_LINES, 0, _REAL_LINES)
    print(f'real legacy lines: {_REAL_LINES} parsed, all prunable by age, 0 unparsable')


def _check_janitor_mixed(root: Path) -> None:
    from src.panes import log_janitor
    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=30)).isoformat()
    fresh = now.isoformat()
    rows = [
        {'ts': old + 'Z', 'k': 'legacy_old'},
        {'ts': fresh + 'Z', 'k': 'legacy_fresh'},
        {'ts': old, 'k': 'new_old'},
        {'ts': fresh, 'k': 'new_fresh'},
        {'ts': 'garbage', 'k': 'bad'},
    ]
    path = root / 'api_errors.jsonl'
    path.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    notes = []
    log_janitor.log_pane_note = _recorder(notes)
    log_janitor.cleanup_old_jsonl(path)
    kept = [json.loads(l)['k'] for l in path.read_text().splitlines()]
    assert kept == ['legacy_fresh', 'new_fresh', 'bad'], kept
    assert any('handled 2 lines with legacy ts suffix' in n for n in notes), notes
    assert any('kept 1 lines whose ts could not be parsed' in n for n in notes), notes
    print(f'mixed prune kept {kept}; notes {notes}')


if __name__ == '__main__':
    main()
