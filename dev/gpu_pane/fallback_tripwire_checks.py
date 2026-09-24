# INFRASTRUCTURE
import importlib
import json
import os
import stat
import sys
import tempfile
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from dev.refactoring.check_group import assert_checks
from dev.refactoring.strand_runner import strand_workflow

_PRESET_SHIM = 'echo \'[{"name": "embedding-8b"}, {"name": "reranker-0.6b"}]\''
_STRAND_NAMES = ['strand_presets', 'strand_state_files', 'strand_collections', 'strand_toggles']

# ORCHESTRATOR


def main():
    sys.exit(strand_workflow(globals(), __file__, _STRAND_NAMES, title='gpu_pane fallback tripwire checks'))


# FUNCTIONS


def strand_presets() -> None:
    workdir, status, _actions, _render, _locks = _setup()
    assert_checks(_preset_checks(status, workdir))


def strand_state_files() -> None:
    workdir, status, _actions, _render, locks = _setup()
    _set_rag_cli(workdir, _PRESET_SHIM)
    status.all_statuses()
    assert_checks(_state_file_checks(status, locks))


def strand_collections() -> None:
    workdir, status, _actions, render, _locks = _setup()
    assert_checks(_collections_checks(status, render, workdir))


def strand_toggles() -> None:
    workdir, _status, actions, _render, _locks = _setup()
    assert_checks(_toggle_checks(actions, workdir))


def _setup() -> tuple:
    workdir = Path(tempfile.mkdtemp(prefix='mcfix_gpu_'))
    pane_log = importlib.import_module('src.pane_error_log')
    pane_log.PANE_ERROR_LOG_PATH = str(workdir / 'pane_error.log')
    status = importlib.import_module('src.gpu_pane.status')
    actions = importlib.import_module('src.gpu_pane.gpu_actions')
    render = importlib.import_module('src.gpu_pane.gpu_render')
    locks = workdir / 'locks'
    locks.mkdir()
    status.RAG_LOCKS_DIR = locks
    return workdir, status, actions, render, locks


def _set_rag_cli(workdir: Path, body: str | None) -> None:
    shim = workdir / 'bin' / 'rag-cli'
    shim.parent.mkdir(exist_ok=True)
    if shim.exists():
        shim.unlink()
    if body is not None:
        shim.write_text('#!/bin/sh\n' + body + '\n')
        shim.chmod(shim.stat().st_mode | stat.S_IXUSR)
    os.environ['PATH'] = f'{workdir / "bin"}:/usr/bin:/bin'


def _notes(workdir: Path) -> list:
    path = workdir / 'pane_error.log'
    if not path.exists():
        return []
    return [ln for ln in path.read_text().splitlines() if '] [gpu] note:' in ln]


def _kinds(status) -> list:
    return [a['kind'] for a in status.get_anomalies()]


def _preset_checks(status, workdir: Path) -> list:
    identity = id(status.PRESET_NAMES)
    _set_rag_cli(workdir, None)
    status.all_statuses()
    absent_kinds = _kinds(status)
    absent_names = list(status.PRESET_NAMES)
    _set_rag_cli(workdir, _PRESET_SHIM)
    status.all_statuses()
    return [
        ('discovery with rag-cli absent yields an anomaly and no names', 'presets_unavailable' in absent_kinds and absent_names == []),
        ('discovery retried on the next tick fills PRESET_NAMES in place',
         status.PRESET_NAMES == ['embedding-8b', 'reranker-0.6b'] and id(status.PRESET_NAMES) == identity),
        ('anomaly is gone after successful discovery', 'presets_unavailable' not in _kinds(status)),
    ]


def _state_file_checks(status, locks: Path) -> list:
    (locks / 'server-port-1.json').write_text('{not json')
    (locks / 'server-port-2.json').write_text(json.dumps({'pid': os.getpid(), 'name': 'embedding-8b'}))
    (locks / 'server-port-3.json').write_text(json.dumps({'pid': os.getpid(), 'port': 3, 'name': 'reranker-0.6b'}))
    presets, arbitrary = status.all_statuses()
    kinds = _kinds(status)
    dir_path = locks / 'server-port-9.json'
    dir_path.mkdir()
    locks.chmod(0)
    try:
        status._state_file_idle(9)
        raised = False
    except PermissionError:
        raised = True
    finally:
        locks.chmod(0o755)
    return [
        ('malformed state file is a traced skip', 'malformed_json' in kinds),
        ('state file without a port is a traced skip', 'missing_port' in kinds),
        ('valid state file still becomes a preset status', [p['name'] for p in presets if p['running']] == ['reranker-0.6b']),
        ('no state without a port reaches the arbitrary list', arbitrary == []),
        ('_state_file_idle on a missing file returns None', status._state_file_idle(77) is None),
        ('_state_file_idle on a non-ENOENT OSError propagates', raised),
    ]


def _collections_checks(status, render, workdir: Path) -> list:
    _set_rag_cli(workdir, 'exit 2')
    failed = status._fetch_collections()
    before = len(_notes(workdir))
    status._fetch_collections()
    _set_rag_cli(workdir, 'echo \'[{"collection": "c", "chunks": 5}]\'')
    ok = status._fetch_collections()
    unavailable = '\n'.join(render._render_collections_block(None, 80))
    empty = '\n'.join(render._render_collections_block([], 80))
    return [
        ('failed collections fetch is None', failed is None),
        ('the failure is noted once per state change', before == 1 and len(_notes(workdir)) == 1 and 'rc=2' in _notes(workdir)[0]),
        ('successful fetch returns the list', ok == [{'collection': 'c', 'chunks': 5}]),
        ('None renders ? and not (none indexed)', '?' in unavailable and '(none indexed)' not in unavailable),
        ('empty list still renders (none indexed)', '(none indexed)' in empty),
    ]


def _toggle_checks(actions, workdir: Path) -> list:
    actions._toggle_state.clear()
    actions._toggle_state['embedding-8b'] = ('starting', time.time() - actions.TOGGLE_TIMEOUT - 5)
    actions._expire_toggle_states([], [])
    expired = 'embedding-8b' not in actions._toggle_state
    noted = any('embedding-8b starting expired' in n for n in _notes(workdir))
    actions._toggle_state['port-None'] = ('stopping', time.time())
    try:
        actions._expire_toggle_states([], [])
        raised = False
    except ValueError:
        raised = True
    actions._toggle_state.clear()
    return [
        ('timed-out toggle is removed', expired),
        ('timed-out toggle is noted', noted),
        ('a port-None toggle key raises', raised),
    ]


if __name__ == '__main__':
    main()
