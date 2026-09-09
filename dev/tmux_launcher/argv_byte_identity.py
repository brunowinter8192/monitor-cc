"""
Byte-identity harness for src/tmux_launcher.py's subprocess.run argv sequences (function-LOC
split of launch_split_screen/restart_panes).

Monkeypatches subprocess.run to record every argv list issued (real tmux is never invoked) and to
return scenario-appropriate canned stdout/returncode, for 3 scenarios:
(1) launch_split_screen — session doesn't pre-exist (has-session returncode != 0, so no
    kill_session call), attach-session stubbed (the fake never blocks).
(2) restart_panes — all 6 windows + every layout pane already present (pure respawn path, no
    new-window/split-window calls at all).
(3) restart_panes — window 2 entirely missing (recreate-from-scratch path, exercises the
    pane_specs[1:] split-after-create loop) AND window 5 present but missing its second pane
    'news-log' (single-missing-pane split path). A stateful fake tmux tracks observed
    new-window/split-window calls so a LATER list-panes call in the same run reflects them,
    exactly like real tmux would — this is what actually exercises the "refresh pane list so
    subsequent iterations see the new pane" comment in restart_panes.

Usage (from project root):
    ./venv/bin/python dev/tmux_launcher/argv_byte_identity.py

Prints one HASH line. Run before and after the tmux_launcher.py split; the hash must match.
"""

# INFRASTRUCTURE
import hashlib
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

# ORCHESTRATOR


def main():
    tmux_launcher = _import_tmux_launcher()
    digest = hashlib.sha256()
    digest.update(b'launch|')
    digest.update(json.dumps(_capture_launch(tmux_launcher)).encode())
    digest.update(b'restart_all_present|')
    digest.update(json.dumps(_capture_restart(tmux_launcher, _all_present_state(), {0, 1, 2, 3, 4, 5})).encode())
    digest.update(b'restart_missing|')
    digest.update(json.dumps(_capture_restart(tmux_launcher, _missing_state(), {0, 1, 3, 4, 5})).encode())
    print(f'HASH: {digest.hexdigest()}')


# FUNCTIONS

# Loaded via importlib (not a literal 'from src.' module-level line) — dev/ scripts may not use
# that form (block_dev_imports_src).
def _import_tmux_launcher():
    return importlib.import_module('src.tmux_launcher')


class _FakeCompletedProcess:
    def __init__(self, stdout='', returncode=0):
        self.stdout = stdout
        self.returncode = returncode


# Stateful fake tmux: tracks which windows/panes "exist" and how new-window/split-window calls
# extend that state, so a list-panes call issued later in the same run reflects a just-created
# pane exactly like real tmux would.
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


def _capture_launch(tmux_launcher) -> list:
    recorded = []
    tmux = _FakeTmux(windows=set(), panes_by_window={}, has_session=False)
    orig_run = subprocess.run
    had_tmux_env = 'TMUX' in os.environ
    tmux_env_val = os.environ.pop('TMUX', None)
    subprocess.run = _make_fake_run(recorded, tmux)
    try:
        tmux_launcher.launch_split_screen(project_filter='/tmp/example project', script_path='workflow.py')
    finally:
        subprocess.run = orig_run
        if had_tmux_env:
            os.environ['TMUX'] = tmux_env_val
    return recorded


# All 6 windows + every layout pane already present -> pure respawn path
def _all_present_state() -> dict:
    return {
        0: [('0', 'python3 workflow.py --mode tokens --project /tmp/example-project')],
        1: [('0', 'python3 workflow.py --mode proxy --project /tmp/example-project')],
        2: [('0', 'python3 workflow.py --mode workers --project /tmp/example-project'),
            ('1', 'python3 workflow.py --mode worker-proxy --project /tmp/example-project')],
        3: [('0', 'python3 workflow.py --mode warnings --project /tmp/example-project')],
        4: [('0', 'python3 workflow.py --mode gpu --project /tmp/example-project')],
        5: [('0', 'python3 workflow.py --mode news --project /tmp/example-project'),
            ('1', 'python3 workflow.py --mode news-log --project /tmp/example-project')],
    }


# Window 2 entirely missing from panes_by_window (caller also excludes it from `windows`);
# window 5 present but missing its second pane ('news-log')
def _missing_state() -> dict:
    state = _all_present_state()
    del state[2]
    state[5] = [('0', 'python3 workflow.py --mode news --project /tmp/example-project')]
    return state


def _capture_restart(tmux_launcher, panes_by_window: dict, windows: set) -> list:
    recorded = []
    tmux = _FakeTmux(windows=windows, panes_by_window=panes_by_window, has_session=True)
    orig_run = subprocess.run
    subprocess.run = _make_fake_run(recorded, tmux)
    try:
        tmux_launcher.restart_panes('monitor_cc_fake', project_path='/tmp/example-project',
                                    script_path='workflow.py')
    finally:
        subprocess.run = orig_run
    return recorded


if __name__ == '__main__':
    main()
