# INFRASTRUCTURE
from .system import _focus_session

# FUNCTIONS

class FocusController:
    def __init__(self, app) -> None:
        self.app = app
        self._idle_since_ts: dict = {}
        self._last_statuses: dict = {}

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

    def statuses_changed(self, sessions) -> bool:
        current = {s.name: s.status for s in sessions}
        return current != self._last_statuses

    def update_statuses(self, sessions) -> None:
        self._last_statuses = {s.name: s.status for s in sessions}
