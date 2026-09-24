# INFRASTRUCTURE
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from dev.skill_picker.t1_fixtures import _imp

# FUNCTIONS

def _case_menu() -> str:
    sc = _imp('skill_controller')
    sd = _imp('skill_discovery')
    S = sd.Skill
    skills = [S('penny', 'penny', 'project'), S('mine', 'mine', 'personal'),
              S('a', 'p:a', 'plugin'), S('b', 'p:b', 'plugin')]
    menu = sc._build_menu(skills, None)
    items = list(menu.itemArray())
    kinds = ['sep' if i.isSeparatorItem() else str(i.title()) for i in items]
    assert kinds == ['penny', 'sep', 'mine', 'sep', 'a', 'b'], f'kinds {kinds}'
    reps = [str(i.representedObject()) for i in items if not i.isSeparatorItem()]
    assert reps == ['penny', 'mine', 'p:a', 'p:b'], reps
    assert all(str(i.action()).strip("b'") == 'insertSkill:' for i in items if not i.isSeparatorItem()), [i.action() for i in items]
    empty = list(sc._build_menu([], None).itemArray())
    assert len(empty) == 1 and str(empty[0].title()) == 'no skills' and not empty[0].isEnabled(), empty
    return f'titles {kinds}, represented full names {reps}, empty list -> one disabled "no skills"'

class _FakeApp:
    def __init__(self, sessions=None):
        self.settings = SimpleNamespace(panel_width=422, panel_min_height=460)
        self._panel_controller = None

def _find_grid(pm):
    for v in pm._widgets.stack.arrangedSubviews():
        if hasattr(v, 'numberOfColumns'):
            return v
    raise AssertionError('no grid in stack')

def _case_grid() -> str:
    pm_mod = _imp('panel_manager')
    S = _imp('discover').SessionInfo
    main = S('alpha', 'idle', False, '-a', 'alpha', False, '/tmp/alpha', 's1', '', 2)
    other = S('beta', 'working', False, '-b', 'beta', False, '/tmp/beta', 's2', '', None)
    worker = S('w1', 'idle', False, '-a-w', 'alpha', True, '', 's3', 'worker-alpha-w1', None)
    app = _FakeApp()
    pm = pm_mod.PanelManager(app)
    pm.rebuild([main, other, worker], {})
    grid = _find_grid(pm)
    assert grid.numberOfColumns() == 7, grid.numberOfColumns()
    rows = []
    for r in range(grid.numberOfRows()):
        rows.append([grid.cellAtIndex_(r, c) if False else grid.cellAtColumnIndex_rowIndex_(c, r) for c in range(7)])
    main_rows = [cells for cells in rows if cells[6].contentView() is not None and hasattr(cells[6].contentView(), 'title')
                 and str(cells[6].contentView().attributedTitle().string()) == 'skill']
    assert len(main_rows) == 2, f'skill buttons on {len(main_rows)} rows, want 2 main rows'
    for cells in main_rows:
        btn = cells[6].contentView()
        assert str(btn.action()).strip("b'") == 'showSkillMenu:', btn.action()
        assert btn.tag() == cells[5].contentView().tag(), 'skill tag differs from the mon tag of the row'
        assert str(cells[5].contentView().attributedTitle().string()) == 'mon', 'skill button is not right after mon'
    cwd_by_tag = pm._lookups.cwd_map
    assert sorted(cwd_by_tag.values()) == ['/tmp/alpha', '/tmp/beta'], cwd_by_tag
    worker_rows = [cells for cells in rows if cells[2].contentView() is not None
                   and hasattr(cells[2].contentView(), 'attributedTitle')
                   and str(cells[2].contentView().attributedTitle().string()) == 'w1']
    assert len(worker_rows) == 1, f'worker rows {len(worker_rows)}'
    worker_cell = worker_rows[0][6].contentView()
    assert worker_cell is None or not hasattr(worker_cell, 'attributedTitle'), 'worker row has a button in column 6'
    return f'7 columns, skill button on both main rows right after mon with matching tag, cwd_map {cwd_by_tag}, worker row column 6 empty'

def _case_controller() -> str:
    sc = _imp('skill_controller')
    app = SimpleNamespace(_panel_controller='CTL')
    ctl = sc.SkillController(app)
    logs = []
    inserted = []
    with patch.object(sc, 'log_menubar', lambda c, m: logs.append((c, m))), \
         patch.object(sc, 'insert_skill_workflow', lambda cwd, full: inserted.append((cwd, full))), \
         patch.object(sc, 'discover_skills_workflow', lambda cwd: [_imp('skill_discovery').Skill('a', 'p:a', 'plugin')]):
        button = MagicMock()
        button.bounds.return_value = SimpleNamespace(size=SimpleNamespace(height=20.0))
        ctl.show_menu(button, '')
        assert logs and logs[-1][1].startswith('FAILED stage=menu detail=no_cwd_for_row'), logs
        fake_menu = MagicMock()
        with patch.object(sc, '_build_menu', lambda skills, target: (fake_menu if target == 'CTL' else None)):
            ctl.show_menu(button, '/p/x')
        assert fake_menu.popUpMenuPositioningItem_atLocation_inView_.call_count == 1
        args = fake_menu.popUpMenuPositioningItem_atLocation_inView_.call_args[0]
        assert args[0] is None and args[2] is button and args[1].y == 20.0 and args[1].x == 0.0, args
        assert ctl._menu_cwd == '/p/x'
        item = MagicMock()
        item.representedObject.return_value = 'p:a'
        ctl.handle_choice(item)
        assert inserted == [('/p/x', 'p:a')], inserted
        item.representedObject.return_value = None
        ctl.handle_choice(item)
        assert len(inserted) == 1 and 'missing_choice' in logs[-1][1], (inserted, logs)
    return 'no cwd -> FAILED and no menu; menu popped at the button bottom-left with the controller as target; choice inserts for the clicked row; missing choice -> FAILED'

def _case_isolation() -> str:
    home = Path(os.environ['HOME'])
    log_mod = _imp('menubar_log')
    sd = _imp('skill_discovery')
    assert str(log_mod.MENUBAR_LOG).startswith(str(home)), log_mod.MENUBAR_LOG
    assert str(sd.CLAUDE_DIR).startswith(str(home)), sd.CLAUDE_DIR
    sd.discover_skills_workflow('/nonexistent/project')
    text = log_mod.MENUBAR_LOG.read_text() if log_mod.MENUBAR_LOG.exists() else ''
    assert 'settings_unreadable' in text, f'log {text!r}'
    return f'CLAUDE_DIR=<home>/{sd.CLAUDE_DIR.relative_to(home)} and MENUBAR_LOG under the isolated home; discovery log line landed there'
