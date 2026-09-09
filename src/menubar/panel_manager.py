# INFRASTRUCTURE
from collections import Counter
from itertools import groupby

from AppKit import (NSAttributedString, NSColor, NSFontAttributeName,
                    NSForegroundColorAttributeName, NSGridCell,
                    NSGridCellPlacementLeading, NSGridView)
from Foundation import NSMakeRect, NSRange

from .panel import (
    _make_nspanel,
    _MENLO, _BADGE_WORKING, _BADGE_IDLE,
    _ROW_H, _LABEL_H,
    _project_desktop_no, _compute_required_height,
    _make_line_separator, _make_header_label, _make_separator_view,
    _make_grid_cell_btn, _format_bg_badge)
from .panel_grid import (_GRID_COL0_W, _GRID_COL1_W, _GRID_COL3_W, _GRID_COL4_W,
                         _GRID_COL5_W, _GRID_COL_SPC)

# FUNCTIONS

class _PanelWidgets:
    def __init__(self, panel, stack, quit_btn, toggle_btn, kill_btn):
        self.panel = panel
        self.stack = stack
        self.quit_btn = quit_btn
        self.toggle_btn = toggle_btn
        self.kill_btn = kill_btn

class _PanelLookups:
    def __init__(self):
        self.displayed_items = {}
        self.cwd_map = {}
        self.worker_tag_map = {}
        self.desktop_to_cwd = {}
        self.abort_btns_by_project = {}
        self.abort_project_for_tag = {}

def _sorted_sessions(sessions):
    pdn = {pn: _project_desktop_no(sessions, pn) for pn in {s.project_name for s in sessions}}
    inf = float('inf')
    return sorted(
        sessions,
        key=lambda s: (
            pdn[s.project_name] if pdn[s.project_name] is not None else inf,
            s.project_name,
            s.is_worker,
            s.name,
        )
    )

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

class PanelManager:
    def __init__(self, app) -> None:
        self.app = app
        self._panel_open: bool = False
        self._panel_backgrounded: bool = False
        self._initialized: bool = False
        self._rebuild_in_progress: bool = False
        self._lookups = _PanelLookups()
        self._widgets = _PanelWidgets(*_make_nspanel())

    def rebuild(self, sessions, bg_by_project=None) -> None:
        if self._rebuild_in_progress:
            return
        self._rebuild_in_progress = True
        try:
            self._rebuild_inner(sessions, bg_by_project)
        finally:
            self._rebuild_in_progress = False

    def _rebuild_inner(self, sessions, bg_by_project=None) -> None:
        stack = self._widgets.stack
        for sv in list(stack.arrangedSubviews()):
            stack.removeView_(sv)
            sv.removeFromSuperview()
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

    def _populate_grid(self, grid, sorted_sessions, bg_by_project) -> None:
        empty = NSGridCell.emptyContentView()
        dno_counts = Counter(s.desktop_no for s in sorted_sessions
                             if not s.is_worker and s.desktop_no is not None)
        conflict_set = {dn for dn, c in dno_counts.items() if c > 1}
        next_tag  = [1]
        abort_tag = [1000]
        for project_name, group_iter in groupby(sorted_sessions, key=lambda s: s.project_name):
            proj_bg = (bg_by_project or {}).get(project_name)
            self._add_separator_row(grid, empty, project_name, proj_bg, abort_tag)
            for s in group_iter:
                tag = next_tag[0]; next_tag[0] += 1
                if not s.is_worker:
                    self._add_main_row(grid, empty, s, tag, conflict_set, proj_bg)
                else:
                    self._add_worker_row(grid, empty, s, tag)

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
        monitor_btn = _make_grid_cell_btn('mon', NSColor.systemBlueColor())
        monitor_btn.setTag_(tag)
        monitor_btn.setTarget_(self.app._panel_controller)
        monitor_btn.setAction_(b'openMonitor:')
        views = [slot_btn, star_btn, name_btn, dot_btn,
                 badge_btn if badge_btn is not None else empty, monitor_btn]
        grid.addRowWithViews_(views)
        grid.rowAtIndex_(grid.numberOfRows() - 1).setHeight_(float(_ROW_H - 1))
        self._lookups.displayed_items[s.name] = (dot_btn, badge_btn)

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

    def _resize_panel(self, new_h: float) -> None:
        w         = self.app.settings.panel_width
        frame     = self._widgets.panel.frame()
        top_y     = frame.origin.y + frame.size.height
        self._widgets.panel.setFrame_display_(
            NSMakeRect(frame.origin.x, top_y - new_h, w, new_h), False)
