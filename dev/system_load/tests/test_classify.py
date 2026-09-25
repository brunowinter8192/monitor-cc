# INFRASTRUCTURE
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dev.refactoring.strand_runner import check, strand_workflow
from fixtures import CC_BIN, HOME, PYTHON_APP, TASKS, base_procs, by_pid, proc, snapshot
from sysload.classify import classify_snapshot

_STRAND_NAMES = [
    '_test_system_and_core_are_essential',
    '_test_caller_chain_and_session_are_excluded',
    '_test_monitor_and_worker_sessions',
    '_test_firefox_tree',
    '_test_worker_proxies',
    '_test_task_file_holders',
    '_test_mineru_tree_is_protected',
    '_test_doubtful_cases',
    '_test_actions_are_exact_and_merged',
]
_TITLE = 'test_classify'
_REPORT_PATH = Path(__file__).resolve().parents[1] / 'md' / 'test_classify.md'
_MINERU = f'{HOME}/Documents/ai/Mineru'
_WORKER_PROXY_SCRIPT = f'{HOME}/Documents/ai/monitor-cc/src/logs/.proxy_addon_live_worker_%s_1790353047_47072.py'
_MAIN_PROXY_SCRIPT = f'{HOME}/Documents/ai/monitor-cc/src/logs/.proxy_addon_live_52fce57c_33313_1790329794.py'


# ORCHESTRATOR

def test_classify_workflow() -> None:
    sys.exit(strand_workflow(globals(), __file__, _STRAND_NAMES, _REPORT_PATH, _TITLE))


# FUNCTIONS

def _run(procs, **kwargs):
    result = classify_snapshot(snapshot(procs, kwargs.pop('self_pid', 9003), **kwargs))
    return result, by_pid(result)


def _test_system_and_core_are_essential() -> None:
    procs = base_procs() + [
        proc(403, 1, '/System/Library/PrivateFrameworks/SkyLight.framework/Resources/WindowServer -daemon', uid=88),
        proc(359, 1, '/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/Metadata.framework/Versions/A/Support/mds', uid=0),
        proc(2100, 1, '/System/Library/Frameworks/CoreServices.framework/Frameworks/Metadata.framework/Support/mdworker_shared -s mdworker -c MDSImporterWorker', uid=501),
        proc(97486, 1, f'{HOME}/Applications/monitor-cc-menubar.app/Contents/MacOS/monitor-cc-menubar'),
        proc(865, 1, '/Applications/Ghostty.app/Contents/MacOS/ghostty'),
        proc(8713, 1, '/System/Applications/Preview.app/Contents/MacOS/Preview', rss_kb=700 * 1024),
    ]
    result, rows = _run(procs, cpu_now={403: 31.3, 2100: 12.0, 97486: 4.7})
    check('WindowServer essential', rows[403]['group'] == 'essential' and rows[403]['rule'] == 'system_owner')
    check('mds essential', rows[359]['group'] == 'essential')
    check('hot mdworker under /System stays essential', rows[2100]['group'] == 'essential' and rows[2100]['rule'] == 'system_path')
    check('menubar essential', rows[97486]['rule'] == 'core_app')
    check('ghostty essential', rows[865]['rule'] == 'core_app')
    check('tmux server essential', rows[72039]['rule'] == 'tmux_server')
    check('launchd essential', rows[1]['group'] == 'essential')
    check('Preview under /System/Applications is a user app, doubtful by memory', rows[8713]['group'] == 'doubtful' and rows[8713]['rule'] == 'D_rss')
    check('hot system pids listed in summary', 403 in result['summary']['hot_system'] and 2100 in result['summary']['hot_system'])


def _test_caller_chain_and_session_are_excluded() -> None:
    procs = [
        proc(1, 0, '/sbin/launchd', uid=0),
        proc(72039, 1, 'tmux new-session -d -s worker-monitor-cc-sysload'),
        proc(92919, 72039, 'bash /tmp/.worker_sysload.abc'),
        proc(92925, 92919, CC_BIN + ' --model claude-sonnet-5'),
        proc(92990, 92925, 'python3 -m sysload snapshot'),
        proc(92991, 92919, 'sleep 30'),
        proc(9101, 72039, 'python3 workflow.py --mode tokens'),
    ]
    _, rows = _run(procs, self_pid=92990, sessions=[('worker-monitor-cc-sysload', 1), ('monitor_cc_25c51a2e', 2)],
                   panes=[('worker-monitor-cc-sysload', 92919), ('monitor_cc_25c51a2e', 9101)])
    check('own claude ancestor essential', rows[92925]['rule'] == 'caller_chain')
    check('own process essential', rows[92990]['rule'] == 'caller_chain')
    check('sibling inside own session essential', rows[92991]['rule'] == 'caller_session')
    check('other monitor session still killable', rows[9101]['group'] == 'killable')

    _, rows = _run(procs, self_pid=9101, sessions=[('monitor_cc_25c51a2e', 2)], panes=[('monitor_cc_25c51a2e', 9101)])
    check('caller inside a monitor session protects that session', rows[9101]['group'] == 'essential')


