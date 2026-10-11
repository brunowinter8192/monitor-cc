# INFRASTRUCTURE
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from Foundation import NSObject

from p5_common import load, tmpdir, check, point_log, log_text

WORKTREE_CWD = '/Users/x/monitor-cc/.claude/worktrees/haikutest'
METADATA_TAIL = ('last-prompt', 'ai-title', 'mode', 'permission-mode', 'atis-latch')
REPO_ROOT = Path(__file__).resolve().parents[2]


# ORCHESTRATOR

def main() -> None:
    d = tmpdir()
    mlog = point_log(d)
    disc = load('discover')
    disc._tmux_session_exists = lambda s: True
    disc._tmux_window_activity = lambda s: None
    cache_survives_unreadable_tail(disc, d)
    wide_scan_finds_first_sighting(disc, d)
    unresolvable_worker_is_scanned_once_per_mtime(disc, d)
    dead_tmux_session_is_not_resurrected(disc, d)
    click_resolves_at_click_time(mlog)
    log_keeps_non_ascii_under_ascii_locale(d)


# FUNCTIONS

def jsonl_text(big_assistant_line: bool, with_cwd: bool = True) -> str:
    cwd = WORKTREE_CWD if with_cwd else ''
    lines = [json.dumps({'type': 'system', 'cwd': cwd})]
    lines.append(json.dumps({'type': 'assistant', 'cwd': cwd, 'message': 'x' * (150000 if big_assistant_line else 100)}))
    lines += [json.dumps({'type': t}) for t in METADATA_TAIL]
    return '\n'.join(lines) + '\n'


def worker_info(disc, path: Path, session_id: str, mtime: float):
    return disc._worker_session_info(path, mtime, 'enc', 'monitor-cc', 'haikutest', session_id, False, {}, time.time())


def cache_survives_unreadable_tail(disc, d: Path) -> None:
    path = d / 'a.jsonl'
    path.write_text(jsonl_text(big_assistant_line=False))
    first = worker_info(disc, path, 'sess-a', 1.0)
    path.write_text(jsonl_text(big_assistant_line=True))
    check('click.narrow_scan_fails_on_big_tail', disc._cwd_from_jsonl(path) is None)
    second = worker_info(disc, path, 'sess-a', 2.0)
    check('click.cache_keeps_tmux_name', first.tmux_session_name == second.tmux_session_name == 'worker-monitor-cc-haikutest',
          f'{first.tmux_session_name!r} {second.tmux_session_name!r}')


def wide_scan_finds_first_sighting(disc, d: Path) -> None:
    path = d / 'b.jsonl'
    path.write_text(jsonl_text(big_assistant_line=True))
    info = worker_info(disc, path, 'sess-b', 1.0)
    check('click.wide_scan_resolves_first_sighting', info.tmux_session_name == 'worker-monitor-cc-haikutest', repr(info.tmux_session_name))


def unresolvable_worker_is_scanned_once_per_mtime(disc, d: Path) -> None:
    path = d / 'c.jsonl'
    path.write_text(jsonl_text(big_assistant_line=True, with_cwd=False))
    calls = []
    real = disc._cwd_from_jsonl_wide
    with mock.patch.object(disc, '_cwd_from_jsonl_wide', lambda p: calls.append(1) or real(p)):
        recent = time.time() - 10
        first = worker_info(disc, path, 'sess-c', recent)
        worker_info(disc, path, 'sess-c', recent)
        worker_info(disc, path, 'sess-c', recent + 1)
    check('click.unresolvable_scanned_once_per_mtime', len(calls) == 2, f'wide scans={len(calls)}')
    check('click.unresolvable_keeps_mtime_route_with_empty_name', first.tmux_session_name == '' and first.name == 'haikutest')


def dead_tmux_session_is_not_resurrected(disc, d: Path) -> None:
    path = d / 'd.jsonl'
    path.write_text(jsonl_text(big_assistant_line=False))
    worker_info(disc, path, 'sess-d', 1.0)
    path.write_text(jsonl_text(big_assistant_line=True))
    disc._tmux_session_exists = lambda s: False
    gone = worker_info(disc, path, 'sess-d', 2.0)
    disc._tmux_session_exists = lambda s: True
    check('click.cached_identity_respects_tmux_death', gone is None)


def session(disc, tmux_name: str):
    return disc.SessionInfo(name='haikutest', status='working', has_bg=False, encoded_dir='enc-haiku', project_name='monitor-cc',
                            is_worker=True, cwd='', session_id='s', tmux_session_name=tmux_name)


def click_resolves_at_click_time(mlog) -> None:
    app_mod = load('app')
    disc = load('discover')
    pm_mod = load('panel_manager')
    sc_mod = load('sessions_controller')

    class FakeCtl(NSObject):
        pass

    fake_app = SimpleNamespace(settings=SimpleNamespace(panel_width=422, panel_min_height=460),
                               _panel_controller=FakeCtl.alloc().init())
    pm = pm_mod.PanelManager(fake_app)
    fake_app.panel = pm
    fake_app.sessions = sc_mod.SessionsController(fake_app)
    main_row = disc.SessionInfo(name='monitor-cc', status='idle', has_bg=False, encoded_dir='enc-main', project_name='monitor-cc',
                                is_worker=False, cwd='/p/monitor-cc', session_id='m', tmux_session_name='')
    pm.rebuild([main_row, session(disc, '')], {})
    tag = next(iter(pm._lookups.worker_dir_by_tag))
    check('click.rebuild_stores_stable_row_identity', pm._lookups.worker_dir_by_tag[tag] == 'enc-haiku')

    controller = app_mod._PanelController.alloc().initWithApp_(fake_app)
    sender = SimpleNamespace(tag=lambda: tag)
    focused = []
    with mock.patch.object(app_mod, '_focus_worker', focused.append):
        fake_app.sessions._last_sessions = [main_row, session(disc, '')]
        controller.focusWorker_(sender)
        empty_logged = 'focus_worker NO-OP reason=no_tmux_session' in log_text(mlog)
        fake_app.sessions._last_sessions = [main_row, session(disc, 'worker-monitor-cc-haikutest')]
        controller.focusWorker_(sender)
        controller.focusWorker_(SimpleNamespace(tag=lambda: 9999))
    check('click.empty_name_is_logged_not_silent', empty_logged)
    check('click.recovered_name_is_used_without_rebuild', focused == ['worker-monitor-cc-haikutest'], str(focused))
    check('click.unknown_tag_is_logged', 'tag=9999' in log_text(mlog))


def log_keeps_non_ascii_under_ascii_locale(d: Path) -> None:
    target = d / 'ascii_locale.log'
    code = (
        f'import sys; sys.path.insert(0, {str(REPO_ROOT)!r})\n'
        'from pathlib import Path\n'
        'from src.menubar import menubar_log\n'
        f'menubar_log.MENUBAR_LOG = Path({str(target)!r})\n'
        "menubar_log.log_menubar('hotkey', 'cmd+4 \\u2192 focus')\n"
    )
    env = dict(os.environ, LC_ALL='C', PYTHONUTF8='0', PYTHONCOERCECLOCALE='0')
    env.pop('LANG', None)
    r = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True)
    written = target.read_bytes() if target.exists() else b''
    check('click.log_writes_non_ascii_under_ascii_locale', '→'.encode() in written, f'stderr={r.stderr.strip()[:120]!r}')


main()
