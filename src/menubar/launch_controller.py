# INFRASTRUCTURE
import threading

from AppKit import NSAttributedString, NSFontAttributeName
from Foundation import NSMakeRect

from .launch_config import LAUNCH_DESKTOPS, LAUNCH_PROJECTS
from .launch_panel_ui import (_make_launch_nspanel, _make_desktop_row, _make_project_button)
from .menubar_log import log_menubar
from .panel import _TOP_BAR_H, _ROW_H, _LABEL_H, _MENLO, _make_line_separator
from .panel_lifecycle import _close_launch_panel
from .panel_tabs import tab_header_text
from .session_launch import launch_workflow

# FUNCTIONS

def occupied_desktops(sessions) -> frozenset:
    return frozenset(s.desktop_no for s in sessions
                     if not s.is_worker and s.desktop_no is not None)

class LaunchController:
    def __init__(self, app) -> None:
        self.app = app
        self._launch_open: bool = False
        self._launch_panel, self._launch_sv, self._launch_header_btn = _make_launch_nspanel()
        self._selected_desktop = None
        self._occupied = frozenset()
        self._desktop_btns = {}
        self._launch_in_progress: bool = False

    def open(self) -> None:
        self._selected_desktop = None
        self.rebuild(self.app.sessions.refresh())

    def tick(self, sessions) -> None:
        if not self._launch_open:
            return
        if occupied_desktops(sessions) != self._occupied:
            self.rebuild(sessions)

    def rebuild(self, sessions=None) -> None:
        app = self.app
        if sessions is None:
            sessions = app.sessions.refresh()
        for sv in list(self._launch_sv.arrangedSubviews()):
            self._launch_sv.removeView_(sv)
            sv.removeFromSuperview()
        self._occupied = occupied_desktops(sessions)
        if self._selected_desktop in self._occupied:
            self._selected_desktop = None
        pw = app.settings.panel_width
        self._launch_header_btn.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                tab_header_text('Launch'),
                {NSFontAttributeName: _MENLO()}))
        required_h = _TOP_BAR_H + _LABEL_H + _ROW_H + _LABEL_H + len(LAUNCH_PROJECTS) * _ROW_H
        self._resize_launch_panel(max(app.settings.panel_min_height, required_h))
        self._launch_sv.addView_inGravity_(_make_line_separator(pw), 1)
        row, self._desktop_btns = _make_desktop_row(
            pw, LAUNCH_DESKTOPS, self._occupied, self._selected_desktop, app._panel_controller)
        self._launch_sv.addView_inGravity_(row, 1)
        self._launch_sv.addView_inGravity_(_make_line_separator(pw), 1)
        for index, project in enumerate(LAUNCH_PROJECTS):
            self._launch_sv.addView_inGravity_(
                _make_project_button(pw, project, index, app._panel_controller), 1)

    def handle_select_desktop(self, desktop: int) -> None:
        if desktop not in LAUNCH_DESKTOPS or desktop in self._occupied:
            log_menubar('launch', f'select ignored desktop={desktop} occupied={sorted(self._occupied)}')
            return
        self._selected_desktop = desktop
        self.rebuild()

    def handle_launch_project(self, index: int) -> None:
        if self._launch_in_progress:
            log_menubar('launch', f'click ignored index={index} reason=launch_in_progress')
            return
        if self._selected_desktop is None:
            log_menubar('launch', f'click ignored index={index} reason=no_desktop_selected')
            return
        if not 0 <= index < len(LAUNCH_PROJECTS):
            log_menubar('launch', f'click ignored index={index} reason=index_out_of_range')
            return
        desktop = self._selected_desktop
        if desktop in occupied_desktops(self.app.sessions.refresh()):
            log_menubar('launch', f'click refused desktop={desktop} reason=desktop_occupied')
            self.rebuild()
            return
        project = LAUNCH_PROJECTS[index]
        self._selected_desktop = None
        _close_launch_panel(self.app)
        self._start_launch_thread(desktop, project)

    def _start_launch_thread(self, desktop: int, project: str) -> None:
        self._launch_in_progress = True
        threading.Thread(target=self._run_launch, args=(desktop, project), daemon=True).start()

    def _run_launch(self, desktop: int, project: str) -> None:
        try:
            launch_workflow(desktop, project)
        finally:
            self._launch_in_progress = False

    def _resize_launch_panel(self, new_h: float) -> None:
        w     = self.app.settings.panel_width
        frame = self._launch_panel.frame()
        top_y = frame.origin.y + frame.size.height
        self._launch_panel.setFrame_display_(
            NSMakeRect(frame.origin.x, top_y - new_h, w, new_h), False)