def _test_monitor_and_worker_sessions() -> None:
    procs = base_procs() + [
        proc(10, 72039, 'python3 workflow.py --mode tokens', cpu_s=8000),
        proc(11, 72039, 'python3 workflow.py --mode proxy'),
        proc(20, 72039, 'bash /tmp/.worker_dead.x'),
        proc(21, 20, 'tail -f /dev/null'),
        proc(30, 72039, 'bash /tmp/.worker_live.y'),
        proc(31, 30, CC_BIN + ' --model claude-sonnet-5'),
        proc(32, 30, 'sleep 1'),
    ]
    sessions = [('monitor_cc_25c51a2e', 1790332894), ('worker-general-dead', 5), ('worker-general-live', 6)]
    panes = [('monitor_cc_25c51a2e', 10), ('monitor_cc_25c51a2e', 11), ('worker-general-dead', 20), ('worker-general-live', 30)]
    result, rows = _run(procs, sessions=sessions, panes=panes)
    check('monitor pane killable by session', rows[10]['rule'] == 'K1_monitor_session' and rows[10]['action']['kind'] == 'tmux_kill_session')
    check('monitor action carries exact name and created stamp', rows[10]['action']['target'] == 'monitor_cc_25c51a2e' and rows[10]['action']['created'] == 1790332894)
    check('worker without claude killable', rows[21]['rule'] == 'K3_dead_worker_session')
    check('worker with claude: claude doubtful', rows[31]['group'] == 'doubtful' and rows[31]['rule'] == 'D_claude')
    check('worker with claude: its shell not killable', rows[30]['group'] == 'essential' and rows[32]['group'] == 'essential')
    check('worker session with claude yields no session action', all(a['target'] != 'worker-general-live' for a in result['actions']))

    _, rows = _run(procs, sessions=sessions, panes=panes, tmux_ok=False)
    check('unreadable tmux: nothing is killable by session', rows[10]['group'] != 'killable' and rows[21]['group'] != 'killable')


def _test_firefox_tree() -> None:
    ff = '/Applications/Firefox.app/Contents/MacOS'
    procs = base_procs() + [
        proc(63785, 1, f'{ff}/firefox', rss_kb=900 * 1024),
        proc(63819, 1, f'{ff}/crashhelper 63785 gecko-crash-server-pipe.63785 /private/var/folders/x/'),
        proc(63837, 63785, f'{ff}/gpu-helper.app/Contents/MacOS/Firefox GPU Helper -parentBuildID 20260921121718'),
        proc(63900, 63785, f'{ff}/plugin-container.app/Contents/MacOS/plugin-container -isForBrowser -prefsHandle 0:53513'),
        proc(7773, 7771, 'ugrep -G --ignore-files --hidden -I Firefox.app'),
    ]
    result, rows = _run(procs, cpu_now={63785: 30.0})
    check('main firefox killable', rows[63785]['rule'] == 'K2_firefox' and rows[63785]['action']['target'] == 63785)
    check('helper is covered by the main pid action', rows[63837]['action']['target'] == 63785 and rows[63900]['action']['target'] == 63785)
    check('detached crashhelper has its own exact pid action', rows[63819]['action']['target'] == 63819)
    check('grep that only mentions Firefox.app is untouched', rows[7773]['group'] != 'killable')
    check('pid actions carry lstart for the pid-reuse guard', all(a['lstart'] for a in result['actions']))


