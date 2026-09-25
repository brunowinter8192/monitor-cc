# INFRASTRUCTURE
import importlib
import os
import subprocess
import sys
import tempfile
import types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))


# ORCHESTRATOR

def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == '--case':
        run_selected_case()
        print('PASS')
        return
    names = compute_names()
    results = collect_results(names)
    report(results)


# FUNCTIONS

def run_selected_case():
    globals()['case_' + sys.argv[2]]()


def compute_names():
    return sorted(n[len('case_'):] for n in globals() if n.startswith('case_'))


def collect_results(names):
    with ThreadPoolExecutor(max_workers=len(names)) as pool:
        results = list(pool.map(spawn_case, names))
    return results


def spawn_case(name: str) -> tuple:
    proc = subprocess.run([sys.executable, __file__, '--case', name], capture_output=True, text=True)
    return name, proc.returncode == 0, (proc.stdout + proc.stderr).strip().splitlines()[-1:]


def report(results: list) -> None:
    failed = [r for r in results if not r[1]]
    for name, ok, tail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ('' if ok else f'  {tail}'))
    print(f'{len(results) - len(failed)}/{len(results)} cases passed')
    sys.exit(1 if failed else 0)


def prepare(tmp: str) -> Path:
    os.environ['MONITOR_CC_ROOT'] = tmp
    os.environ['PROXY_LOG_ID'] = 'opus_probe_1'
    os.environ['PROXY_PROJECT_PATH'] = ''
    stub = types.ModuleType('mitmproxy')
    stub.http = types.SimpleNamespace(HTTPFlow=object, Request=object)
    sys.modules['mitmproxy'] = stub
    sys.modules['mitmproxy.http'] = stub.http
    return Path(tmp) / 'src' / 'logs' / 'proxy_error.log'


def entries(log: Path) -> list:
    if not log.exists():
        return []
    return [l for l in log.read_text().splitlines() if l.startswith('[') and '[monitor_root]' not in l and '] [' in l]


class FakeHeaders(dict):
    def get(self, key, default=None):
        return super().get(key.lower(), default)

    def pop(self, key, default=None):
        return dict.pop(self, key.lower(), default)


class FakeRequest:
    method = 'POST'
    pretty_host = 'api.anthropic.com'
    path = '/v1/messages'
    pretty_url = 'https://api.anthropic.com/v1/messages'

    def __init__(self, content: bytes, headers: dict = None):
        self.content = content
        self.headers = FakeHeaders(headers or {})


class FakeFlow:
    def __init__(self, request, response=None):
        self.id = 'flow-probe'
        self.request = request
        self.response = response
        self.metadata = {}


def case_log_entry_has_source_error_and_traceback() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = prepare(tmp)
        module = importlib.import_module('src.proxy.proxy_error_log')
        try:
            raise ValueError('probe failure')
        except ValueError as exc:
            module.log_proxy_error('probe.source', exc)
        module.log_proxy_error('probe.text', 'plain message')
        text = log.read_text()
        assert '[probe.source] ValueError: probe failure' in text and 'Traceback (most recent call last)' in text, text
        assert '[probe.text] plain message' in text and '[monitor_root] source=env' in text, text


def case_on_change_dedupes_and_clear_rearms() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = prepare(tmp)
        module = importlib.import_module('src.proxy.proxy_error_log')
        module.log_proxy_error_on_change('s', 'same')
        module.log_proxy_error_on_change('s', 'same')
        assert len(entries(log)) == 1, entries(log)
        module.log_proxy_error_on_change('s', 'different')
        assert len(entries(log)) == 2
        module.clear_proxy_error('s')
        module.log_proxy_error_on_change('s', 'different')
        assert len(entries(log)) == 3


def case_size_cap_keeps_tail() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = prepare(tmp)
        module = importlib.import_module('src.proxy.proxy_error_log')
        module.PROXY_ERROR_LOG_MAX_BYTES = 1000
        module.PROXY_ERROR_LOG_KEEP_BYTES = 300
        for i in range(30):
            module.log_proxy_error('cap', f'line {i:03d} ' + 'x' * 40)
        assert log.stat().st_size < 1000 + 200, log.stat().st_size
        assert 'line 029' in log.read_text()


def case_logger_failure_is_silent() -> None:
    prepare('/nonexistent')
    module = importlib.import_module('src.proxy.proxy_error_log')
    module.log_proxy_error('probe', 'no root directory')


