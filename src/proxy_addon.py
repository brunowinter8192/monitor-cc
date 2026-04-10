# Thin entry point — mitmproxy loads this file via -s proxy_addon.py / -s .proxy_addon_live.py
# All logic lives in src/proxy/ package. This file just sets up the import path and re-exports.
import sys
from pathlib import Path

# Ensure src/ is in sys.path so the `proxy` package (src/proxy/) is importable
# Live-copies live in src/logs/ — check for a frozen package copy FIRST, then walk up.
_here = Path(__file__).resolve().parent
_stem = Path(__file__).stem  # e.g. ".proxy_addon_live_abc12345" or "proxy_addon"
_src_dir = None

# If running as a live-copy, look for the frozen proxy package in the co-located live dir
if '_live_' in _stem:
    _session_id = _stem.rsplit('_', 1)[-1]
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

from proxy.addon import ProxyAddon, addons  # noqa: E402
from proxy.rules import apply_modification_rules  # noqa: E402
