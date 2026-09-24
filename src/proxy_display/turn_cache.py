# FUNCTIONS

class TurnCache:
    def __init__(self, name: str = 'proxy_display'):
        self.name = name
        self.clear()

    def clear(self) -> None:
        self.records = {}
        self.flat = None
        self.flow_turns = None
        self.flow_key = None
        self.flow_maps = None
        self.assign_path = None