def _test_worker_proxies() -> None:
    def mitm(pid, port, script, ppid=1):
        return proc(pid, ppid, f'mitmdump -p {port} -s {script} --set flow_detail=0 -q')

    procs = base_procs() + [
        mitm(94233, 8094, _WORKER_PROXY_SCRIPT % 'mineru-floor'),
        mitm(47186, 8087, _WORKER_PROXY_SCRIPT % 'dsia-k07'),
        mitm(43260, 8083, _WORKER_PROXY_SCRIPT % 'dsia-k03'),
        mitm(34803, 8092, _MAIN_PROXY_SCRIPT, ppid=33313),
        mitm(34900, 8095, _MAIN_PROXY_SCRIPT.replace('52fce57c', '11111111')),
        proc(33313, 1, 'bash claude_proxy_start.sh'),
    ]
    established = ['[::1]:8087->[::1]:64381', '[::1]:64381->[::1]:8087', '[::1]:8094->[::1]:59242']
    _, rows = _run(procs, sessions=[('worker-monitor-cc-mineru-floor', 1)], established=established)
    check('proxy of a live worker essential', rows[94233]['rule'] == 'proxy_live_worker')
    check('stale proxy with connections is doubtful', rows[47186]['group'] == 'doubtful' and rows[47186]['rule'] == 'proxy_clients_left')
    check('stale proxy without connections is killable by exact pid', rows[43260]['rule'] == 'K4_stale_proxy' and rows[43260]['action']['target'] == 43260)
    check('main proxy with live parent essential', rows[34803]['rule'] == 'proxy_owned')
    check('parentless main proxy doubtful', rows[34900]['rule'] == 'proxy_parentless')

    _, rows = _run(procs, sessions=[('worker-monitor-cc-mineru-floor', 1)], established=None)
    check('unreadable connection state: stale proxy is doubtful', rows[43260]['group'] == 'doubtful' and rows[43260]['rule'] == 'proxy_unverified')
    _, rows = _run(procs, sessions=[], tmux_ok=False)
    check('unreadable tmux: stale proxy is doubtful', rows[43260]['rule'] == 'proxy_unverified')


def _test_task_file_holders() -> None:
    files = lambda pid, size, age: [{'pid': pid, 'path': f'{TASKS}/b{pid}.output', 'size': size, 'mtime_age_s': age}]
    procs = base_procs() + [
        proc(58209, 9001, '/bin/zsh -c source snapshot-zsh', age_s=120),
        proc(58300, 9001, "python3 - <<'E'", age_s=5160, cpu_s=2.0),
        proc(79018, 1, f'{PYTHON_APP} -', age_s=3600),
        proc(79500, 79499, f'{PYTHON_APP} -', age_s=3600),
    ]
    task_files = files(58209, 10, 5) + files(58300, 0, 5160) + files(79018, 0, 3600) + files(79500, 0, 3600)
    result, rows = _run(procs, task_files=task_files)
    check('young live holder essential', rows[58209]['rule'] == 'bgshell_fresh')
    check('the 1h26m silent heredoc shell is doubtful with its file facts',
          rows[58300]['rule'] == 'D_stale_bgshell' and rows[58300]['facts']['task_files'][0]['size'] == 0)
    check('holder owner names the project', rows[58300]['owner'] == 'bgshell:-Users-brunowinter2000-Documents-ai-monitor-cc')
    check('orphan holder (ppid 1, no claude ancestor) killable by pid', rows[79018]['rule'] == 'K5_bg_orphan' and rows[79018]['action']['target'] == 79018)
    check('holder with unresolved ancestry is doubtful, never killable', rows[79500]['rule'] == 'holder_unresolved')


def _test_mineru_tree_is_protected() -> None:
    procs = base_procs() + [
        proc(500, 9000, f'{PYTHON_APP} workflow.py convert /pdf/in.pdf', rss_kb=2000 * 1024),
        proc(501, 500, f'{PYTHON_APP} {_MINERU}/venv/bin/mineru -p /pdf/in.pdf -o out', rss_kb=6000 * 1024),
        proc(502, 501, f'{PYTHON_APP} -m mineru.cli.fast_api --port 8000', rss_kb=9000 * 1024),
        proc(503, 502, 'python3 -c multiprocessing.spawn', rss_kb=3000 * 1024),
        proc(600, 9000, f'{PYTHON_APP} workflow.py convert /other.pdf', rss_kb=2000 * 1024),
        proc(700, 9000, f'{PYTHON_APP} /tmp/Mineru-notes.py', rss_kb=900 * 1024),
        proc(800, 9000, 'sleep 100', rss_kb=4000 * 1024),
    ]
    _, rows = _run(procs, cwds={500: _MINERU, 600: f'{HOME}/Documents/ai/monitor-cc'}, protect_pids=[800])
    check('convert by relative script plus exact cwd is protected', rows[500]['rule'] == 'protected')
    check('whole spawned tree is protected', all(rows[p]['rule'] == 'protected' for p in (501, 502, 503)))
    check('lookalike convert in another cwd is not protected', rows[600]['rule'] != 'protected')
    check('a Mineru substring in a script name is not protected', rows[700]['rule'] != 'protected')
    check('explicit protect pid is honored', rows[800]['rule'] == 'protected')
    check('protected owner names the job', rows[502]['owner'] == 'job:mineru')

    _, rows = _run(procs, cwds={500: _MINERU, 600: f'{HOME}/Documents/ai/monitor-cc'}, protect_roots=[f'{HOME}/Documents/ai/monitor-cc'])
    check('extra protect root extends the exact match', rows[600]['rule'] == 'protected')


