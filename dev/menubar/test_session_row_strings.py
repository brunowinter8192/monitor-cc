# INFRASTRUCTURE
from collections import namedtuple
from types import SimpleNamespace

from AppKit import NSAttributedString, NSFontAttributeName
from Foundation import NSObject

from p5_common import load, check

_BgInfo = namedtuple('_BgInfo', ['min_remaining', 'sleep_pids'])

_COLUMNS = 7
_FIXED_COLUMNS = (0, 1, 3, 4, 5, 6)

_EXPECTED_ROWS_WAIT_7200 = [
    ['[3]', '*', 'alpha', '[ ]', '[B 120:00]', 'mon', 'skill'],
    [None, None, 'w-bg', '[*]', '[B]', None, None],
    [None, None, 'w-plain', '[ ]', None, None, None],
]

_EXPECTED_ROWS_WAIT_300 = [
    ['[3]', '*', 'alpha', '[ ]', '[B 5:00]', 'mon', 'skill'],
    [None, None, 'w-bg', '[*]', '[B]', None, None],
    [None, None, 'w-plain', '[ ]', None, None, None],
]

_EXPECTED_ROWS_NO_WAIT_MAIN_BG = [
    ['[3]', '*', 'alpha', '[ ]', '[B]', 'mon', 'skill'],
    [None, None, 'w-bg', '[*]', '[B]', None, None],
    [None, None, 'w-plain', '[ ]', None, None, None],
]

_EXPECTED_ROWS_NO_WAIT_NO_MAIN_BG = [
    ['[3]', '*', 'alpha', '[ ]', None, 'mon', 'skill'],
    [None, None, 'w-bg', '[*]', '[B]', None, None],
    [None, None, 'w-plain', '[ ]', None, None, None],
]


# ORCHESTRATOR

def main() -> None:
    check_rows('wait 7200s remaining, main has bg', 7200, True, _EXPECTED_ROWS_WAIT_7200)
    check_rows('wait 300s remaining, main has bg', 300, True, _EXPECTED_ROWS_WAIT_300)
    check_rows('wait 300s remaining, main without bg', 300, False, _EXPECTED_ROWS_WAIT_300)
    check_rows('no wait, main has bg', None, True, _EXPECTED_ROWS_NO_WAIT_MAIN_BG)
    check_rows('no wait, main without bg', None, False, _EXPECTED_ROWS_NO_WAIT_NO_MAIN_BG)
    check_bg_change_detection()
    check_main_bg_change_detection()
    check_active_bg_ignores_path_case()


# FUNCTIONS

def check_rows(label: str, remaining, main_has_bg: bool, expected_rows: list) -> None:
    pm = rendered_panel(make_sessions(main_has_bg), bg_by_project(remaining))
    grid = session_grid(pm)
    actual = session_row_titles(grid)
    check(f'{label}: row strings', actual == expected_rows, f'{actual!r}')
    check(f'{label}: abort label', abort_label(pm) == expected_abort_label(remaining),
          f'{abort_label(pm)!r}')
    check(f'{label}: titles fit buttons', not clipped_titles(grid), f'{clipped_titles(grid)!r}')


def rendered_panel(sessions: list, bg: dict):
    pm = load('panel_manager').PanelManager(FakeApp())
    pm.rebuild(sessions, bg)
    pm._widgets.panel.contentView().layoutSubtreeIfNeeded()
    return pm


def session_grid(pm):
    grids = [v for v in pm._widgets.stack.arrangedSubviews() if hasattr(v, 'numberOfRows')]
    check('one session grid', len(grids) == 1, f'found {len(grids)}')
    return grids[0]


def session_row_titles(grid) -> list:
    return [[cell_title(grid.cellAtColumnIndex_rowIndex_(c, r).contentView())
             for c in range(_COLUMNS)]
            for r in range(1, grid.numberOfRows())]


def cell_title(view):
    if view is None:
        return None
    return str(view.attributedTitle().string())


def abort_label(pm):
    button = pm._lookups.abort_btns_by_project.get('alpha')
    return None if button is None else str(button.attributedTitle().string())


def expected_abort_label(remaining):
    return None if remaining is None else 'abort'


