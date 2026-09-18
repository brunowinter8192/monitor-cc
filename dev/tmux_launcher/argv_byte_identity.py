# INFRASTRUCTURE
import importlib
import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

_LAUNCH_PROJECT = '/tmp/example project'
_RESTART_PROJECT = '/tmp/example-project'
_SCRIPT_PATH = 'workflow.py'
_RESTART_SESSION = 'monitor_cc_fake'

# ORCHESTRATOR


def main():
    tmux_launcher = _import_tmux_launcher()
    checks = []
    checks += _run_launch_scenario(tmux_launcher)
    checks += _run_restart_all_present_scenario(tmux_launcher)
    checks += _run_restart_self_heal_scenario(tmux_launcher)
    _report(checks)


# FUNCTIONS

def _import_tmux_launcher():
    return importlib.import_module('src.tmux_launcher')


class _FakeCompletedProcess:
    def __init__(self, stdout='', returncode=0):
        self.stdout = stdout
        self.returncode = returncode


class _FakeTmux:
    def __init__(self, windows: set, panes_by_window: dict, has_session: bool):
        self.windows = set(windows)
        self.panes_by_window = {k: list(v) for k, v in panes_by_window.items()}
        self._next_idx = {k: (max((int(i) for i, _ in v), default=-1) + 1)
                          for k, v in self.panes_by_window.items()}
        self.has_session = has_session

    @staticmethod
    def _win_of(argv: list) -> int:
        t_arg = argv[argv.index('-t') + 1]
        return int(t_arg.split(':')[1].split('.')[0])

    def observe(self, argv: list) -> None:
        if argv[:2] not in (['tmux', 'new-window'], ['tmux', 'split-window']):
            return
        win_idx = self._win_of(argv)
        cmd = argv[-1]
        self.windows.add(win_idx)
        self.panes_by_window.setdefault(win_idx, [])
        idx = self._next_idx.get(win_idx, 0)
        self.panes_by_window[win_idx].append((str(idx), cmd))
        self._next_idx[win_idx] = idx + 1

    def list_windows(self) -> str:
        return '\n'.join(str(w) for w in sorted(self.windows))

    def list_panes(self, win_idx: int, fmt: str) -> str:
        panes = self.panes_by_window.get(win_idx, [])
        if '#{pane_start_command}' in fmt:
            return '\n'.join(f'{idx}|{cmd}' for idx, cmd in panes)
        return '\n'.join(idx for idx, _cmd in panes)


def _make_fake_run(recorded: list, tmux: _FakeTmux):
    def _fake_run(argv, *args, **kwargs):
        recorded.append(list(argv))
        if argv[:2] == ['which', 'tmux']:
            return _FakeCompletedProcess(returncode=0)
        if argv[:2] == ['tmux', 'has-session']:
            return _FakeCompletedProcess(returncode=0 if tmux.has_session else 1)
        if argv[:2] == ['tmux', 'show-options']:
            return _FakeCompletedProcess(stdout='2000\n', returncode=0)
        if argv[:2] == ['tmux', 'list-windows']:
            return _FakeCompletedProcess(stdout=tmux.list_windows(), returncode=0)
        if argv[:2] == ['tmux', 'list-panes']:
            win_idx = tmux._win_of(argv)
            fmt = argv[argv.index('-F') + 1]
            return _FakeCompletedProcess(stdout=tmux.list_panes(win_idx, fmt), returncode=0)
        if argv[:2] in (['tmux', 'new-window'], ['tmux', 'split-window']):
            tmux.observe(argv)
            return _FakeCompletedProcess(returncode=0)
        return _FakeCompletedProcess(returncode=0)
    return _fake_run


def _capture_launch(tmux_launcher, project_filter: str, script_path: str) -> list:
    recorded = []
    tmux = _FakeTmux(windows=set(), panes_by_window={}, has_session=False)
    orig_run = subprocess.run
    had_tmux_env = 'TMUX' in os.environ
    tmux_env_val = os.environ.pop('TMUX', None)
    subprocess.run = _make_fake_run(recorded, tmux)
    try:
        tmux_launcher.launch_split_screen(project_filter=project_filter, script_path=script_path)
    finally:
        subprocess.run = orig_run
        if had_tmux_env:
            os.environ['TMUX'] = tmux_env_val
    return recorded


