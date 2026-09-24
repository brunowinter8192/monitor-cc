# INFRASTRUCTURE
import sys
from pathlib import Path

_LIVE_MARKER = '_live_'

# ORCHESTRATOR

def bootstrap_paths() -> None:
    package_dir, repo_root = _resolve_layout(Path(__file__))
    _require_package(package_dir)
    _prepend_paths(package_dir, repo_root)

# FUNCTIONS

def _resolve_layout(shim_path: Path) -> tuple:
    here = shim_path.resolve().parent
    stem = shim_path.stem
    if _LIVE_MARKER in stem:
        session_id = stem.split(_LIVE_MARKER, 1)[-1]
        return here / f'.proxy_live_{session_id}', here.parent.parent
    return here, here.parent

def _require_package(package_dir: Path) -> None:
    if not (package_dir / 'proxy').is_dir():
        raise FileNotFoundError(f'proxy package not found under {package_dir}')

def _prepend_paths(package_dir: Path, repo_root: Path) -> None:
    for entry in (str(repo_root), str(package_dir)):
        if entry not in sys.path:
            sys.path.insert(0, entry)

bootstrap_paths()

from proxy.addon import ProxyAddon, addons
from proxy.rules import apply_modification_rules
