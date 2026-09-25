# INFRASTRUCTURE
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

_BG_FIXTURE = Path(__file__).resolve().parent / 'fixtures' / 'bg_escape_events_legacy_ts.jsonl'
_LEGACY = '2026-07-30T16:09:30.317412+00:00Z'
_NEW = '2026-07-30T16:09:30.317412+00:00'

# ORCHESTRATOR


def main():
    _run_sandboxed_checks()
    print('PASS')


# FUNCTIONS

def _run_sandboxed_checks() -> None:
    with tempfile.TemporaryDirectory() as tmp_root:
        os.environ['MONITOR_CC_ROOT'] = tmp_root
        os.environ['PROXY_LOG_ID'] = 'ts_probe_0'
        os.environ['PROXY_PROJECT_PATH'] = ''
        root = Path(tmp_root)
        _check_original_writer(root)
        _check_response_writer(root)
        _check_bg_escape_writer(root)
        _check_reader_local_datetime()
        _check_mixed_ordering()
        _check_bg_escape_janitor(root)
        _check_registry_sweep(root)


class _Headers(dict):
    def get(self, k, default=None):
        return super().get(k.lower(), default) if isinstance(k, str) else default


class _Request:
    headers = _Headers({'x-request-id': 'req-1'})


class _Response:
    status_code = 200
    headers = _Headers({'request-id': 'resp-1'})


class _Flow:
    request = _Request()
    response = _Response()
    id = 'flow-1'
    metadata = {}


def _assert_parses(label: str, value: str) -> None:
    parsed = datetime.fromisoformat(value)
    assert parsed.utcoffset() == timedelta(0), (label, value)
    assert not value.endswith('Z'), (label, value)
    print(f'{label} ts parses: {value}')


def _check_original_writer(root: Path) -> None:
    from src.proxy.addon_dual_log import _log_original_request
    log_file = root / 'original.jsonl'
    _log_original_request(log_file, _Flow(), {'model': 'x'})
    _assert_parses('original', json.loads(log_file.read_text())['timestamp'])


def _check_response_writer(root: Path) -> None:
    from src.proxy.addon import _write_response_entry
    log_file = root / 'response.jsonl'
    entry = _write_response_entry(_Flow(), log_file)
    assert entry is not None
    _assert_parses('response', json.loads(log_file.read_text())['timestamp'])


def _check_bg_escape_writer(root: Path) -> None:
    from src.proxy.bg_escape import _log_bg_escape_event, _resolve_bg_escape_log_file
    _log_bg_escape_event('fired', 'worker:x', 'task', 'sess', send_result=True)
    lines = _resolve_bg_escape_log_file().read_text().splitlines()
    assert len(lines) == 1, lines
    _assert_parses('bg_escape', json.loads(lines[0])['ts'])


def _check_reader_local_datetime() -> None:
    from src.dual_log_cli.reader import local_datetime
    assert local_datetime(_LEGACY) == local_datetime(_NEW)
    assert local_datetime(_LEGACY) is not None
    print('local_datetime: legacy and new value give the same instant')


def _check_mixed_ordering() -> None:
    base = datetime(2026, 9, 25, 10, 0, 0, 500000, tzinfo=timezone.utc)
    instants = [base + timedelta(seconds=i, microseconds=i * 7) for i in range(20)]
    legacy = [i.isoformat() + 'Z' for i in instants]
    new = [i.isoformat() for i in instants]
    mixed = [legacy[i] if i % 2 else new[i] for i in range(20)]
    assert sorted(mixed) == mixed
    assert sorted(legacy) == legacy and sorted(new) == new
    whole_second = datetime(2026, 9, 25, 10, 0, 0, tzinfo=timezone.utc)
    assert (whole_second.isoformat() + 'Z') < (whole_second.replace(microsecond=1).isoformat())
    print('mixed legacy/new values keep chronological lexical order (distinct instants)')


def _check_bg_escape_janitor(root: Path) -> None:
    from src.panes import log_janitor
    real = _BG_FIXTURE.read_text().splitlines(keepends=True)
    assert real and all(json.loads(l)['ts'].endswith('+00:00Z') for l in real)
    now = datetime.now(timezone.utc)
    fresh_legacy = json.dumps({'ts': now.isoformat() + 'Z', 'event': 'fired'}) + '\n'
    fresh_new = json.dumps({'ts': now.isoformat(), 'event': 'fired'}) + '\n'
    path = root / 'bg_escape_events.jsonl'
    path.write_text(''.join(real) + fresh_legacy + fresh_new)
    notes = []
    log_janitor.log_pane_note = lambda name, msg: notes.append(msg)
    log_janitor.cleanup_old_jsonl(path)
    assert path.read_text() == fresh_legacy + fresh_new, path.read_text()
    assert any(f'handled {len(real) + 1} lines with legacy ts suffix' in n for n in notes), notes
    assert not any('could not be parsed' in n for n in notes), notes
    print(f'bg_escape janitor: {len(real)} real old lines pruned, fresh legacy and new kept; notes {notes}')


def _check_registry_sweep(root: Path) -> None:
    from src.panes.log_janitor import sweep_eligible_specs
    specs = dict((spec.name, path) for spec, path in sweep_eligible_specs(root))
    assert set(specs) == {'hook_firing', 'api_errors', 'bg_escape_events'}, set(specs)
    assert specs['bg_escape_events'] == root / 'bg_escape_events.jsonl'
    print('sweep-eligible registry entries:', sorted(specs))


if __name__ == '__main__':
    main()