def _all_present_state() -> dict:
    return {
        0: [('0', f'python3 {_SCRIPT_PATH} --mode tokens --project {_RESTART_PROJECT}')],
        1: [('0', f'python3 {_SCRIPT_PATH} --mode proxy --project {_RESTART_PROJECT}')],
        2: [('0', f'python3 {_SCRIPT_PATH} --mode worker-tokens --project {_RESTART_PROJECT}')],
        3: [('0', f'python3 {_SCRIPT_PATH} --mode worker-proxy --project {_RESTART_PROJECT}')],
        4: [('0', f'python3 {_SCRIPT_PATH} --mode warnings --project {_RESTART_PROJECT}')],
        5: [('0', f'python3 {_SCRIPT_PATH} --mode gpu --project {_RESTART_PROJECT}')],
        6: [('0', f'python3 {_SCRIPT_PATH} --mode news --project {_RESTART_PROJECT}'),
            ('1', f'python3 {_SCRIPT_PATH} --mode news-log --project {_RESTART_PROJECT}')],
    }


def _missing_state() -> dict:
    state = _all_present_state()
    del state[3]
    state[6] = [('0', f'python3 {_SCRIPT_PATH} --mode news --project {_RESTART_PROJECT}')]
    return state


def _capture_restart(tmux_launcher, panes_by_window: dict, windows: set) -> list:
    recorded = []
    tmux = _FakeTmux(windows=windows, panes_by_window=panes_by_window, has_session=True)
    orig_run = subprocess.run
    subprocess.run = _make_fake_run(recorded, tmux)
    try:
        tmux_launcher.restart_panes(_RESTART_SESSION, project_path=_RESTART_PROJECT,
                                    script_path=_SCRIPT_PATH)
    finally:
        subprocess.run = orig_run
    return recorded


def _extract_session_name(recorded: list) -> str:
    for argv in recorded:
        if argv[:2] == ['tmux', 'new-session']:
            return argv[argv.index('-s') + 1]
    return ''


def _expected_layout_calls(session_name: str, cmds: dict) -> list:
    return [
        ['tmux', 'new-session', '-d', '-s', session_name, cmds['tokens']],
        ['tmux', 'rename-window', '-t', f'{session_name}:0', 'tokens'],
        ['tmux', 'new-window', '-t', f'{session_name}:1', '-n', 'proxy', cmds['proxy']],
        ['tmux', 'new-window', '-t', f'{session_name}:2', '-n', 'w-tokens', cmds['worker-tokens']],
        ['tmux', 'new-window', '-t', f'{session_name}:3', '-n', 'w-proxy', cmds['worker-proxy']],
        ['tmux', 'new-window', '-t', f'{session_name}:4', '-n', 'debug', cmds['warnings']],
        ['tmux', 'new-window', '-t', f'{session_name}:5', '-n', 'gpu', cmds['gpu']],
        ['tmux', 'new-window', '-t', f'{session_name}:6', '-n', 'news', cmds['news']],
        ['tmux', 'split-window', '-h', '-t', f'{session_name}:6.0', '-l', '50%', cmds['news-log']],
        ['tmux', 'select-window', '-t', f'{session_name}:0'],
    ]


def _expected_pane_title_calls(session_name: str) -> list:
    pane_titles = {
        '0.0': 'TOKENS',
        '1.0': 'PROXY',
        '2.0': 'WORKER-TOKENS',
        '3.0': 'WORKER-PROXY',
        '4.0': 'WARNINGS',
        '5.0': 'GPU',
        '6.0': 'NEWS', '6.1': 'NEWS-LOG',
    }
    return [['tmux', 'select-pane', '-t', f'{session_name}:{ref}', '-T', title]
            for ref, title in pane_titles.items()]


def _expected_mkey_calls(session_name: str) -> list:
    targets = {
        'M-t': ('0.0', 'Tokens'),
        'M-p': ('1.0', 'Proxy'),
        'M-k': ('2.0', 'Worker-tokens'),
        'M-w': ('4.0', 'Warnings'),
        'M-n': ('6.1', 'News-log'),
    }
    return [
        ['tmux', 'bind-key', '-T', 'root', key, 'run-shell',
         f"tmux capture-pane -t {session_name}:{pane} -pS - | pbcopy && tmux display '{label} pane copied'"]
        for key, (pane, label) in targets.items()
    ]


