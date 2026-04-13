# INFRASTRUCTURE
# Stage 0: hardcoded bead_list injection for dispatcher verification.
# This is TEMPORARY test code — will be replaced in Stage 2 by the full schema-store integration.

_BEAD_LIST_SCHEMA = {
    "name": "mcp__plugin_iterative-dev_iterative-dev__bead_list",
    "description": "List beads by status.",
    "input_schema": {
        "type": "object",
        "properties": {
            "status": {
                "default": "open",
                "enum": ["open", "closed"],
                "type": "string",
            },
            "repo": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "default": None,
            },
        },
        "additionalProperties": False,
    },
}

# FUNCTIONS

# Inject hardcoded bead_list schema after last built-in tool if not already present (Stage 0 test)
def inject_mcp_tools_stage0(payload: dict) -> dict:
    tools = payload.get("tools", [])
    names = {t.get("name") for t in tools}
    if _BEAD_LIST_SCHEMA["name"] in names:
        return payload
    modified = dict(payload)
    modified["tools"] = list(tools) + [_BEAD_LIST_SCHEMA]
    return modified