def _test_doubtful_cases() -> None:
    procs = base_procs() + [
        proc(94716, 1, f'{HOME}/Documents/ai/Meta/ClaudeCode/cli/rag-cli/llama.cpp/build/bin/llama-server -m x.gguf', rss_kb=3865 * 1024),
        proc(9571, 1, '/Applications/OrbStack.app/Contents/Frameworks/OrbStack Helper.app/Contents/MacOS/OrbStack Helper vmgr', rss_kb=1000 * 1024),
        proc(76068, 9000, CC_BIN + ' --model claude-opus-5-5', tty='ttys002', rss_kb=500 * 1024),
        proc(4001, 9000, f'{PYTHON_APP} stray.py', cpu_s=100),
        proc(4002, 9000, f'{PYTHON_APP} bloated.py', rss_kb=600 * 1024),
        proc(4003, 9000, f'{PYTHON_APP} burner.py', age_s=6000, cpu_s=1000, rss_kb=20000),
        proc(4004, 9000, f'{PYTHON_APP} quiet.py', age_s=6000, cpu_s=30),
        proc(65, 1, '/usr/sbin/mDNSResponder', uid=65),
    ]
    _, rows = _run(procs, cpu_now={4001: 9.5}, cwds={76068: f'{HOME}/Documents/general'})
    check('llama-server doubtful, never killable', rows[94716]['group'] == 'doubtful' and rows[94716]['action'] is None)
    check('OrbStack doubtful, never killable', rows[9571]['group'] == 'doubtful' and rows[9571]['action'] is None)
    check('claude main doubtful with cwd and tty facts', rows[76068]['facts']['cwd'].endswith('general') and rows[76068]['facts']['tty'] == 'ttys002')
    check('cpu over threshold', rows[4001]['rule'] == 'D_cpu_now')
    check('rss over threshold', rows[4002]['rule'] == 'D_rss')
    check('life-long burn over threshold', rows[4003]['rule'] == 'D_burn')
    check('quiet user process is essential', rows[4004]['group'] == 'essential' and rows[4004]['rule'] == 'quiet')
    check('other user daemon essential', rows[65]['rule'] == 'system_owner')


def _test_actions_are_exact_and_merged() -> None:
    procs = base_procs() + [
        proc(10, 72039, 'python3 workflow.py --mode tokens'),
        proc(11, 72039, 'python3 workflow.py --mode proxy'),
        proc(12, 72039, 'python3 workflow.py --mode gpu'),
    ]
    result, rows = _run(procs, sessions=[('monitor_cc_aaaa1111', 7)],
                        panes=[('monitor_cc_aaaa1111', 10), ('monitor_cc_aaaa1111', 11), ('monitor_cc_aaaa1111', 12)],
                        cpu_now={10: 3.0, 11: 2.0, 12: 1.0})
    session_actions = [a for a in result['actions'] if a['kind'] == 'tmux_kill_session']
    check('one action per session, not per pane', len(session_actions) == 1 and sorted(session_actions[0]['covers']) == [10, 11, 12])
    check('action sums the covered load', session_actions[0]['cpu_now'] == 6.0)
    check('every action target is an exact pid or session name', all(isinstance(a['target'], (int, str)) and '*' not in str(a['target']) for a in result['actions']))
    check('summary counts add up', sum(result['summary']['counts'].values()) == len(procs))


if __name__ == '__main__':
    test_classify_workflow()
