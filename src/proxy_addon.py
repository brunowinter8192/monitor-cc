# INFRASTRUCTURE
import sys
from pathlib import Path

_LIVE_MARKER = '_live_'

# ORCHESTRATOR

def bootstrap_paths() -> None:
    import_root = _resolve_layout(Path(__file__))
    _require_package(import_root)
    _prepend_path(import_root)

# FUNCTIONS

def _resolve_layout(shim_path: Path) -> Path:
    here = shim_path.resolve().parent
    stem = shim_path.stem
    if _LIVE_MARKER in stem:
        session_id = stem.split(_LIVE_MARKER, 1)[-1]
        return here / f'.proxy_live_{session_id}'
    return here.parent

def _require_package(import_root: Path) -> None:
    if not (import_root / 'src' / 'proxy').is_dir():
        raise FileNotFoundError(f'proxy package not found under {import_root}')

def _prepend_path(import_root: Path) -> None:
    entry = str(import_root)
    if entry not in sys.path:
        sys.path.insert(0, entry)

bootstrap_paths()

from src.proxy.addon import ProxyAddon, addons
from src.proxy.rules import apply_modification_rules
