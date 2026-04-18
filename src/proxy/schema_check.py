# INFRASTRUCTURE
import sys
import os
from pathlib import Path

_src_dir = os.path.join(os.environ.get("MONITOR_CC_ROOT", str(Path(__file__).parent.parent.parent)), "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)
from constants import KNOWN_PAYLOAD_KEYS, KNOWN_TOOL_DEFINITION_KEYS

# FUNCTIONS

# Check payload structure against known-good invariants — returns list of warning strings
def _check_payload_schema(payload: dict) -> list:
    try:
        warnings = []

        # Unknown top-level keys
        unknown_keys = set(payload.keys()) - KNOWN_PAYLOAD_KEYS
        if unknown_keys:
            warnings.append(f"Unknown top-level keys: {sorted(unknown_keys)}")

        # system structure
        system = payload.get("system")
        if system is not None:
            if not isinstance(system, list):
                warnings.append(f"system is {type(system).__name__}, expected list")
            else:
                if len(system) != 4:
                    warnings.append(f"system has {len(system)} blocks, expected 4")
                if len(system) >= 3:
                    block2 = system[2]
                    if not isinstance(block2, dict) or block2.get("type") != "text":
                        warnings.append(f"system[2].type={block2.get('type') if isinstance(block2, dict) else type(block2).__name__!r}, expected 'text' (BP1 anchor broken)")

        # messages[0] content shape
        messages = payload.get("messages") or []
        if messages:
            m0 = messages[0]
            c0 = m0.get("content")
            if not isinstance(c0, list):
                warnings.append(f"messages[0].content is {type(c0).__name__}, expected list")

        # tools missing for opus
        tools = payload.get("tools") or []
        if not tools:
            warnings.append("tools is empty — proxy cache markers and tool stripping will not apply")

        # Unknown tool definition keys (check first tool as representative sample)
        if tools and isinstance(tools[0], dict):
            unknown_tool_keys = set(tools[0].keys()) - KNOWN_TOOL_DEFINITION_KEYS - {"cache_control"}
            if unknown_tool_keys:
                warnings.append(f"Unknown keys in tools[0]: {sorted(unknown_tool_keys)}")

        return warnings
    except Exception as e:
        return [f"schema check error: {e}"]
