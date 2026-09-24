# FUNCTIONS

class FocusController:
    def __init__(self, app) -> None:
        self.app = app
        self._last_statuses: dict = {}

    def statuses_changed(self, sessions) -> bool:
        current = {s.name: s.status for s in sessions}
        return current != self._last_statuses

    def update_statuses(self, sessions) -> None:
        self._last_statuses = {s.name: s.status for s in sessions}
