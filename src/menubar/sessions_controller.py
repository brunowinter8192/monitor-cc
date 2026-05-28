# INFRASTRUCTURE

# From discover.py: Live session discovery
from .discover import list_alive_sessions

# FUNCTIONS

# Cache for list_alive_sessions() results; one snapshot per tick
class SessionsController:
    def __init__(self, app) -> None:
        self.app = app
        self._last_sessions: list = []

    # Call list_alive_sessions(), update cache, return new snapshot
    def refresh(self) -> list:
        sessions = list_alive_sessions()
        self._last_sessions = sessions
        return sessions

    @property
    def data(self) -> list:
        return self._last_sessions
