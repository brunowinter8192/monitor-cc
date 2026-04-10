# Thin entry point — mitmproxy loads this file via -s proxy_addon.py / -s .proxy_addon_live.py
# All logic lives in src/proxy/ package. This file just sets up the import path and re-exports.
import sys
from pathlib import Path

# Ensure src/ is in sys.path so the `proxy` package (src/proxy/) is importable
_src_dir = str(Path(__file__).parent)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from proxy.addon import ProxyAddon, addons  # noqa: E402
from proxy.rules import apply_modification_rules  # noqa: E402
