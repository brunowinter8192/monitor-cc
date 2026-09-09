# INFRASTRUCTURE
from collections import Counter
from itertools import groupby

from AppKit import (NSAttributedString, NSColor, NSFontAttributeName,
                    NSForegroundColorAttributeName, NSGridCell,
                    NSGridCellPlacementLeading, NSGridView)
from Foundation import NSMakeRect, NSRange

# From panel.py: NSPanel factory, layout constants, pure render helpers
from .panel import (
    _make_nspanel,
    _MENLO, _BADGE_WORKING, _BADGE_IDLE,
    _ROW_H, _LABEL_H,
    _project_desktop_no, _compute_required_height,
    _make_line_separator, _make_header_label, _make_separator_view,
    _make_grid_cell_btn, _format_bg_badge)
# From panel_grid.py: main-panel NSGridView column geometry (_GRID_* constant cluster)
from .panel_grid import (_GRID_COL0_W, _GRID_COL1_W, _GRID_COL3_W, _GRID_COL4_W,
                         _GRID_COL5_W, _GRID_COL_SPC)

# FUNCTIONS

# The 5 NSPanel/NSStackView/NSButton refs _make_nspanel() returns together — created together,
# read together by app.py/panel_lifecycle.py for lifecycle/wiring.
class _PanelWidgets:
    def __init__(self, panel, stack, quit_btn, toggle_btn, kill_btn):
        self.panel = panel
        self.stack = stack
        self.quit_btn = quit_btn
        self.toggle_btn = toggle_btn
        self.kill_btn = kill_btn

# The 6 per-rebuild lookup maps — rebuilt together (fresh instance each _rebuild_inner call),
# cleared together, read by app.py/_PanelController/panel_lifecycle.py for click routing.
class _PanelLookups:
    def __init__(self):
        self.displayed_items = {}          # session name -> (dot_btn, badge_btn)
        self.cwd_map = {}                  # tag -> cwd (main-row click routing)
        self.worker_tag_map = {}           # tag -> tmux_session_name (worker-row click routing)
        self.desktop_to_cwd = {}           # real desktop number -> cwd (Cmd+N routing, conflict-free only)
        self.abort_btns_by_project = {}    # project_name -> abort NSButton
        self.abort_project_for_tag = {}    # abort button tag -> project_name

# Effective sort order: (project desktop number or +inf, project_name, is_worker, name) —
# desktop-ordered, detection-failed projects last, mains before workers within a project.
def _sorted_sessions(sessions):
    pdn = {pn: _project_desktop_no(sessions, pn) for pn in {s.project_name for s in sessions}}
    inf = float('inf')
    return sorted(
        sessions,
        key=lambda s: (
            pdn[s.project_name] if pdn[s.project_name] is not None else inf,
            s.project_name,   # tie-break on conflict [!N]; keeps None-group order stable
            s.is_worker,      # mains (False) before workers (True) within project
            s.name,           # alphabetical within same type
        )
    )

# 6-column NSGridView shell for the session list — leading-aligned columns, fixed widths on
# 0/1/3/4/5 (col 2, the name column, stays flexible).
def _make_session_grid() -> NSGridView:
    grid = NSGridView.gridViewWithNumberOfColumns_rows_(6, 0)
    grid.setColumnSpacing_(float(_GRID_COL_SPC))
    grid.setRowSpacing_(1.0)
    for i in range(6):
        grid.columnAtIndex_(i).setXPlacement_(NSGridCellPlacementLeading)
    grid.columnAtIndex_(0).setWidth_(float(_GRID_COL0_W))
    grid.columnAtIndex_(1).setWidth_(float(_GRID_COL1_W))
    grid.columnAtIndex_(3).setWidth_(float(_GRID_COL3_W))
    grid.columnAtIndex_(4).setWidth_(float(_GRID_COL4_W))
    grid.columnAtIndex_(5).setWidth_(float(_GRID_COL5_W))
    grid.setTranslatesAutoresizingMaskIntoConstraints_(False)
    return grid

