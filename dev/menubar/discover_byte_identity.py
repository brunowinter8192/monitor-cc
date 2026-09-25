# INFRASTRUCTURE
import hashlib
import importlib
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
from dev.refactoring.live_log_isolation import isolate_home

_HOME_SANDBOX = isolate_home("discover_byte_identity_")


_NOW = 1_000_000.0

_PATCHED_NAMES = [
    '_newest_jsonl', '_has_active_bg', '_read_hook_state', '_cwd_from_jsonl',
    '_worker_tmux_session', '_tmux_session_exists', '_tmux_window_activity',
    '_proc_cwd_for_encoded_dir', '_proxy_log_newest_mtime',
]


# ORCHESTRATOR

def main():
    discover_mod = _import_discover()
    results = compute_results(discover_mod)
    print_hash(results)


# FUNCTIONS

def _import_discover():
    return importlib.import_module('.'.join(['src', 'menubar', 'discover']))


def compute_results(discover_mod):
    return [_run_scenario(discover_mod, name, factory()) for name, factory in scenarios()]


def _run_scenario(discover_mod, name: str, scenario: dict):
    originals = _install_fakes(discover_mod, scenario)
    try:
        result = discover_mod._process_project_dir(scenario['project_dir'], _NOW)
    finally:
        _restore(discover_mod, originals)
    return name, result


def _install_fakes(discover_mod, scenario: dict) -> dict:
    originals = {name: getattr(discover_mod, name) for name in _PATCHED_NAMES}
    discover_mod._newest_jsonl = lambda project_dir: scenario['jsonl']
    discover_mod._has_active_bg = lambda encoded_dir, session_id: scenario['has_bg']
    discover_mod._read_hook_state = lambda now: scenario['hook_state']
    discover_mod._cwd_from_jsonl = lambda jsonl: scenario.get('cwd_from_jsonl')
    discover_mod._worker_tmux_session = lambda cwd, worker_name: (
        f'worker-fake-{worker_name}' if cwd else None)
    discover_mod._tmux_session_exists = lambda name: scenario.get('tmux_session_exists', False)
    discover_mod._tmux_window_activity = lambda name: scenario.get('tmux_window_activity', 0)
    discover_mod._proc_cwd_for_encoded_dir = lambda encoded_dir: scenario.get('proc_cwd')
    discover_mod._proxy_log_newest_mtime = lambda project_key, now: scenario.get('proxy_mtime')
    return originals


def _restore(discover_mod, originals: dict) -> None:
    for name, fn in originals.items():
        setattr(discover_mod, name, fn)


def scenarios():
    return [
        ('worker_fresh_working_stale_activity', _scenario_worker_fresh_working_stale_activity),
        ('worker_no_worktree_old_mtime', _scenario_worker_no_worktree_old_mtime),
        ('main_fresh_hook', _scenario_main_fresh_hook),
        ('main_idle_proxy_override', _scenario_main_idle_proxy_override),
    ]


def _scenario_worker_fresh_working_stale_activity() -> dict:
    return dict(
        project_dir=_FakeProjectDir('-Users-x-Monitor_CC--claude-worktrees-alpha'),
        jsonl=_FakeJsonl('sess-w1', _NOW - 5),
        cwd_from_jsonl='/Users/x/Monitor_CC/.claude/worktrees/alpha',
        tmux_session_exists=True,
        tmux_window_activity=_NOW - 999,
        hook_state={'sess-w1': {'status': 'working', 'updated_ts': _NOW - 1}},
        has_bg=False,
    )


class _FakeProjectDir:
    def __init__(self, name):
        self.name = name


class _FakeJsonl:
    def __init__(self, stem, mtime):
        self.stem = stem
        self._mtime = mtime

    def stat(self):
        return _FakeStat(self._mtime)


class _FakeStat:
    def __init__(self, st_mtime):
        self.st_mtime = st_mtime


def _scenario_worker_no_worktree_old_mtime() -> dict:
    return dict(
        project_dir=_FakeProjectDir('-Users-x-Monitor_CC--claude-worktrees-beta'),
        jsonl=_FakeJsonl('sess-w2', _NOW - 999999),
        cwd_from_jsonl=None,
        tmux_session_exists=False,
        tmux_window_activity=0,
        hook_state={},
        has_bg=False,
    )


def _scenario_main_fresh_hook() -> dict:
    return dict(
        project_dir=_FakeProjectDir('-Users-x-Monitor_CC'),
        jsonl=_FakeJsonl('sess-m1', _NOW - 3),
        proc_cwd='/Users/x/Monitor_CC',
        hook_state={'sess-m1': {'status': 'working', 'updated_ts': _NOW - 1}},
        has_bg=True,
        proxy_mtime=None,
    )


def _scenario_main_idle_proxy_override() -> dict:
    return dict(
        project_dir=_FakeProjectDir('-Users-x-Other_Proj'),
        jsonl=_FakeJsonl('sess-m2', _NOW - 999),
        proc_cwd='/Users/x/Other_Proj',
        hook_state={},
        has_bg=False,
        proxy_mtime=_NOW - 100,
    )


def print_hash(results):
    print(f'HASH: {_hash_results(results)}')


def _hash_results(results) -> str:
    entries = [{'scenario': name, 'result': info._asdict() if info is not None else None}
               for name, info in results]
    return hashlib.sha256(json.dumps(entries, sort_keys=True, default=str).encode()).hexdigest()


if __name__ == '__main__':
    main()
