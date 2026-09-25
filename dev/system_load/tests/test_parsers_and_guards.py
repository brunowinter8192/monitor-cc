# INFRASTRUCTURE
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dev.refactoring.strand_runner import check, strand_workflow
from fixtures import base_procs, proc, snapshot
from sysload import collect, confirm, diff, render
from sysload.classify import classify_snapshot

_PACKAGE_DIR = Path(__file__).resolve().parents[1] / 'sysload'
_STRAND_NAMES = [
    '_test_parse_ps_and_clock',
    '_test_parse_top_lsof_tmux',
    '_test_confirm_uses_exact_identity',
    '_test_diff_reports_outcomes',
    '_test_render_shows_all_groups',
    '_test_package_has_no_termination_code',
]
_TITLE = 'test_parsers_and_guards'
_REPORT_PATH = Path(__file__).resolve().parents[1] / 'md' / 'test_parsers_and_guards.md'
_PS_SYSPOLICYD = '  505     1     0 ??       05-06:23:44  61:26.89  25104 Ss   Sun Sep 20 12:21:00 2026     /usr/libexec/syspolicyd'
_PS_CLAUDE = '  4714  4407   501 ttys003     01:01:47   0:50.82 622352 S+   Fri Sep 25 17:42:57 2026     /Users/x/claude.exe --model claude-opus-5'
_TOP_TWO_SAMPLES = (
    'Processes: 976 total\nLoad Avg: 4.85, 5.45, 5.21\n\nPID    %CPU\n1      0.0\n403    99.9\n\n'
    'Processes: 976 total\nLoad Avg: 4.90, 5.40, 5.20\n\nPID    %CPU\n1      0.5\n403    31.3\n9571   20.0\n'
)
_LSOF_PAIRS = 'p58209\nn/private/tmp/claude-501/-p/s/tasks/a.output\nn/private/tmp/claude-501/-p/s/tasks/b.output\np79018\nn/x.output\n'
_FORBIDDEN_TERMS = ('os.kill', 'signal', 'killpg', 'pkill', 'killall', 'kill-session', 'SIGTERM', 'SIGKILL')


# ORCHESTRATOR

def test_parsers_and_guards_workflow() -> None:
    sys.exit(strand_workflow(globals(), __file__, _STRAND_NAMES, _REPORT_PATH, _TITLE))


# FUNCTIONS

def _test_parse_ps_and_clock() -> None:
    daemon = collect.parse_ps_line(_PS_SYSPOLICYD)
    check('daemon fields', daemon['pid'] == 505 and daemon['ppid'] == 1 and daemon['uid'] == 0 and daemon['tty'] == '??')
    check('lstart is the five-token start time', daemon['lstart'] == 'Sun Sep 20 12:21:00 2026')
    check('command survives', daemon['command'] == '/usr/libexec/syspolicyd')
    check('day-prefixed etime', daemon['age_s'] == 5 * 86400 + 6 * 3600 + 23 * 60 + 44)
    check('cputime with fraction', abs(daemon['cpu_s'] - (61 * 60 + 26.89)) < 0.001)
    claude = collect.parse_ps_line(_PS_CLAUDE)
    check('tty and args survive', claude['tty'] == 'ttys003' and claude['command'].endswith('--model claude-opus-5'))
    check('short line is skipped', collect.parse_ps_line('  1 0 0') is None)
    check('mm:ss clock', collect.parse_clock('01:01') == 61.0)


def _test_parse_top_lsof_tmux() -> None:
    cpu = collect.parse_top_last_sample(_TOP_TWO_SAMPLES)
    check('only the last top sample is used', cpu == {1: 0.5, 403: 31.3, 9571: 20.0})
    check('no header gives empty', collect.parse_top_last_sample('nothing') == {})
    pairs = collect.parse_lsof_pairs(_LSOF_PAIRS)
    check('lsof pairs carry the holder pid', pairs[0] == (58209, '/private/tmp/claude-501/-p/s/tasks/a.output') and pairs[2] == (79018, '/x.output'))
    sessions = collect.parse_tmux_sessions('monitor_cc_25c51a2e|1790332894\nworker-x|abc\n')
    check('tmux sessions parsed, malformed skipped', sessions == [{'name': 'monitor_cc_25c51a2e', 'created': 1790332894}])
    panes = collect.parse_tmux_panes('monitor_cc_25c51a2e|57090|/Users/x/monitor-cc\n')
    check('tmux panes parsed', panes == [{'session': 'monitor_cc_25c51a2e', 'pane_pid': 57090, 'path': '/Users/x/monitor-cc'}])


