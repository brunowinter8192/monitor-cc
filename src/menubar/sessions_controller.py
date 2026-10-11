# INFRASTRUCTURE

from src.menubar.discovery_worker import get_latest_snapshot

# FUNCTIONS

class SessionsController:
    def __init__(self, app) -> None:
        self.app = app
        self._last_sessions: list = []
        self._last_bg_by_project: dict = {}

    def refresh(self) -> list:
        snapshot = get_latest_snapshot()
        self._last_sessions = snapshot.sessions
        self._last_bg_by_project = snapshot.bg_by_project
        return snapshot.sessions

    def tmux_session_for(self, encoded_dir: str) -> str:
        for s in self._last_sessions:
            if s.is_worker and s.encoded_dir == encoded_dir:
                return s.tmux_session_name
        return ''

    @property
    def data(self) -> list:
        return self._last_sessions

    @property
    def bg_by_project(self) -> dict:
        return self._last_bg_by_project
