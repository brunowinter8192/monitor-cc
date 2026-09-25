# INFRASTRUCTURE
import hashlib
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_MAIN_PORT = 18940
_WORKER_PORT = 18941
_UPSTREAM_PORT = 18942
_BODY = {'model': 'claude-opus-4-5', 'max_tokens': 8, 'messages': [{'role': 'user', 'content': 'worker sandbox ping'}]}
_MITMDUMP_SHIM = '#!/bin/bash\nexec "{python}" -c "from mitmproxy.tools.main import mitmdump; mitmdump()" "$@"\n'
_DRIVER = (
    'source "{script}"\n'
    '_worker_proxy_setup vproxy "{project}"\n'
    'rc=$?\n'
    'echo "RC=$rc"\n'
    'echo "PID=$WORKER_PROXY_PID"\n'
    'echo "LIVE_DIR=$WORKER_PROXY_LIVE_DIR"\n'
    'echo "LIVE_ADDON=$WORKER_PROXY_LIVE_ADDON"\n'
    '[ -n "$WORKER_PROXY_PID" ] && sleep 1\n'
    'exit $rc\n'
)

# ORCHESTRATOR

def worker_proxy_sandbox_workflow() -> None:
    iterative_dev_tree = _parse_args()
    _run_in_temp_dir(iterative_dev_tree)

# FUNCTIONS

def _parse_args() -> Path:
    return Path(sys.argv[1]).resolve()

def _run_in_temp_dir(iterative_dev_tree: Path) -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw).resolve()
        monitor_root = _build_monitor_root(tmp)
        project = _build_project(tmp)
        marker = _write_marker(project, monitor_root)
        bin_dir = _build_bin_dir(tmp)
        upstream = _start_upstream()
        try:
            outcome = _run_setup(iterative_dev_tree, project, monitor_root, bin_dir)
            answer = _probe_proxy(outcome)
            _stop_proxy(outcome)
        finally:
            upstream.shutdown()
            marker.unlink()
        _report(monitor_root, outcome, answer)

def _build_monitor_root(tmp: Path) -> Path:
    root = tmp / 'monitor-cc'
    shutil.copytree(_ROOT / 'src', root / 'src', ignore=shutil.ignore_patterns('logs', '__pycache__'))
    (root / 'src' / 'logs').mkdir()
    return root

def _build_project(tmp: Path) -> Path:
    project = tmp / 'project'
    project.mkdir()
    return project

def _write_marker(project: Path, monitor_root: Path) -> Path:
    session_id = hashlib.md5(str(project).encode()).hexdigest()[:8]
    marker = Path(f'/tmp/.monitor_cc_proxy_{session_id}')
    marker.write_text(f'{_MAIN_PORT}\n0\n{monitor_root}\n')
    return marker

def _build_bin_dir(tmp: Path) -> Path:
    bin_dir = tmp / 'bin'
    bin_dir.mkdir()
    shim = bin_dir / 'mitmdump'
    shim.write_text(_MITMDUMP_SHIM.format(python=sys.executable))
    shim.chmod(0o755)
    return bin_dir

def _start_upstream() -> http.server.HTTPServer:
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length', 0)))
            payload = json.dumps({'type': 'message', 'content': []}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass
    server = http.server.HTTPServer(('127.0.0.1', _UPSTREAM_PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server

def _run_setup(tree: Path, project: Path, monitor_root: Path, bin_dir: Path) -> dict:
    driver = _DRIVER.format(script=tree / 'src' / 'spawn' / 'worker_proxy.sh', project=project)
    home = bin_dir.parent / 'home'
    home.mkdir()
    env = {**os.environ, 'HOME': str(home), 'PATH': f'{bin_dir}:{os.environ["PATH"]}'}
    proc = subprocess.run(['bash', '-c', driver], capture_output=True, text=True, env=env, timeout=60)
    values = dict(line.split('=', 1) for line in proc.stdout.splitlines() if '=' in line)
    return {'rc': proc.returncode, 'values': values, 'stderr': proc.stderr.replace(str(monitor_root), '<ROOT>')}

def _probe_proxy(outcome: dict) -> str:
    if outcome['rc'] != 0:
        return 'skipped: setup failed'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({'http': f'http://127.0.0.1:{_WORKER_PORT}'}))
    request = urllib.request.Request(f'http://127.0.0.1:{_UPSTREAM_PORT}/v1/messages', data=json.dumps(_BODY).encode(),
                                     headers={'Content-Type': 'application/json', 'Host': 'api.anthropic.com'}, method='POST')
    with opener.open(request, timeout=20) as response:
        return response.read().decode()

def _stop_proxy(outcome: dict) -> None:
    pid = outcome['values'].get('PID', '')
    if pid:
        subprocess.run(['kill', pid], capture_output=True)

def _report(monitor_root: Path, outcome: dict, answer: str) -> None:
    dual_dir = monitor_root / 'src' / 'logs' / 'dual_log'
    files = sorted(p.name for p in dual_dir.glob('*')) if dual_dir.exists() else []
    live_dir = outcome['values'].get('LIVE_DIR', '')
    print(f'setup_rc={outcome["rc"]}')
    print(f'live_dir_src={sorted(p.name for p in (Path(live_dir) / "src").iterdir()) if live_dir and (Path(live_dir) / "src").exists() else None}')
    print(f'setup_stderr={outcome["stderr"].strip()[-400:]}')
    print(f'answer={answer}')
    print(f'dual_log_files={files}')
    sys.exit(0 if outcome['rc'] == 0 and files else 1)

if __name__ == '__main__':
    worker_proxy_sandbox_workflow()
