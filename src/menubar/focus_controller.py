# INFRASTRUCTURE
from .system import _focus_session

# FUNCTIONS

# Per-concern controller for auto-focus debounce (Step 5/6 of CCMenuBarApp composition refactor;
# auto-abort was removed 2026-08 — worker-cli wait is self-terminating, no menubar-side push-abort
# needed. Manual abort via the panel button stays live in bg_timer.py/app.py, unaffected by this.)
class FocusController:
    def __init__(self, app) -> None:
        self.app = app
        self._idle_since_ts: dict = {}
        self._last_statuses: dict = {}

    # Auto-focus: debounce idle main sessions (working→idle transition + 3s hold-off).
    # self._last_statuses holds the OLD snapshot — update_statuses() is called at tick-end.
    def tick(self, sessions, now: float) -> None:
        if not self.app.settings.auto_focus:
            return
        for s in sessions:
            if s.is_worker or not s.cwd:
                self._idle_since_ts.pop(s.name, None)
                continue
            if s.status == 'idle' and not s.has_bg:
                if s.name not in self._idle_since_ts:
                    if self._last_statuses.get(s.name) == 'working':
                        self._idle_since_ts[s.name] = now
                elif now - self._idle_since_ts[s.name] >= 3.0:
                    _focus_session(s.cwd)
                    del self._idle_since_ts[s.name]
            else:
                self._idle_since_ts.pop(s.name, None)

    # True if any session status differs from _last_statuses snapshot. Does NOT update snapshot.
    # Must be called BEFORE update_statuses() within the same tick.
    def statuses_changed(self, sessions) -> bool:
        current = {s.name: s.status for s in sessions}
        return current != self._last_statuses

    # Snapshot {name: status} into _last_statuses for next-tick comparison.
    # Called at tick-end (after all status reads for the current tick are complete).
    def update_statuses(self, sessions) -> None:
        self._last_statuses = {s.name: s.status for s in sessions}
