# INFRASTRUCTURE
import subprocess
from unittest import mock

from p5_common import load, tmpdir, check, point_log

MAIN_PS = '1 /usr/bin/x\n50 /Applications/Ghostty.app/Contents/MacOS/ghostty\n'
VIEWER_PS = '60 /Users/u/Library/Application Support/iterative-dev/GhosttyViewer.app/Contents/MacOS/ghostty --initial-window=false\n'


# ORCHESTRATOR

def main() -> None:
    point_log(tmpdir())
    g = load('ghostty')
    s = load('system')
    process_markers_are_disjoint(g)
    refresh_maps_both_apps(g)
    prune_drops_both_maps(g)
    query_targets_follow_the_app(g)
    reprobe_asks_only_the_known_app(g)
    focus_activates_viewer_from_outside(s, g)
    focus_worker_routes_by_tty(s, g)


# FUNCTIONS

def run_result(stdout='', returncode=0, stderr=''):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


def reset(g) -> None:
    g._ghostty_tty_to_id.clear()
    g._ghostty_tty_to_app.clear()
    g._ghostty_tty_last_refresh = 0.0


def process_markers_are_disjoint(g) -> None:
    for ps in (MAIN_PS + VIEWER_PS, VIEWER_PS + MAIN_PS):
        with mock.patch.object(g.subprocess, 'run', lambda *a, **k: run_result(ps)):
            got = (g._app_pid(g.GHOSTTY_MAIN), g._app_pid(g.GHOSTTY_VIEWER))
        check('viewer.process_markers_disjoint', got == ('50', '60'), str(got))
    with mock.patch.object(g.subprocess, 'run', lambda *a, **k: run_result(MAIN_PS)):
        check('viewer.not_running_gives_none', g._app_pid(g.GHOSTTY_VIEWER) is None)


def refresh_maps_both_apps(g) -> None:
    reset(g)
    pids = {g.GHOSTTY_MAIN: '50', g.GHOSTTY_VIEWER: '60'}
    ttys = {'50': ['ttys1'], '60': ['ttys9']}
    names = {g.GHOSTTY_MAIN: 'MAIN-ID|||__GHT_ttys1\n', g.GHOSTTY_VIEWER: 'VIEW-ID|||__GHT_ttys9\n'}
    with mock.patch.object(g, '_app_pid', lambda app: pids[app]), \
         mock.patch.object(g, '_ghostty_child_ttys', lambda p: ttys[p]), \
         mock.patch.object(g, '_write_markers', lambda t: [(x, '__GHT_' + x) for x in t]), \
         mock.patch.object(g, '_clear_markers', lambda m: None), mock.patch.object(g.time, 'sleep', lambda s: None), \
         mock.patch.object(g, '_query_terminal_names', lambda app: run_result(names[app])):
        g._refresh_ghostty_tty_to_id(100.0)
    check('viewer.refresh_maps_ids', g._ghostty_tty_to_id == {'ttys1': 'MAIN-ID', 'ttys9': 'VIEW-ID'}, str(g._ghostty_tty_to_id))
    check('viewer.refresh_maps_apps', g._ghostty_tty_to_app == {'ttys1': g.GHOSTTY_MAIN, 'ttys9': g.GHOSTTY_VIEWER})
    check('viewer.refresh_marks_done', g._ghostty_tty_last_refresh == 100.0)


def prune_drops_both_maps(g) -> None:
    reset(g)
    g._ghostty_tty_to_id.update({'ttys1': 'A', 'ttys9': 'B'})
    g._ghostty_tty_to_app.update({'ttys1': g.GHOSTTY_MAIN, 'ttys9': g.GHOSTTY_VIEWER})
    g._prune_gone_ttys(['ttys1'])
    check('viewer.prune_drops_gone_tty_from_both_maps',
          g._ghostty_tty_to_id == {'ttys1': 'A'} and g._ghostty_tty_to_app == {'ttys1': g.GHOSTTY_MAIN})


def query_targets_follow_the_app(g) -> None:
    seen = []
    with mock.patch.object(g.subprocess, 'run', lambda cmd, **k: seen.append(cmd[2]) or run_result('')):
        g._query_terminal_names(g.GHOSTTY_MAIN)
        g._query_terminal_names(g.GHOSTTY_VIEWER)
        g._query_single_terminal_id(g.GHOSTTY_VIEWER, 'm')
    check('viewer.query_targets',
          seen[0].startswith('tell application "Ghostty"') and
          seen[1].startswith('tell application id "com.brunowinter.ghostty-viewer"') and
          seen[2].startswith('tell application id "com.brunowinter.ghostty-viewer"'))


def reprobe_asks_only_the_known_app(g) -> None:
    reset(g)
    g._ghostty_tty_to_app['ttys9'] = g.GHOSTTY_VIEWER
    asked = []

    def ask(app, marker):
        asked.append(app)
        return run_result('VIEW-NEW\n')

    with mock.patch.object(g, '_write_markers', lambda t: [('ttys9', 'm')]), mock.patch.object(g, '_clear_markers', lambda m: None), \
         mock.patch.object(g, '_query_single_terminal_id', ask):
        got = g._reprobe_single_tty('ttys9')
    check('viewer.reprobe_known_app_only', got == 'VIEW-NEW' and asked == [g.GHOSTTY_VIEWER] and g._ghostty_tty_to_id['ttys9'] == 'VIEW-NEW')


def focus_activates_viewer_from_outside(s, g) -> None:
    calls = []
    with mock.patch.object(s.subprocess, 'run', lambda cmd, **k: calls.append(cmd) or run_result('')):
        s._focus_terminal_by_id('V1', g.GHOSTTY_VIEWER)
        s._focus_terminal_by_id('M1', g.GHOSTTY_MAIN)
    viewer_script, open_call, main_script = calls[0][2], calls[1], calls[2][2]
    check('viewer.focus_viewer_script', 'tell application id "com.brunowinter.ghostty-viewer"' in viewer_script and 'focus terminal id "V1"' in viewer_script)
    check('viewer.focus_viewer_activates_from_outside', open_call == ['open', '-b', 'com.brunowinter.ghostty-viewer'])
    check('viewer.focus_main_unchanged', 'tell application "Ghostty"' in main_script and len(calls) == 3)


def focus_worker_routes_by_tty(s, g) -> None:
    reset(g)
    g._ghostty_tty_to_id['ttys9'] = 'V1'
    g._ghostty_tty_to_app['ttys9'] = g.GHOSTTY_VIEWER
    calls = []
    with mock.patch.object(s, '_find_worker_viewer_tty', lambda name: 'ttys9'), \
         mock.patch.object(s.subprocess, 'run', lambda cmd, **k: calls.append(cmd) or run_result('')):
        s._focus_worker('worker-demo')
    check('viewer.focus_worker_end_to_end', len(calls) == 2 and 'focus terminal id "V1"' in calls[0][2] and calls[1][:2] == ['open', '-b'])
    reset(g)


main()
