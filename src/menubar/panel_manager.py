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
    _GRID_COL0_W, _GRID_COL1_W, _GRID_COL3_W, _GRID_COL4_W, _GRID_COL_SPC,
    _ROW_H, _LABEL_H,
    _project_desktop_no, _compute_required_height,
    _make_line_separator, _make_header_label, _make_separator_view,
    _make_grid_cell_btn, _format_bg_badge)

# FUNCTIONS

# Per-concern controller for main-session panel: lifecycle, state, render, coordinate mapping
class PanelManager:
    def __init__(self, app) -> None:
        self.app = app
        self._panel_open: bool = False
        self._initialized: bool = False
        self._displayed_items: dict = {}
        self._cwd_map: dict = {}
        self._desktop_to_cwd: dict = {}
        self._abort_btns_by_project: dict = {}
        self._abort_project_for_tag: dict = {}
        self._rebuild_in_progress: bool = False
        self._panel, self._panel_sv, self._panel_quit_btn, self._toggle_btn, self._panel_kill_btn = _make_nspanel()

    # Full panel rebuild; re-entry guard mirrors BeadController/QueueController pattern
    def rebuild(self, sessions, bg_by_project=None) -> None:
        if self._rebuild_in_progress:
            return
        self._rebuild_in_progress = True
        try:
            self._rebuild_inner(sessions, bg_by_project)
        finally:
            self._rebuild_in_progress = False

    # ONE NSGridView holds all project-separator + session/worker rows added to _panel_sv.
    # Populates _displayed_items, _cwd_map, _desktop_to_cwd, _abort_btns_by_project, _abort_project_for_tag.
    # bg_by_project: Dict[project_name, BgSleepInfo] from _scan_bg_sleep_timers(); None = no timers.
    # Separator rows merged across all 5 columns; worker rows leave cols 0/1/4 empty.
    def _rebuild_inner(self, sessions, bg_by_project=None) -> None:
        for sv in list(self._panel_sv.arrangedSubviews()):
            self._panel_sv.removeView_(sv)
            sv.removeFromSuperview()   # removeView_ removes from arrangedSubviews only; view persists as regular subview without this
        self._displayed_items = {}
        self._cwd_map = {}
        self._desktop_to_cwd = {}
        self._abort_btns_by_project = {}
        self._abort_project_for_tag = {}
        next_tag  = [1]
        abort_tag = 1000   # abort button tags start above session row tags (1..N)
        pw = self.app._panel_width
        _pdn = {pn: _project_desktop_no(sessions, pn)
                for pn in {s.project_name for s in sessions}}
        _INF = float('inf')
        sorted_sessions = sorted(
            sessions,
            key=lambda s: (
                _pdn[s.project_name] if _pdn[s.project_name] is not None else _INF,
                s.project_name,   # tie-break on conflict [!N]; keeps None-group order stable
                s.is_worker,      # mains (False) before workers (True) within project
                s.name,           # alphabetical within same type
            )
        )
        required_h = _compute_required_height(sorted_sessions)
        self._resize_panel(max(self.app._panel_min_height, required_h))
        state = 'ON' if self.app._auto_focus else 'OFF'
        self._toggle_btn.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                f'[Sessions] \u00b7 Beads \u00b7 Queue     Auto-Jump: {state}',
                {NSFontAttributeName: _MENLO()}))
        self._panel_sv.addView_inGravity_(_make_line_separator(pw), 1)
        if not sorted_sessions:
            self._panel_sv.addView_inGravity_(_make_header_label('No active sessions', pw), 1)
            return
        empty = NSGridCell.emptyContentView()
        grid  = NSGridView.gridViewWithNumberOfColumns_rows_(5, 0)
        grid.setColumnSpacing_(float(_GRID_COL_SPC))
        grid.setRowSpacing_(1.0)
        for i in range(5):
            grid.columnAtIndex_(i).setXPlacement_(NSGridCellPlacementLeading)
        grid.columnAtIndex_(0).setWidth_(float(_GRID_COL0_W))
        grid.columnAtIndex_(1).setWidth_(float(_GRID_COL1_W))
        grid.columnAtIndex_(3).setWidth_(float(_GRID_COL3_W))
        grid.columnAtIndex_(4).setWidth_(float(_GRID_COL4_W))
        grid.setTranslatesAutoresizingMaskIntoConstraints_(False)
        dno_counts   = Counter(s.desktop_no for s in sorted_sessions
                               if not s.is_worker and s.desktop_no is not None)
        conflict_set = {dn for dn, c in dno_counts.items() if c > 1}
        row_idx      = 0
        for project_name, group_iter in groupby(sorted_sessions, key=lambda s: s.project_name):
            proj_bg = (bg_by_project or {}).get(project_name)
            sep_view, abort_btn = _make_separator_view(
                project_name, pw, proj_bg.min_remaining if proj_bg else None)
            grid.addRowWithViews_([sep_view, empty, empty, empty, empty])
            grid.rowAtIndex_(row_idx).setHeight_(float(_LABEL_H - 1))
            grid.mergeCellsInHorizontalRange_verticalRange_(NSRange(0, 5), NSRange(row_idx, 1))
            row_idx += 1
            if abort_btn is not None:
                abort_btn.setTag_(abort_tag)
                abort_btn.setTarget_(self.app._panel_controller)
                abort_btn.setAction_(b'abortBgTimer:')
                self._abort_btns_by_project[project_name] = abort_btn
                self._abort_project_for_tag[abort_tag] = project_name
                abort_tag += 1
            for s in group_iter:
                dot   = _BADGE_WORKING if s.status == 'working' else _BADGE_IDLE
                color = NSColor.systemOrangeColor()
                if not s.is_worker:
                    dno = s.desktop_no
                    if dno is None:
                        slot_str   = ''
                        slot_color = color
                    elif dno in conflict_set:
                        slot_str   = f'[!{dno}]'
                        slot_color = NSColor.systemRedColor()
                    else:
                        slot_str   = f'[{dno}]'
                        slot_color = color
                    tag      = next_tag[0]; next_tag[0] += 1
                    slot_btn = _make_grid_cell_btn(slot_str, slot_color)
                    star_btn = _make_grid_cell_btn('*', color)
                    name_btn = _make_grid_cell_btn(s.name, color)
                    dot_btn  = _make_grid_cell_btn(dot, color)
                    for btn in (slot_btn, star_btn, name_btn, dot_btn):
                        btn.setTag_(tag)
                        btn.setTarget_(self.app._panel_controller)
                        btn.setAction_(b'focusSession:')
                    self._cwd_map[tag] = s.cwd or ''
                    if dno is not None and dno not in conflict_set:
                        self._desktop_to_cwd[dno] = s.cwd or ''
                    if proj_bg is not None:
                        badge_btn = _make_grid_cell_btn(
                            _format_bg_badge(proj_bg.min_remaining), color)
                        badge_btn.setTag_(tag)
                        badge_btn.setTarget_(self.app._panel_controller)
                        badge_btn.setAction_(b'focusSession:')
                        views = [slot_btn, star_btn, name_btn, dot_btn, badge_btn]
                    else:
                        badge_btn = None
                        views     = [slot_btn, star_btn, name_btn, dot_btn, empty]
                    grid.addRowWithViews_(views)
                    grid.rowAtIndex_(row_idx).setHeight_(float(_ROW_H - 1))
                    row_idx += 1
                    self._displayed_items[s.name] = (dot_btn, badge_btn)
                else:
                    name_btn = _make_grid_cell_btn(s.name)
                    dot_btn  = _make_grid_cell_btn(dot)
                    grid.addRowWithViews_([empty, empty, name_btn, dot_btn, empty])
                    grid.rowAtIndex_(row_idx).setHeight_(float(_ROW_H - 1))
                    row_idx += 1
                    self._displayed_items[s.name] = (dot_btn, None)
        self._panel_sv.addView_inGravity_(grid, 1)
        grid.widthAnchor().constraintEqualToConstant_(float(pw)).setActive_(True)

    # In-place dot + badge update while panel is open; preserves grid layout
    def update_inplace(self, sessions, bg_by_project) -> None:
        session_map = {s.name: s for s in sessions}
        for name, (dot_btn, badge_btn) in self._displayed_items.items():
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

    # Resize NSPanel anchored at top edge; uses self.app._panel_width (setting stays on app)
    def _resize_panel(self, new_h: float) -> None:
        w         = self.app._panel_width
        frame     = self._panel.frame()
        top_y     = frame.origin.y + frame.size.height   # fix the TOP edge in screen coords
        self._panel.setFrame_display_(
            NSMakeRect(frame.origin.x, top_y - new_h, w, new_h), False)