def _test_confirm_uses_exact_identity() -> None:
    with patch.object(confirm, 'run_text', return_value='Fri Sep 25 17:42:57 2026\n'):
        check('same lstart confirms', confirm.pid_matches('4714', 'Fri Sep 25 17:42:57 2026'))
        check('other lstart is a reused pid', not confirm.pid_matches('4714', 'Fri Sep 25 18:00:00 2026'))
    with patch.object(confirm, 'run_text', return_value=''):
        check('vanished pid with empty stamp never confirms', not confirm.pid_matches('4714', ''))
    with patch.object(confirm, 'run_text', return_value=None):
        check('unreadable ps never confirms', not confirm.pid_matches('4714', 'Fri Sep 25 17:42:57 2026'))
    check('non-numeric pid never confirms', not confirm.pid_matches('4714; rm', 'x'))
    listing = 'monitor_cc_25c51a2e|1790332894\nmonitor_cc_52070e64|1790352953\n'
    with patch.object(confirm, 'run_text', return_value=listing):
        check('session with same created confirms', confirm.session_matches('monitor_cc_25c51a2e', '1790332894'))
        check('session with other created is a recreated session', not confirm.session_matches('monitor_cc_25c51a2e', '5'))
        check('missing session does not confirm', not confirm.session_matches('monitor_cc_zzzzzzzz', '1'))


def _classified(with_monitor: bool) -> dict:
    procs = base_procs()
    panes, sessions = [], []
    if with_monitor:
        procs = procs + [proc(10, 72039, 'python3 workflow.py --mode tokens'), proc(77, 1, '/Applications/Firefox.app/Contents/MacOS/firefox')]
        panes, sessions = [('monitor_cc_25c51a2e', 10)], [('monitor_cc_25c51a2e', 1790332894)]
    return classify_snapshot(snapshot(procs, 9003, sessions=sessions, panes=panes))


def _test_diff_reports_outcomes() -> None:
    before = json.loads(json.dumps(_classified(True)))
    after = json.loads(json.dumps(_classified(False)))
    text = diff.render_diff(before, after)
    check('killed session reported gone', 'tmux_kill_session monitor_cc_25c51a2e: gone' in text)
    check('killed pid reported gone', 'kill_pid 77: gone' in text)
    check('nothing new after', 'no new killable actions' in text)
    survived = diff.render_diff(before, before)
    check('survivors are flagged', 'STILL PRESENT' in survived and 'STILL RUNNING' in survived)
    fresh = diff.render_diff(after, before)
    check('respawned targets show up as new', 'new killable actions' in fresh and 'monitor_cc_25c51a2e' in fresh)


def _test_render_shows_all_groups() -> None:
    text = render.render_report(_classified(True), '/tmp/x.json')
    check('summary lists three groups', all(g in text for g in ('killable', 'doubtful', 'essential')))
    check('actions block present with the exact target', 'monitor_cc_25c51a2e' in text and 'kill_pid' in text)
    check('json path echoed', '/tmp/x.json' in text)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / 'r.json'
        out.write_text(json.dumps(_classified(True)), encoding='utf-8')
        check('report json round-trips', diff.load_result(str(out))['summary']['process_total'] > 0)


def _test_package_has_no_termination_code() -> None:
    for path in sorted(_PACKAGE_DIR.glob('*.py')):
        text = path.read_text(encoding='utf-8')
        for term in _FORBIDDEN_TERMS:
            check(f'{path.name} has no {term}', term not in text)


if __name__ == '__main__':
    test_parsers_and_guards_workflow()
