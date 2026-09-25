# INFRASTRUCTURE
import json
import logging
import os
from logging.handlers import TimedRotatingFileHandler
import subprocess
import time
import urllib.request
from pathlib import Path

from src.pane_error_log import log_pane_error, log_pane_note

RAG_LOCKS_DIR = Path.home() / '.rag-locks'


PRESET_NAMES: list[str] = []

_last_anomalies: list[dict] = []
_preset_failure: str | None = None
_collections_failure: str | None = None
_legacy_warned: bool = False

_SKIP = object()

_logger = logging.getLogger('gpu_pane')


# ORCHESTRATOR

def all_statuses() -> tuple[list[dict], list[dict]]:
    _reset_anomalies()
    _check_legacy_files()
    _ensure_preset_names()
    states_by_name, arbitrary = _load_states()
    return _build_statuses(states_by_name, arbitrary)

# FUNCTIONS

def _reset_anomalies() -> None:
    global _last_anomalies
    _last_anomalies = []

def _check_legacy_files() -> None:
    global _legacy_warned
    legacy = list(RAG_LOCKS_DIR.glob('rag-server-*.port'))
    if not legacy:
        return
    for lf in legacy:
        _last_anomalies.append({'kind': 'legacy_file',
                                'message': f'legacy port file: {lf} (delete after Phase 5)',
                                'source': str(lf)})
    if not _legacy_warned:
        _legacy_warned = True
        try:
            _logger.warning(
                f'legacy port file(s): {[str(f) for f in legacy]} (delete after Phase 5)')
        except Exception:
            pass

def _ensure_preset_names() -> None:
    global _preset_failure
    if PRESET_NAMES:
        return
    try:
        PRESET_NAMES[:] = _discover_preset_names()
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError, KeyError, RuntimeError) as exc:
        cause = f'{type(exc).__name__}: {exc}'
        _last_anomalies.append({'kind': 'presets_unavailable', 'message': f'preset discovery failed: {cause}',
                                'source': 'rag-cli server presets'})
        if cause != _preset_failure:
            _logger.warning(f'preset discovery failed: {cause}')
        _preset_failure = cause
        return
    _preset_failure = None

def _discover_preset_names() -> list[str]:
    r = subprocess.run(
        ['rag-cli', 'server', 'presets', '--json'],
        capture_output=True, text=True, timeout=3,
    )
    if r.returncode != 0:
        raise RuntimeError(f'rc={r.returncode}')
    return [p['name'] for p in json.loads(r.stdout)]

def _load_states() -> tuple:
    states_by_name: dict[str, dict] = {}
    arbitrary: list[dict] = []
    for sf in RAG_LOCKS_DIR.glob('server-port-*.json'):
        state = _load_valid_state(sf)
        if state is not _SKIP:
            _classify_state(state, sf, states_by_name, arbitrary)
    return states_by_name, arbitrary

def _load_valid_state(sf: Path):
    state = _read_state_file(sf)
    if state is _SKIP:
        return _SKIP
    if not isinstance(state.get('port'), int):
        _warn('missing_port', f'state file without integer port: {sf}', str(sf))
        return _SKIP
    if _pid_is_dead(state.get('pid'), sf):
        return _SKIP
    return state

def _read_state_file(sf: Path):
    try:
        return json.loads(sf.read_text())
    except (json.JSONDecodeError, OSError):
        _warn('malformed_json', f'malformed state file: {sf}', str(sf))
        return _SKIP

def _warn(kind: str, message: str, source: str) -> None:
    _last_anomalies.append({'kind': kind, 'message': message, 'source': source})
    try:
        _logger.warning(message)
    except Exception:
        pass

def _pid_is_dead(pid, sf: Path) -> bool:
    if pid is not None:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            _warn('dead_pid', f'stale state file: pid {pid} dead', str(sf))
            return True
        except PermissionError: pass
    return False

