# INFRASTRUCTURE
import sys
from pathlib import Path

_here = Path(__file__).resolve().parent
_stem = Path(__file__).stem
_src_dir = None

if '_live_' in _stem:
    _session_id = _stem.split('_live_', 1)[-1]
    _live_dir = _here / f'.proxy_live_{_session_id}'
    if (_live_dir / 'proxy').is_dir():
        _src_dir = str(_live_dir)

if _src_dir is None:
    for _candidate in [_here, _here.parent, _here.parent.parent]:
        if (_candidate / 'proxy').is_dir():
            _src_dir = str(_candidate)
            break
    else:
        _src_dir = str(_here)

if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from proxy.addon import ProxyAddon, addons
from proxy.rules import apply_modification_rules