def _actual_window_option_targets(recorded: list) -> set:
    targets = set()
    for argv in recorded:
        if argv[:2] == ['tmux', 'set-window-option']:
            win = int(argv[argv.index('-t') + 1].split(':')[1])
            targets.add(win)
    return targets


def _run_launch_scenario(tmux_launcher) -> list:
    recorded = _capture_launch(tmux_launcher, _LAUNCH_PROJECT, _SCRIPT_PATH)
    session_name = _extract_session_name(recorded)
    cmds = tmux_launcher._build_mode_commands(_SCRIPT_PATH, _LAUNCH_PROJECT)

    actual_layout = [argv for argv in recorded
                      if argv[:2] in (['tmux', 'new-session'], ['tmux', 'rename-window'],
                                       ['tmux', 'new-window'], ['tmux', 'split-window'],
                                       ['tmux', 'select-window'])]
    actual_titles = [argv for argv in recorded if argv[:2] == ['tmux', 'select-pane']]
    actual_mkeys = [argv for argv in recorded if argv[:2] == ['tmux', 'bind-key']
                     and len(argv) > 4 and argv[4] in ('M-t', 'M-p', 'M-k', 'M-w', 'M-n')]
    actual_win_opts = _actual_window_option_targets(recorded)

    return [
        ('launch: window/pane creation sequence (7 windows, 8 panes)',
         actual_layout == _expected_layout_calls(session_name, cmds)),
        ('launch: pane title map (2.0/3.0 split, 4.0/5.0/6.0/6.1 shifted)',
         actual_titles == _expected_pane_title_calls(session_name)),
        ('launch: M-* copy bindings (M-w -> 4.0, M-n -> 6.1)',
         actual_mkeys == _expected_mkey_calls(session_name)),
        ('launch: per-window option loop covers windows 0..6',
         actual_win_opts == set(range(7))),
    ]


def _run_restart_all_present_scenario(tmux_launcher) -> list:
    recorded = _capture_restart(tmux_launcher, _all_present_state(), set(range(7)))
    create_calls = [argv for argv in recorded
                     if argv[:2] in (['tmux', 'new-window'], ['tmux', 'split-window'])]
    return [
        ('restart, all present: zero create/split calls (pure respawn)',
         create_calls == []),
    ]


def _run_restart_self_heal_scenario(tmux_launcher) -> list:
    recorded = _capture_restart(tmux_launcher, _missing_state(), set(range(7)) - {3})
    cmds = tmux_launcher._build_mode_commands(_SCRIPT_PATH, _RESTART_PROJECT)

    expected_create_calls = [
        ['tmux', 'new-window', '-t', f'{_RESTART_SESSION}:3', '-n', 'w-proxy', cmds['worker-proxy']],
        ['tmux', 'split-window', '-h', '-t', f'{_RESTART_SESSION}:6.0', '-l', '50%', cmds['news-log']],
    ]
    actual_create_calls = [argv for argv in recorded
                            if argv[:2] in (['tmux', 'new-window'], ['tmux', 'split-window'])]

    expected_respawn_targets = sorted(f'{_RESTART_SESSION}:{ref}' for ref in
                                       ('0.0', '1.0', '2.0', '3.0', '4.0', '5.0', '6.0', '6.1'))
    actual_respawn_targets = sorted(argv[-1] for argv in recorded
                                     if argv[:2] == ['tmux', 'respawn-pane'])

    return [
        ('restart, self-heal: whole missing window (3) recreated, single missing pane (6.1) split back in',
         actual_create_calls == expected_create_calls),
        ('restart, self-heal: exactly 8 panes respawned after healing',
         actual_respawn_targets == expected_respawn_targets),
    ]


def _report(checks: list) -> None:
    failed = [name for name, passed in checks if not passed]
    for name, passed in checks:
        print(f"{'PASS' if passed else 'FAIL'}: {name}")
    if failed:
        print(f"\n{len(failed)} of {len(checks)} checks FAILED")
        sys.exit(1)
    print(f"\nall {len(checks)} checks PASSED")


if __name__ == '__main__':
    main()