# Per-concern controller for main-session panel: lifecycle, state, render, coordinate mapping
class PanelManager:
    def __init__(self, app) -> None:
        self.app = app
        self._panel_open: bool = False
        self._panel_backgrounded: bool = False   # True while panel is orderBack_'d behind other windows (Cmd+K); sibling of _panel_open
        self._initialized: bool = False
        self._rebuild_in_progress: bool = False
        self._lookups = _PanelLookups()
        self._widgets = _PanelWidgets(*_make_nspanel())

    # Full panel rebuild; re-entry guard mirrors RagController pattern
    def rebuild(self, sessions, bg_by_project=None) -> None:
        if self._rebuild_in_progress:
            return
        self._rebuild_in_progress = True
        try:
            self._rebuild_inner(sessions, bg_by_project)
        finally:
            self._rebuild_in_progress = False

    # ONE NSGridView holds all project-separator + session/worker rows added to _widgets.stack.
    # Populates self._lookups (displayed_items/cwd_map/worker_tag_map/desktop_to_cwd/
    # abort_btns_by_project/abort_project_for_tag) — see _populate_grid + its row helpers.
    # bg_by_project: Dict[project_name, BgSleepInfo] from _scan_bg_sleep_timers(); None = no timers.
    def _rebuild_inner(self, sessions, bg_by_project=None) -> None:
        stack = self._widgets.stack
        for sv in list(stack.arrangedSubviews()):
            stack.removeView_(sv)
            sv.removeFromSuperview()   # removeView_ removes from arrangedSubviews only; view persists as regular subview without this
        self._lookups = _PanelLookups()
        pw = self.app.settings.panel_width
        sorted_sessions = _sorted_sessions(sessions)
        required_h = _compute_required_height(sorted_sessions)
        self._resize_panel(max(self.app.settings.panel_min_height, required_h))
        self._set_toggle_title()
        stack.addView_inGravity_(_make_line_separator(pw), 1)
        if not sorted_sessions:
            stack.addView_inGravity_(_make_header_label('No active sessions', pw), 1)
            return
        grid = _make_session_grid()
        self._populate_grid(grid, sorted_sessions, bg_by_project)
        stack.addView_inGravity_(grid, 1)
        grid.widthAnchor().constraintEqualToConstant_(float(pw)).setActive_(True)

    def _set_toggle_title(self) -> None:
        state = 'ON' if self.app.settings.auto_focus else 'OFF'
        self._widgets.toggle_btn.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                f'[Sessions] · RAG · Models     Auto-Jump: {state}',
                {NSFontAttributeName: _MENLO()}))

    # Per-project separator row + one row per session (main or worker); conflict_set drives
    # [!N] red rendering (2+ mains sharing a desktop number).
    def _populate_grid(self, grid, sorted_sessions, bg_by_project) -> None:
        empty = NSGridCell.emptyContentView()
        dno_counts = Counter(s.desktop_no for s in sorted_sessions
                             if not s.is_worker and s.desktop_no is not None)
        conflict_set = {dn for dn, c in dno_counts.items() if c > 1}
        next_tag  = [1]
        abort_tag = [1000]   # abort button tags start above session row tags (1..N)
        for project_name, group_iter in groupby(sorted_sessions, key=lambda s: s.project_name):
            proj_bg = (bg_by_project or {}).get(project_name)
            self._add_separator_row(grid, empty, project_name, proj_bg, abort_tag)
            for s in group_iter:
                tag = next_tag[0]; next_tag[0] += 1
                if not s.is_worker:
                    self._add_main_row(grid, empty, s, tag, conflict_set, proj_bg)
                else:
                    self._add_worker_row(grid, empty, s, tag)

    # Separator row merged across all 6 columns; embeds the per-project abort button (Option B)
    # when a bg timer is running — zero extra height cost.
    def _add_separator_row(self, grid, empty, project_name, proj_bg, abort_tag) -> None:
        pw = self.app.settings.panel_width
        sep_view, abort_btn = _make_separator_view(
            project_name, pw, proj_bg.min_remaining if proj_bg else None)
        grid.addRowWithViews_([sep_view, empty, empty, empty, empty, empty])
        row_idx = grid.numberOfRows() - 1
        grid.rowAtIndex_(row_idx).setHeight_(float(_LABEL_H - 1))
        grid.mergeCellsInHorizontalRange_verticalRange_(NSRange(0, 6), NSRange(row_idx, 1))
        if abort_btn is not None:
            abort_btn.setTag_(abort_tag[0])
            abort_btn.setTarget_(self.app._panel_controller)
            abort_btn.setAction_(b'abortBgTimer:')
            self._lookups.abort_btns_by_project[project_name] = abort_btn
            self._lookups.abort_project_for_tag[abort_tag[0]] = project_name
            abort_tag[0] += 1

    # Main-session row: slot/star/name/dot(+badge)/monitor columns, all sharing one click tag.
    def _add_main_row(self, grid, empty, s, tag, conflict_set, proj_bg) -> None:
        dot   = _BADGE_WORKING if s.status == 'working' else _BADGE_IDLE
        color = NSColor.systemOrangeColor()
        dno = s.desktop_no
        if dno is None:
            slot_str, slot_color = '', color
        elif dno in conflict_set:
            slot_str, slot_color = f'[!{dno}]', NSColor.systemRedColor()
        else:
            slot_str, slot_color = f'[{dno}]', color
        slot_btn = _make_grid_cell_btn(slot_str, slot_color)
        star_btn = _make_grid_cell_btn('*', color)
        name_btn = _make_grid_cell_btn(s.name, color)
        dot_btn  = _make_grid_cell_btn(dot, color)
        for btn in (slot_btn, star_btn, name_btn, dot_btn):
            btn.setTag_(tag)
            btn.setTarget_(self.app._panel_controller)
            btn.setAction_(b'focusSession:')
        self._lookups.cwd_map[tag] = s.cwd or ''
        if dno is not None and dno not in conflict_set:
            self._lookups.desktop_to_cwd[dno] = s.cwd or ''
        if proj_bg is not None:
            badge_btn = _make_grid_cell_btn(_format_bg_badge(proj_bg.min_remaining), color)
            badge_btn.setTag_(tag)
            badge_btn.setTarget_(self.app._panel_controller)
            badge_btn.setAction_(b'focusSession:')
        else:
            badge_btn = None
        # Monitor column: launches/focuses 'python3 workflow.py --project <cwd>' for this row's
        # project (system.py:_open_or_focus_monitor). Own column (not the badge slot) — badge
        # already carries bg-task-remaining state and is absent on most rows; overloading it
        # would mix two unrelated meanings and hide the launch control whenever a badge shows.
        monitor_btn = _make_grid_cell_btn('mon', NSColor.systemBlueColor())
        monitor_btn.setTag_(tag)
        monitor_btn.setTarget_(self.app._panel_controller)
        monitor_btn.setAction_(b'openMonitor:')
        views = [slot_btn, star_btn, name_btn, dot_btn,
                 badge_btn if badge_btn is not None else empty, monitor_btn]
        grid.addRowWithViews_(views)
        grid.rowAtIndex_(grid.numberOfRows() - 1).setHeight_(float(_ROW_H - 1))
        self._lookups.displayed_items[s.name] = (dot_btn, badge_btn)

    # Worker row: click focuses the Ghostty viewer window running
    # 'tmux attach -t <tmux_session_name>' — see system.py:_focus_worker. Cols 0/1/4/5 empty.
    def _add_worker_row(self, grid, empty, s, tag) -> None:
        dot = _BADGE_WORKING if s.status == 'working' else _BADGE_IDLE
        name_btn = _make_grid_cell_btn(s.name)
        dot_btn  = _make_grid_cell_btn(dot)
        for btn in (name_btn, dot_btn):
            btn.setTag_(tag)
            btn.setTarget_(self.app._panel_controller)
            btn.setAction_(b'focusWorker:')
        self._lookups.worker_tag_map[tag] = s.tmux_session_name
        grid.addRowWithViews_([empty, empty, name_btn, dot_btn, empty, empty])
        grid.rowAtIndex_(grid.numberOfRows() - 1).setHeight_(float(_ROW_H - 1))
        self._lookups.displayed_items[s.name] = (dot_btn, None)

    # In-place dot + badge update while panel is open; preserves grid layout
    def update_inplace(self, sessions, bg_by_project) -> None:
        session_map = {s.name: s for s in sessions}
        for name, (dot_btn, badge_btn) in self._lookups.displayed_items.items():
            s = session_map.get(name)
            if s is None:
                continue
            proj_bg = (bg_by_project or {}).get(s.project_name)
            dot     = _BADGE_WORKING if s.status == 'working' else _BADGE_IDLE
            attrs   = {NSFontAttributeName: _MENLO()}
            if not s.is_worker:
                attrs[NSForegroundColorAttributeName] = NSColor.systemOrangeColor()
            dot_btn.setAttributedTitle_(
                NSAttributedString.alloc().initWithString_attributes_(dot, attrs))
            if badge_btn is not None and proj_bg is not None:
                badge_btn.setAttributedTitle_(
                    NSAttributedString.alloc().initWithString_attributes_(
                        _format_bg_badge(proj_bg.min_remaining),
                        {NSFontAttributeName: _MENLO(),
                         NSForegroundColorAttributeName: NSColor.systemOrangeColor()}))

    # Resize NSPanel anchored at top edge; uses self.app.settings.panel_width (setting stays on app)
    def _resize_panel(self, new_h: float) -> None:
        w         = self.app.settings.panel_width
        frame     = self._widgets.panel.frame()
        top_y     = frame.origin.y + frame.size.height   # fix the TOP edge in screen coords
        self._widgets.panel.setFrame_display_(
            NSMakeRect(frame.origin.x, top_y - new_h, w, new_h), False)
