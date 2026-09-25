# INFRASTRUCTURE
import json
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


def prepare(tmp: str, log_id: str = 'opus_probe_1') -> Path:
    os.environ['MONITOR_CC_ROOT'] = tmp
    os.environ.pop('PROXY_LOG_ID', None)
    os.environ.pop('PROXY_SESSION_ID', None)
    if log_id:
        os.environ['PROXY_LOG_ID'] = log_id
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


def raises(exc_type, fn) -> str:
    try:
        fn()
    except exc_type as exc:
        return str(exc)
    raise AssertionError(f'{exc_type.__name__} not raised')


def case_missing_log_id_raises_at_addon_import() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        prepare(tmp, log_id='')
        os.environ['PROXY_SESSION_ID'] = 'abcd1234'
        message = raises(RuntimeError, lambda: importlib.import_module('src.proxy.addon'))
        assert message == 'PROXY_LOG_ID is not set', message


def case_worker_context_parsing() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        prepare(tmp)
        addon = importlib.import_module('src.proxy.addon')
        for log_id, expected in (
            ('worker_deadbeef_isolation-check_1785000000', 'worker:isolation-check'),
            ('worker_deadbeef_name_with_underscores_1785000000', 'worker:name_with_underscores'),
            ('opus_monitor_cc_1785336796', 'main'),
        ):
            os.environ['PROXY_LOG_ID'] = log_id
            assert addon._derive_worker_context() == expected, (log_id, addon._derive_worker_context())
        os.environ['PROXY_LOG_ID'] = 'worker_deadbeef_1785000000'
        assert 'unparsable worker log id' in raises(ValueError, addon._derive_worker_context)


def case_dual_log_names_carry_the_log_id() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        prepare(tmp, log_id='worker_deadbeef_probe_1785000000')
        module = importlib.import_module('src.proxy.addon_dual_log')
        path = module._resolve_dual_log_file('forwarded')
        assert path == Path(tmp) / 'src' / 'logs' / 'dual_log' / 'api_requests_worker_deadbeef_probe_1785000000_forwarded.jsonl', path


def case_model_family_names() -> None:
    from src.proxy.message_summary import _infer_model_family
    for model, expected in (
        ('claude-opus-5-5', 'opus'), ('claude-sonnet-5', 'sonnet'), ('claude-haiku-4-5-20251001', 'haiku'),
        ('CLAUDE-OPUS-X', 'opus'), ('', 'unknown'), (None, 'unknown'), ('gpt-mystery', 'unknown'),
    ):
        assert _infer_model_family(model) == expected, (model, _infer_model_family(model))


def case_unknown_family_is_logged_once_and_request_still_forwarded() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = prepare(tmp)
        addon = importlib.import_module('src.proxy.addon').ProxyAddon()
        for i in range(2):
            flow = FakeFlow(FakeRequest(json.dumps({'model': 'mystery-model', 'system': [], 'tools': [], 'messages': []}).encode(), {'x-request-id': f'r{i}'}))
            addon.request(flow)
            assert json.loads(flow.request.content)['model'] == 'mystery-model'
        lines = [l for l in entries(log) if 'addon.model_family' in l]
        assert len(lines) == 1 and "unknown model family for model 'mystery-model'" in lines[0], entries(log)


def case_unmapped_marker_raises_and_production_markers_map() -> None:
    from src.proxy.strip_sr import _strip_system_reminder
    assert 'no system-reminder template mapped' in raises(ValueError, lambda: _strip_system_reminder('x', 'never mapped marker'))
    from src.proxy import message_passes
    markers = [m for m, _ in message_passes._CUMULATIVE_SR_MARKERS] + ['task tools haven', 'deferred tools are now available via ToolSearch']
    for marker in markers:
        _strip_system_reminder('<system-reminder>\nother\n</system-reminder>', marker)


if __name__ == '__main__':
    main()
