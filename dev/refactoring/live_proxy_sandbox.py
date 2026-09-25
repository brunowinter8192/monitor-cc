# INFRASTRUCTURE
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_MITMDUMP_CODE = 'from mitmproxy.tools.main import mitmdump; mitmdump()'
_PROXY_PORT = 18931
_UPSTREAM_PORT = 18932
_BODY = {'model': 'claude-opus-4-5', 'max_tokens': 8, 'messages': [{'role': 'user', 'content': 'sandbox ping'}]}

# ORCHESTRATOR

def live_proxy_sandbox_workflow() -> None:
    _run_in_temp_dir()

# FUNCTIONS

def _run_in_temp_dir() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw).resolve()
        shim = _build_live_layout(tmp)
        upstream = _start_upstream()
        proc = _start_mitmdump(tmp, shim)
        answer = _send_request()
        _stop_mitmdump(proc)
        upstream.shutdown()
        _report(tmp, answer, proc)

def _build_live_layout(tmp: Path) -> Path:
    log_dir = tmp / 'src' / 'logs'
    live_src = log_dir / '.proxy_live_sbx' / 'src'
    live_src.mkdir(parents=True)
    shim = log_dir / '.proxy_addon_live_sbx.py'
    shutil.copy(_ROOT / 'src' / 'proxy_addon.py', shim)
    for name in ('__init__.py', 'constants.py', 'monitor_root.py'):
        shutil.copy(_ROOT / 'src' / name, live_src / name)
    shutil.copytree(_ROOT / 'src' / 'proxy', live_src / 'proxy', ignore=shutil.ignore_patterns('__pycache__'))
    return shim

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

def _start_mitmdump(tmp: Path, shim: Path) -> subprocess.Popen:
    env = {k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}
    env.update({'MONITOR_CC_ROOT': str(tmp), 'PROXY_SESSION_ID': 'sbx', 'PROXY_LOG_ID': 'opus_sbx_1', 'PROXY_PROJECT_PATH': str(tmp)})
    proc = subprocess.Popen([sys.executable, '-c', _MITMDUMP_CODE, '-p', str(_PROXY_PORT), '-s', str(shim), '--set', 'flow_detail=0', '-q'],
                            env=env, cwd='/', stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(4)
    return proc

def _send_request() -> str:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({'http': f'http://127.0.0.1:{_PROXY_PORT}'}))
    request = urllib.request.Request(f'http://127.0.0.1:{_UPSTREAM_PORT}/v1/messages', data=json.dumps(_BODY).encode(),
                                     headers={'Content-Type': 'application/json', 'Host': 'api.anthropic.com'}, method='POST')
    with opener.open(request, timeout=20) as response:
        return response.read().decode()

def _stop_mitmdump(proc: subprocess.Popen) -> None:
    proc.terminate()
    proc.wait(timeout=15)

def _report(tmp: Path, answer: str, proc: subprocess.Popen) -> None:
    dual_dir = tmp / 'src' / 'logs' / 'dual_log'
    files = sorted(p.name for p in dual_dir.glob('*')) if dual_dir.exists() else []
    error_log = tmp / 'src' / 'logs' / 'proxy_error.log'
    print(f'answer={answer}')
    print(f'dual_log_files={files}')
    print(f'proxy_error_log={error_log.read_text() if error_log.exists() else None}')
    print(f'mitmdump_stderr={proc.stderr.read()[-600:]}')
    sys.exit(0 if files else 1)

if __name__ == '__main__':
    live_proxy_sandbox_workflow()
