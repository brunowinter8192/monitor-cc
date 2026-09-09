# INFRASTRUCTURE
from pathlib import Path
from typing import Dict


class DualLogPaths:
    def __init__(self, original: Path, forwarded: Path, stripped: Path, injected: Path,
                 errors: Path, response: Path):
        self.original = original
        self.forwarded = forwarded
        self.stripped = stripped
        self.injected = injected
        self.errors = errors
        self.response = response


class DeltaState:
    def __init__(self):
        self.messages_by_model: Dict[str, list] = {}
        self.forwarded_hashes_by_model: dict = {}
        self.stripped_hashes_by_model: dict = {}
        self.injected_hashes_by_model: dict = {}
        self.error_ids_by_model: Dict[str, set] = {}


class FixationState:
    def __init__(self):
        self.fixated: dict = {}
        self.model_params_fixated: Dict[str, dict] = {}


class SessionIdentity:
    def __init__(self, session_id: str, worker_context: str):
        self.session_id = session_id
        self.worker_context = worker_context
