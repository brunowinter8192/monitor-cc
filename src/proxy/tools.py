# INFRASTRUCTURE
import os
import sys
from pathlib import Path

_src_dir = os.path.join(os.environ.get("MONITOR_CC_ROOT", str(Path(__file__).parent.parent.parent)), "src")
sys.path.insert(0, _src_dir)
from constants import TOOL_BLOCKLIST

# FUNCTIONS

# Remove blocklisted tools from payload and trim Agent description. Returns (modified_payload, count_removed).
def _strip_unused_tools(payload: dict) -> tuple:
    tools = payload.get("tools", [])
    if not tools:
        return payload, 0
    kept = [t for t in tools if t.get("name") not in TOOL_BLOCKLIST]
    removed = len(tools) - len(kept)
    if removed == 0:
        return payload, 0
    modified = dict(payload)
    modified["tools"] = kept
    return modified, removed
