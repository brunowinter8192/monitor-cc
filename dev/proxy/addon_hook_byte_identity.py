"""
Byte-identity regression harness for the ProxyAddon HOOK METHODS themselves (request,
responseheaders, response) — proxy addon-split milestone (collaborator-object split of
ProxyAddon's 15 self.<attr> + request()/response() helper extraction). pipeline_byte_identity.py
covers the pure-function pipeline; this harness is the one that actually calls ProxyAddon(),
addon.request(), addon.responseheaders(), addon.response() — nothing else in dev/ does.

Constructs a real ProxyAddon with MONITOR_CC_ROOT pointed at a fresh temp dir, drives the three
hooks with a minimal fake mitmproxy flow (request: method/pretty_host/path/headers/content;
response: status_code/headers/content/stream; flow: metadata dict/id) over a bounded prefix of a
real *_original.jsonl, with x-request-id pinned per request (so uuid.uuid4() is never invoked —
no monkeypatch needed there) and timestamp-shaped JSONL fields ('timestamp'/'ts') normalized to a
fixed sentinel post-write, hashing the concatenated contents of all six dual-log files plus
captured stderr.

Usage (from project root):
    ./venv/bin/python dev/proxy/addon_hook_byte_identity.py

Prints one HASH line. Run before and after the src/proxy/addon.py split; the hash must match.
Never commits a log snapshot — only reads.
"""

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
_PREFIX_LINES = 60  # bounded prefix — an append-only source file's own prefix never changes
_TIMESTAMP_KEYS = ('timestamp', 'ts')
_DUAL_LOG_SUFFIXES = ('original', 'forwarded', 'stripped', 'injected', 'errors', 'response')

# ORCHESTRATOR


def main():
    orig_path = _source_log()
    payloads = _load_payloads(orig_path)
    proxy_addon_cls = _import_proxy_addon()
    with tempfile.TemporaryDirectory() as tmp_root:
        os.environ['MONITOR_CC_ROOT'] = tmp_root
        os.environ.pop('PROXY_LOG_ID', None)
        os.environ.pop('PROXY_SESSION_ID', None)
        os.environ['PROXY_PROJECT_PATH'] = ''
        stderr_buf = io.StringIO()
        with redirect_stderr(stderr_buf):
            _drive_addon(payloads, proxy_addon_cls)
        # tmp_root itself is a fresh random path every run (tempfile.TemporaryDirectory) — the
        # tool_injection "schema store missing" warning embeds it verbatim, so it must be
        # normalized out of stderr before hashing or the hash would never be reproducible.
        stderr_text = stderr_buf.getvalue().replace(tmp_root, '<TMP_ROOT>')
        digest = _hash_dual_logs(tmp_root, stderr_text)
    print(f'source: {orig_path.name}')
    print(f'payloads: {len(payloads)}')
    print(f'HASH: {digest}')


# FUNCTIONS

# Imported at THIS point — BEFORE MONITOR_CC_ROOT is repointed at a tempdir in main() below —
# because src/proxy/payload_helpers.py resolves its own sys.path insert from MONITOR_CC_ROOT
# (falling back to the real src/ only when the env var is unset at import time); importing early
# avoids resolving `constants` against an empty tempdir.
def _import_proxy_addon():
    from src.proxy.addon import ProxyAddon
    return ProxyAddon


# ADDON_HOOK_BYTE_IDENTITY_LOG overrides the source *_original.jsonl path — needed to pin a
# before/after comparison to the exact same bytes, same pitfall class as
# dev/proxy/pipeline_byte_identity.py's PROXY_PIPELINE_BYTE_IDENTITY_LOG (see its own docstring).
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
                continue
            payload = entry.get('payload')
            if isinstance(payload, dict):
                payloads.append(payload)
    return payloads


# Minimal fake mitmproxy header container — case-insensitive get/pop, same shape as the
# _FakeHeaders class in dev/native-model-start/p3_cache_breakpoints_probe.py and
# dev/bg_wakeup_id_line/p2_bg_escape_probe.py (reused here, extended with a response side).
class _FakeHeaders(dict):
    def get(self, k, default=None):
        return super().get(k.lower(), default) if isinstance(k, str) else default

    def pop(self, k, default=None):
        return dict.pop(self, k.lower(), default) if isinstance(k, str) else default


class _FakeRequest:
    def __init__(self, payload: dict, request_id: str):
        self.method = 'POST'
        self.pretty_host = 'api.anthropic.com'
        self.path = '/v1/messages'
        self.pretty_url = 'https://api.anthropic.com/v1/messages'
        self.headers = _FakeHeaders({'x-request-id': request_id})
        self.content = json.dumps(payload).encode('utf-8')


class _FakeResponse:
    def __init__(self, status_code: int, request_id: str):
        self.status_code = status_code
        self.headers = _FakeHeaders({
            'request-id': request_id,
            'anthropic-ratelimit-requests-remaining': '999',
        })
        self.content = b'{"type": "message"}'
        self.stream = False


class _FakeFlow:
    def __init__(self, payload: dict, flow_id: str, request_id: str):
        self.request = _FakeRequest(payload, request_id)
        self.response = None
        self.metadata = {}
        self.id = flow_id


# Drives every payload through request() + a 2xx responseheaders()/response() pair, plus one
# dedicated 4xx flow (reusing payloads[0]) to exercise the error-logging branch — its stderr line
# is part of the hashed signal; the api_errors.jsonl side write is out of scope (not one of the
# six dual-log files this harness hashes).
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


# Strip volatile timestamp-shaped fields so the hash is stable across runs made at different
# wall-clock times — everything else (including dict key ORDER, which real json.dumps(entry)
# writes to the JSONL byte-for-byte) stays part of the hashed signal.
def _normalize_for_hash(obj):
    if isinstance(obj, dict):
        return {k: ('<TS>' if k in _TIMESTAMP_KEYS else _normalize_for_hash(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_for_hash(v) for v in obj]
    return obj


def _hash_dual_logs(tmp_root: str, stderr_text: str) -> str:
    digest = hashlib.sha256()
    dual_log_dir = Path(tmp_root) / 'src' / 'logs' / 'dual_log'
    for suffix in _DUAL_LOG_SUFFIXES:
        path = dual_log_dir / f'api_requests_{suffix}.jsonl'
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


if __name__ == '__main__':
    main()