def clipped_titles(grid) -> list:
    clipped = []
    for row in range(1, grid.numberOfRows()):
        for column in _FIXED_COLUMNS:
            view = grid.cellAtColumnIndex_rowIndex_(column, row).contentView()
            if view is not None and title_width(view) > view.frame().size.width:
                clipped.append((row, column, cell_title(view)))
    return clipped


def title_width(view) -> float:
    font = load('panel')._MENLO()
    return NSAttributedString.alloc().initWithString_attributes_(
        cell_title(view), {NSFontAttributeName: font}).size().width


def check_bg_change_detection() -> None:
    sessions = make_sessions(True)
    wait = bg_by_project(300)
    pm = rendered_panel(sessions, wait)
    check('worker bg unchanged after rebuild', not pm.bg_indicator_changed(sessions, wait))
    gained = [s._replace(has_bg=True) if s.name == 'w-plain' else s for s in sessions]
    check('worker bg gained is detected', pm.bg_indicator_changed(gained, wait))
    lost = [s._replace(has_bg=False) if s.name == 'w-bg' else s for s in sessions]
    check('worker bg lost is detected', pm.bg_indicator_changed(lost, wait))


def check_main_bg_change_detection() -> None:
    idle = bg_by_project(None)
    with_bg = make_sessions(True)
    pm = rendered_panel(with_bg, idle)
    check('main bg unchanged after rebuild', not pm.bg_indicator_changed(with_bg, idle))
    lost = [s._replace(has_bg=False) if s.name == 'alpha' else s for s in with_bg]
    check('main bg lost is detected', pm.bg_indicator_changed(lost, idle))
    without_bg = make_sessions(False)
    pm = rendered_panel(without_bg, idle)
    check('main without bg unchanged after rebuild', not pm.bg_indicator_changed(without_bg, idle))
    check('main bg gained is detected', pm.bg_indicator_changed(with_bg, idle))
    pm = rendered_panel(without_bg, bg_by_project(300))
    check('main bg gained under countdown needs no rebuild',
          not pm.bg_indicator_changed(with_bg, bg_by_project(300)))
    pm = rendered_panel(with_bg, bg_by_project(300))
    check('main countdown ending with bg is detected', pm.bg_indicator_changed(with_bg, idle))


def check_active_bg_ignores_path_case() -> None:
    proc_cache = load('proc_cache')
    saved = proc_cache._bg_task_open_paths
    try:
        base = proc_cache._TASKS_BASE_REAL
        proc_cache._bg_task_open_paths = {f'{base}/-Users-x-ai-monitor-cc/sess1/tasks/a.output'}
        check('bg detected when project dir name differs only by case',
              proc_cache._has_active_bg('-Users-x-ai-Monitor-CC', 'sess1'))
        check('bg not detected for another session in a case-different dir',
              not proc_cache._has_active_bg('-Users-x-ai-Monitor-CC', 'sess2'))
    finally:
        proc_cache._bg_task_open_paths = saved


def make_sessions(main_has_bg: bool = True) -> list:
    info = load('discover').SessionInfo
    return [
        info(name='alpha', status='idle', has_bg=main_has_bg, encoded_dir='-alpha',
             project_name='alpha', is_worker=False, cwd='/tmp/alpha', session_id='s1',
             tmux_session_name='', desktop_no=3),
        info(name='w-bg', status='working', has_bg=True, encoded_dir='-alpha-w-bg',
             project_name='alpha', is_worker=True, cwd='', session_id='s2',
             tmux_session_name='worker-alpha-w-bg', desktop_no=None),
        info(name='w-plain', status='idle', has_bg=False, encoded_dir='-alpha-w-plain',
             project_name='alpha', is_worker=True, cwd='', session_id='s3',
             tmux_session_name='worker-alpha-w-plain', desktop_no=None),
    ]


def bg_by_project(remaining) -> dict:
    if remaining is None:
        return {}
    return {'alpha': _BgInfo(min_remaining=remaining, sleep_pids=(4321,))}


class FakePanelController(NSObject):
    pass


class FakeApp:
    def __init__(self):
        self.settings = SimpleNamespace(panel_width=422, panel_min_height=460)
        self._panel_controller = FakePanelController.alloc().init()


if __name__ == '__main__':
    main()
