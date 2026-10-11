# INFRASTRUCTURE
import re

from src.constants import TOOL_BLOCKLIST

_BLOCKED_TOOL_PREFIXES = ("mcp__claude_ai_",)

_DEFERRED_IDENTIFIER = "The following deferred tools are now available via ToolSearch"
_DEFERRED_SR_RE = re.compile(r'(?m)^<system-reminder>(.*?)</system-reminder>', re.DOTALL)

# FUNCTIONS

def _strip_unused_tools(payload: dict) -> tuple:
    tools = payload.get("tools", [])
    if not tools:
        return payload, 0, []
    kept = [t for t in tools if not _is_blocked_tool(t.get("name"))]
    removed_names = [t.get("name", "") for t in tools if _is_blocked_tool(t.get("name"))]
    removed = len(tools) - len(kept)
    if removed == 0:
        return payload, 0, []
    modified = dict(payload)
    modified["tools"] = kept
    return modified, removed, removed_names

def _is_blocked_tool(name) -> bool:
    if name in TOOL_BLOCKLIST:
        return True
    return isinstance(name, str) and name.startswith(_BLOCKED_TOOL_PREFIXES)

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
