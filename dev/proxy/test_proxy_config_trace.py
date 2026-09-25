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


def prepare(tmp: str, log_id: str = 'opus_probe_1') -> Path:
    os.environ['HOME'] = tmp
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


def shared_rules(tmp: str) -> Path:
    directory = Path(tmp) / '.claude' / 'shared-rules'
    directory.mkdir(parents=True)
    return directory


def lines_for(log: Path, source: str) -> list:
    return [l for l in entries(log) if f'[{source}' in l]


def case_load_config_failure_is_traced_once_and_rearms() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = prepare(tmp)
        rules = shared_rules(tmp)
        module = importlib.import_module('src.proxy.rules_config')
        assert module._load_config() == {} and module._load_config() == {}
        assert len(lines_for(log, 'rules_config.load_config')) == 1, entries(log)
        (rules / 'proxy_rules.json').write_text('{"context_management": {"enabled": true}}')
        assert module._load_config() == {'context_management': {'enabled': True}}
        (rules / 'proxy_rules.json').write_text('{broken')
        os.utime(rules / 'proxy_rules.json', (1, 1))
        assert module._load_config() == {}
        assert len(lines_for(log, 'rules_config.load_config')) == 2, entries(log)


def case_rule_file_failure_is_traced_and_returns_empty() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = prepare(tmp)
        rules = shared_rules(tmp)
        module = importlib.import_module('src.proxy.rules_config')
        assert module._read_rule_file('absent.md') == '' and module._read_rule_file('absent.md') == ''
        assert len(lines_for(log, 'rules_config.rule_file absent.md')) == 1, entries(log)
        (rules / 'present.md').write_text('rule text')
        assert module._read_rule_file('present.md') == 'rule text'


def case_model_override_load_failure_is_traced_and_not_pinned() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = prepare(tmp)
        helpers = importlib.import_module('src.proxy.inject_helpers')
        payload = {'model': 'claude-opus-5-5', 'messages': []}
        fixated = {}

        def boom():
            raise RuntimeError('config exploded')

        helpers._load_config = boom
        assert helpers._inject_model_override(payload, fixated) == (payload, False)
        assert helpers._inject_model_override(payload, fixated) == (payload, False)
        assert fixated == {} and len(lines_for(log, 'inject_helpers.model_override')) == 1, entries(log)
        helpers._load_config = lambda: {'model_params': {'claude-opus-5-5': {'effort': 'high'}}}
        result, injected = helpers._inject_model_override(payload, fixated)
        assert injected is True and result['output_config'] == {'effort': 'high'}
        helpers._load_config = boom
        helpers._inject_model_override({'model': 'other', 'messages': []}, {})
        assert len(lines_for(log, 'inject_helpers.model_override')) == 2, entries(log)


def case_context_management_failure_is_traced_fail_open() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = prepare(tmp)
        helpers = importlib.import_module('src.proxy.inject_helpers')
        payload = {'model': 'm', 'messages': []}

        def boom():
            raise RuntimeError('config exploded')

        helpers._load_config = boom
        assert helpers._inject_context_management(payload) == (payload, False)
        assert helpers._inject_context_management(payload) == (payload, False)
        assert len(lines_for(log, 'inject_helpers.context_management')) == 1, entries(log)
        helpers._load_config = lambda: {'context_management': {'enabled': True}}
        result, injected = helpers._inject_context_management(payload)
        assert injected is True and [e['type'] for e in result['context_management']['edits']] == ['clear_thinking_20251015', 'clear_tool_uses_20250919']


def case_active_plugins_degraded_paths_are_traced() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = prepare(tmp)
        module = importlib.import_module('src.proxy.tool_injection')
        project = Path(tmp) / 'project'
        (project / '.claude').mkdir(parents=True)
        plugins_file = project / '.claude' / 'active_plugins.json'
        assert module._load_active_plugins('') == ['iterative-dev']
        assert module._load_active_plugins(str(project)) == ['iterative-dev']
        assert any('active_plugins.json missing' in l for l in lines_for(log, 'tool_injection.active_plugins')), entries(log)
        plugins_file.write_text('{broken')
        assert module._load_active_plugins(str(project)) == ['iterative-dev']
        plugins_file.write_text('{"plugins": "not a list"}')
        os.utime(plugins_file, (5, 5))
        assert module._load_active_plugins(str(project)) == ['iterative-dev']
        assert any("'plugins' is not a list" in l for l in entries(log)), entries(log)
        plugins_file.write_text('{"plugins": ["a", "b"]}')
        os.utime(plugins_file, (9, 9))
        assert module._load_active_plugins(str(project)) == ['iterative-dev', 'a', 'b']
        count = len(entries(log))
        assert module._load_active_plugins(str(project)) == ['iterative-dev', 'a', 'b'] and len(entries(log)) == count


def case_exclude_list_degraded_paths_are_traced() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = prepare(tmp)
        rules = shared_rules(tmp)
        module = importlib.import_module('src.proxy.tool_injection')
        assert module._is_project_excluded('') is False
        assert module._is_project_excluded('/p/x') is False
        assert any('proxy_rules.json missing' in l for l in lines_for(log, 'tool_injection.exclude_projects')), entries(log)
        (rules / 'proxy_rules.json').write_text('{broken')
        assert module._is_project_excluded('/p/x') is False
        (rules / 'proxy_rules.json').write_text('{"tool_injection": {"exclude_projects": "x"}}')
        assert module._is_project_excluded('/p/x') is False
        assert any('exclude_projects is not a list' in l for l in entries(log)), entries(log)
        (rules / 'proxy_rules.json').write_text('{"tool_injection": {"exclude_projects": ["/p/x"]}}')
        assert module._is_project_excluded('/p/x') is True and module._is_project_excluded('/q') is False


def case_schema_file_skip_is_traced() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = prepare(tmp)
        store = Path(tmp) / 'src' / 'proxy' / 'schemas' / 'plugin-a'
        store.mkdir(parents=True)
        (store / 'good.json').write_text('{"name": "tool_a"}')
        (store / 'bad.json').write_text('{broken')
        module = importlib.import_module('src.proxy.tool_injection')
        module._SCHEMA_STORE_CACHE = None
        assert module._load_schema_store() == {'plugin-a': [{'name': 'tool_a'}]}
        assert len(lines_for(log, 'tool_injection.schema_file')) == 1, entries(log)


if __name__ == '__main__':
    main()
