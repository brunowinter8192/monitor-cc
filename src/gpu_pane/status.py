# INFRASTRUCTURE
import json
import logging
import os
import subprocess
import time
import urllib.request
from pathlib import Path

RAG_LOCKS_DIR = Path.home() / '.rag-locks'


# Discovered once per process via `rag-cli server presets --json`. Falls back to
# the legacy three-name list if rag-cli is missing or fails. Process is respawned
# by Monitor's Ctrl+R, which re-imports this module → new presets surface there.
def _discover_preset_names() -> list[str]:
    try:
        r = subprocess.run(
            ['rag-cli', 'server', 'presets', '--json'],
            capture_output=True, text=True, timeout=3,
        )
        if r.returncode == 0:
            payload = json.loads(r.stdout)
            return [p['name'] for p in payload]
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError, KeyError):
        pass
    return ['embedding', 'reranker', 'splade']  # legacy fallback


PRESET_NAMES = _discover_preset_names()

_last_anomalies: list[dict] = []  # reset each tick by all_statuses()
_legacy_warned: bool = False       # log legacy port-file warning once per session

_logger = logging.getLogger('gpu_pane')
if not _logger.handlers:
    _LOG_DIR = Path(__file__).parent / 'logs'
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        _fh = logging.FileHandler(_LOG_DIR / 'gpu_pane.log')
        _fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        _logger.addHandler(_fh)
    except OSError:
        pass
    _logger.setLevel(logging.WARNING)


# ORCHESTRATOR

# Return (preset_statuses, arbitrary_statuses). Anomalies logged to gpu_pane.log; readable via get_anomalies()
def all_statuses() -> tuple[list[dict], list[dict]]:
    global _last_anomalies
    _last_anomalies = []

    _check_legacy_files()

    states_by_name: dict[str, dict] = {}
    arbitrary: list[dict] = []

    for sf in RAG_LOCKS_DIR.glob('server-port-*.json'):
        try:
            state = json.loads(sf.read_text())
        except (json.JSONDecodeError, OSError):
            _warn('malformed_json', f'malformed state file: {sf}', str(sf))
            continue

        pid = state.get('pid')
        if pid is not None:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                _warn('dead_pid', f'stale state file: pid {pid} dead', str(sf))
                continue
            except PermissionError:
                pass  # PID alive, different owner

        name = state.get('name')
        if name in PRESET_NAMES:
            if name in states_by_name:
                _warn('duplicate_preset', f'duplicate preset name in state files: {name}', str(sf))
            else:
                states_by_name[name] = state
        else:
            arbitrary.append(state)

    preset_statuses = [_status_for_preset(n, states_by_name.get(n)) for n in PRESET_NAMES]
    arbitrary_statuses = [_status_for_state(s)
                          for s in sorted(arbitrary, key=lambda x: x.get('port', 0))]
    return preset_statuses, arbitrary_statuses


# FUNCTIONS

# Return anomalies from the last all_statuses() call
def get_anomalies() -> list[dict]:
    return list(_last_anomalies)


# Build stopped status for a preset (state=None) or delegate to _status_for_state
def _status_for_preset(name: str, state: dict | None) -> dict:
    if state is None:
        return {
            'name': name, 'kind': 'preset', 'running': False,
            'port': None, 'pid': None, 'rss_mb': None, 'healthy': False,
            'idle_seconds': None, 'idle_log_missing': False,
            'log_path': None, 'model_name': None,
        }
    return _status_for_state(state, kind='preset')


# Build display-ready status from a live state file dict
def _status_for_state(state: dict, kind: str = 'arbitrary') -> dict:
    port = state.get('port')
    pid = state.get('pid')
    log_path = state.get('log_path')

    idle_seconds = _log_idle(log_path)
    log_missing = bool(log_path and idle_seconds is None)
    if log_missing:
        _warn('missing_log', f'log file missing: {log_path}', str(log_path))

    return {
        'name': state.get('name') or f'port-{port}',
        'kind': kind,
        'running': True,
        'port': port,
        'pid': pid,
        'rss_mb': _read_rss_mb(pid),
        'healthy': _check_health_port(port),
        'idle_seconds': idle_seconds,
        'idle_log_missing': log_missing,
        'log_path': log_path,
        'model_name': state.get('model_name'),
    }


# Seconds since log mtime; None if log_path empty or file not found
def _log_idle(log_path: str | None) -> float | None:
    if not log_path:
        return None
    try:
        return time.time() - Path(log_path).stat().st_mtime
    except (FileNotFoundError, OSError):
        return None


# GET /health on port; True if 200, False on any error
def _check_health_port(port: int | None) -> bool:
    if port is None:
        return False
    try:
        req = urllib.request.Request(f'http://localhost:{port}/health')
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            return resp.status == 200
    except Exception:
        return False


# ps -o rss= for PID; return MB; None on failure
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


# Append anomaly to _last_anomalies and log warning (best-effort)
def _warn(kind: str, message: str, source: str) -> None:
    _last_anomalies.append({'kind': kind, 'message': message, 'source': source})
    try:
        _logger.warning(message)
    except Exception:
        pass


# Detect legacy rag-server-*.port files; add to anomalies; log once per session
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
