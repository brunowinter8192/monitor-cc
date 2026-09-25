# INFRASTRUCTURE
import hashlib
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stderr
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

_MAIN_LOG_DIR = Path('/Users/brunowinter2000/Documents/ai/monitor-cc/src/logs/dual_log')
_PREFIX_LINES = 60
_LOG_ID = 'opus_probe_0'
_TIMESTAMP_KEYS = ('timestamp', 'ts')
_DUAL_LOG_SUFFIXES = ('original', 'forwarded', 'stripped', 'injected', 'errors', 'response')

_SKIPPED_LINES = 0


# ORCHESTRATOR

def main():
    orig_path = _source_log()
    payloads = _load_payloads(orig_path)
    digest = collect_digest(payloads)
    print_source(orig_path)
    print_payloads(payloads)
    _report_skipped_lines()
    print_hash(digest)


# FUNCTIONS

def _source_log() -> Path:
    override = os.environ.get('ADDON_HOOK_BYTE_IDENTITY_LOG')
    if override:
        return Path(override)
    files = sorted(_MAIN_LOG_DIR.glob('*_original.jsonl'), key=lambda p: p.stat().st_mtime)
    if not files:
        raise SystemExit(f'no *_original.jsonl logs found under {_MAIN_LOG_DIR}')
    return files[-1]


def _load_payloads(orig_path: Path) -> list:
    payloads = []
    with open(orig_path, 'r', encoding='utf-8') as f:
        for i, raw_line in enumerate(f):
            if i >= _PREFIX_LINES:
                break
            line = raw_line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                _note_skipped_line()
                continue
            payload = entry.get('payload')
            if isinstance(payload, dict):
                payloads.append(payload)
    return payloads


def _note_skipped_line() -> None:
    global _SKIPPED_LINES
    _SKIPPED_LINES += 1


def collect_digest(payloads):
    with tempfile.TemporaryDirectory() as tmp_root:
        os.environ['MONITOR_CC_ROOT'] = tmp_root
        os.environ['PROXY_LOG_ID'] = _LOG_ID
        os.environ['PROXY_PROJECT_PATH'] = ''
        proxy_addon_cls = _import_proxy_addon()
        stderr_buf = io.StringIO()
        with redirect_stderr(stderr_buf):
            _drive_addon(payloads, proxy_addon_cls)
        stderr_text = stderr_buf.getvalue().replace(tmp_root, '<TMP_ROOT>')
        digest = _hash_dual_logs(tmp_root, stderr_text)
    return digest


def _import_proxy_addon():
    from src.proxy.addon import ProxyAddon
    return ProxyAddon


def _drive_addon(payloads: list, proxy_addon_cls) -> None:
    addon = proxy_addon_cls()
    for i, payload in enumerate(payloads):
        flow = _FakeFlow(payload, f'flow-{i}', f'req-{i}')
        addon.request(flow)
        flow.response = _FakeResponse(200, f'resp-{i}')
        addon.responseheaders(flow)
        addon.response(flow)

    err_flow = _FakeFlow(payloads[0], 'flow-err', 'req-err')
    addon.request(err_flow)
    err_flow.response = _FakeResponse(429, 'resp-err')
    addon.responseheaders(err_flow)
    addon.response(err_flow)


class _FakeFlow:
    def __init__(self, payload: dict, flow_id: str, request_id: str):
        self.request = _FakeRequest(payload, request_id)
        self.response = None
        self.metadata = {}
        self.id = flow_id


class _FakeRequest:
    def __init__(self, payload: dict, request_id: str):
        self.method = 'POST'
        self.pretty_host = 'api.anthropic.com'
        self.path = '/v1/messages'
        self.pretty_url = 'https://api.anthropic.com/v1/messages'
        self.headers = _FakeHeaders({'x-request-id': request_id})
        self.content = json.dumps(payload).encode('utf-8')


class _FakeHeaders(dict):
    def get(self, k, default=None):
        return super().get(k.lower(), default) if isinstance(k, str) else default

    def pop(self, k, default=None):
        return dict.pop(self, k.lower(), default) if isinstance(k, str) else default


class _FakeResponse:
    def __init__(self, status_code: int, request_id: str):
        self.status_code = status_code
        self.headers = _FakeHeaders({
            'request-id': request_id,
            'anthropic-ratelimit-requests-remaining': '999',
        })
        self.content = b'{"type": "message"}'
        self.stream = False


def _hash_dual_logs(tmp_root: str, stderr_text: str) -> str:
    digest = hashlib.sha256()
    dual_log_dir = Path(tmp_root) / 'src' / 'logs' / 'dual_log'
    for suffix in _DUAL_LOG_SUFFIXES:
        path = dual_log_dir / f'api_requests_{_LOG_ID}_{suffix}.jsonl'
        digest.update(f'==={suffix}==='.encode())
        if path.exists():
            with open(path, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    digest.update(json.dumps(_normalize_for_hash(entry), default=str).encode())
        else:
            digest.update(b'<MISSING>')
    digest.update(b'===stderr===')
    digest.update(stderr_text.encode())
    return digest.hexdigest()


def _normalize_for_hash(obj):
    if isinstance(obj, dict):
        return {k: ('<TS>' if k in _TIMESTAMP_KEYS else _normalize_for_hash(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_for_hash(v) for v in obj]
    return obj


def print_source(orig_path):
    print(f'source: {orig_path.name}')


def print_payloads(payloads):
    print(f'payloads: {len(payloads)}')


def _report_skipped_lines() -> None:
    print(f'skipped undecodable lines: {_SKIPPED_LINES}')


def print_hash(digest):
    print(f'HASH: {digest}')


if __name__ == '__main__':
    main()
