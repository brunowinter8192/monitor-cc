# INFRASTRUCTURE
import os
import re
import sys
from pathlib import Path

_src_dir = os.path.join(os.environ.get("MONITOR_CC_ROOT", str(Path(__file__).parent.parent.parent)), "src")
sys.path.insert(0, _src_dir)
from constants import TOOL_BLOCKLIST

_DEFERRED_IDENTIFIER = "The following deferred tools are now available via ToolSearch"
_DEFERRED_SR_RE = re.compile(r'(?m)^<system-reminder>(.*?)</system-reminder>', re.DOTALL)

# FUNCTIONS

# Remove blocklisted tools from payload. Returns (modified_payload, count_removed, removed_names).
def _strip_unused_tools(payload: dict) -> tuple:
    tools = payload.get("tools", [])
    if not tools:
        return payload, 0, []
    kept = [t for t in tools if t.get("name") not in TOOL_BLOCKLIST]
    removed_names = [t.get("name", "") for t in tools if t.get("name") in TOOL_BLOCKLIST]
    removed = len(tools) - len(kept)
    if removed == 0:
        return payload, 0, []
    modified = dict(payload)
    modified["tools"] = kept
    return modified, removed, removed_names

# Scan user messages in payload for deferred-tools SR; return deduplicated tool name list, or [].
def _extract_deferred_tool_names(payload: dict) -> list:
    messages = payload.get("messages", [])
    names = []
    seen = set()
    for msg in messages:
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        if isinstance(content, list):
            content = "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
        if not isinstance(content, str) or _DEFERRED_IDENTIFIER not in content:
            continue
        for m in _DEFERRED_SR_RE.finditer(content):
            inner = m.group(1).strip()
            if not inner.startswith(_DEFERRED_IDENTIFIER):
                continue
            for line in inner.split('\n')[1:]:
                line = line.strip()
                if line and line not in seen:
                    seen.add(line)
                    names.append(line)
    return names