def case_request_handler_logs_and_stays_fail_open() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = prepare(tmp)
        addon = importlib.import_module('src.proxy.addon').ProxyAddon()

        class Broken(FakeRequest):
            @property
            def path(self):
                raise RuntimeError('broken path')

        flow = FakeFlow(Broken(b'{"model": "x"}'))
        addon.request(flow)
        assert flow.request.content == b'{"model": "x"}'
        assert any('[addon.request flow=flow-probe] RuntimeError: broken path' in l for l in entries(log)), entries(log)


def case_response_hooks_log() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = prepare(tmp)
        addon = importlib.import_module('src.proxy.addon').ProxyAddon()

        class Broken(FakeRequest):
            @property
            def path(self):
                raise RuntimeError('broken path')

        flow = FakeFlow(Broken(b''))
        addon.responseheaders(flow)
        addon.response(flow)
        addon.error(flow)
        sources = [l.split(']')[1].strip(' [') for l in entries(log)]
        assert sources == ['addon.responseheaders flow=flow-probe', 'addon.response flow=flow-probe', 'addon.error flow=flow-probe'], sources


def case_decode_and_parse_bypass_is_traced() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = prepare(tmp)
        addon = importlib.import_module('src.proxy.addon')
        assert addon._decode_body(FakeRequest(b'not gzip', {'content-encoding': 'gzip'})) is None
        assert addon._parse_payload(b'{broken') is None
        text = '\n'.join(entries(log))
        assert 'addon._decode_body' in text and 'addon._parse_payload' in text, text


def case_dual_log_write_failures_are_traced() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = prepare(tmp)
        module = importlib.import_module('src.proxy.addon_dual_log')
        blocker = Path(tmp) / 'blocker'
        blocker.write_text('a file where a directory is needed')
        bad = blocker / 'x.jsonl'
        flow = FakeFlow(FakeRequest(b'{}'))
        module._log_original_request(bad, flow, {'model': 'm'})
        assert module._log_forwarded_delta(bad, {'model': 'm'}, flow, None) is None
        assert module._log_errors_entries(bad, {'messages': [{'role': 'user', 'content': [{'type': 'tool_result', 'is_error': True, 'tool_use_id': 't', 'content': 'e'}]}]}, 'r', 't', set(), 'main', 's', 'f') is None
        sources = [l.split(']')[1].strip(' [') for l in entries(log)]
        assert sources == ['addon_dual_log.original', 'addon_dual_log.forwarded', 'addon_dual_log.errors'], sources


def case_4xx_decode_failures_are_traced() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = prepare(tmp)
        module = importlib.import_module('src.proxy.addon_dual_log')

        class BadResponse:
            status_code = 429

            @property
            def content(self):
                raise ValueError('bad content')

        class BadRequest(FakeRequest):
            def __init__(self):
                self.headers = FakeHeaders()

            @property
            def content(self):
                raise ValueError('bad request content')

        flow = FakeFlow(BadRequest(), BadResponse())
        module._log_4xx_error(flow, Path(tmp) / 'src' / 'logs' / 'dual_log' / 'errors.jsonl')
        sources = [l.split(']')[1].strip(' [') for l in entries(log)]
        assert sources == ['addon_dual_log.4xx_response_body', 'addon_dual_log.4xx_request_payload', 'addon_dual_log.4xx'], sources
        assert (Path(tmp) / 'src' / 'logs' / 'api_errors.jsonl').exists()


def case_bg_escape_event_log_failure_is_traced() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = prepare(tmp)
        module = importlib.import_module('src.proxy.bg_escape')
        blocker = Path(tmp) / 'blocker'
        blocker.write_text('x')
        module._resolve_bg_escape_log_file = lambda: blocker / 'events.jsonl'
        module._log_bg_escape_event('skipped', 'main', 'id', '')
        assert any('[bg_escape.event_log]' in l for l in entries(log)), entries(log)


def case_poread_refusal_is_traced_once() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = prepare(tmp)
        module = importlib.import_module('src.proxy.inject_poread')
        marker = '<poread-export path="/nonexistent/probe.txt" bytes="10" sha256="' + 'a' * 16 + '"/>\n' + module.POREAD_NOTICE
        assert module._is_poread_marker_valid(marker, {}) is False
        assert module._is_poread_marker_valid(marker, {}) is False
        lines = [l for l in entries(log) if 'inject_poread /nonexistent/probe.txt' in l]
        assert len(lines) == 1 and 'source changed or unavailable' in lines[0], lines


def case_schema_store_missing_is_traced() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = prepare(tmp)
        module = importlib.import_module('src.proxy.tool_injection')
        module._SCHEMA_STORE_CACHE = None
        assert module._load_schema_store() == {}
        assert any('[tool_injection.schema_store] schema store missing at' in l for l in entries(log)), entries(log)


if __name__ == '__main__':
    main()