def _classify_state(state: dict, sf: Path, states_by_name: dict, arbitrary: list) -> None:
    name = state.get('name')
    if name in PRESET_NAMES:
        if name in states_by_name:
            _warn('duplicate_preset', f'duplicate preset name in state files: {name}', str(sf))
        else:
            states_by_name[name] = state
    else:
        arbitrary.append(state)

def _build_statuses(states_by_name: dict, arbitrary: list) -> tuple:
    preset_statuses = [_status_for_preset(n, states_by_name.get(n)) for n in PRESET_NAMES]
    arbitrary_statuses = [_status_for_state(s)
                          for s in sorted(arbitrary, key=lambda x: x.get('port', 0))]
    return preset_statuses, arbitrary_statuses

def _status_for_preset(name: str, state: dict | None) -> dict:
    if state is None:
        return {
            'name': name, 'kind': 'preset', 'running': False,
            'port': None, 'pid': None, 'rss_mb': None, 'healthy': False,
            'idle_seconds': None, 'idle_log_missing': False,
            'log_path': None, 'model_name': None,
        }
    return _status_for_state(state, kind='preset')

def _status_for_state(state: dict, kind: str = 'arbitrary') -> dict:
    port = state.get('port')
    pid = state.get('pid')
    log_path = state.get('log_path')

    idle_seconds = _state_file_idle(port)
    state_missing = bool(port is not None and idle_seconds is None)
    if state_missing:
        _warn('missing_state_file',
              f'state file missing for port {port}',
              f'server-port-{port}.json')

    return {
        'name': state.get('name') or f'port-{port}',
        'kind': kind,
        'running': True,
        'port': port,
        'pid': pid,
        'rss_mb': _read_rss_mb(pid),
        'healthy': _check_health_port(port),
        'idle_seconds': idle_seconds,
        'idle_state_missing': state_missing,
        'log_path': log_path,
        'model_name': state.get('model_name'),
    }

def _state_file_idle(port: int | None) -> float | None:
    if port is None:
        return None
    try:
        return time.time() - (RAG_LOCKS_DIR / f'server-port-{port}.json').stat().st_mtime
    except FileNotFoundError:
        return None

def _read_rss_mb(pid: int | None) -> int | None:
    if pid is None:
        return None
    try:
        r = subprocess.run(['ps', '-o', 'rss=', '-p', str(pid)],
                           capture_output=True, text=True, timeout=3)
        if r.returncode == 0 and r.stdout.strip():
            return round(int(r.stdout.strip()) / 1024)
    except Exception:
        pass
    return None

def _check_health_port(port: int | None) -> bool:
    if port is None:
        return False
    try:
        req = urllib.request.Request(f'http://localhost:{port}/health')
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            return resp.status == 200
    except Exception:
        return False

def _configure_logger() -> None:
    if not _logger.handlers:
        _LOG_DIR = Path(__file__).parent / 'logs'
        try:
            _LOG_DIR.mkdir(parents=True, exist_ok=True)
            _fh = TimedRotatingFileHandler(_LOG_DIR / 'gpu_pane.log', when='d', interval=1, backupCount=7)
            _fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
            _logger.addHandler(_fh)
        except OSError:
            log_pane_error('gpu_status')
        _logger.setLevel(logging.WARNING)

def get_anomalies() -> list[dict]:
    return list(_last_anomalies)

def _fetch_collections() -> list[dict] | None:
    global _collections_failure
    try:
        r = subprocess.run(
            ['rag-cli', 'list_collections', '--json'],
            capture_output=True, text=True, timeout=5,
        )
        cause = None if r.returncode == 0 else f'rc={r.returncode}'
        collections = json.loads(r.stdout) if cause is None else None
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        cause = type(exc).__name__
        collections = None
    if cause != _collections_failure and cause is not None:
        log_pane_note('gpu', f'collections unavailable: {cause}')
    _collections_failure = cause
    return collections

_configure_logger()
