# INFRASTRUCTURE
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from src.proxy.addon import _check_payload_schema

VALID_TOOL = {"name": "Bash", "description": "Run bash", "input_schema": {"type": "object"}}

VALID_PAYLOAD = {
    "model": "claude-opus-4-6",
    "max_tokens": 32000,
    "system": [
        {"type": "text", "text": "block0"},
        {"type": "text", "text": "block1"},
        {"type": "text", "text": "block2"},
        {"type": "text", "text": "block3"},
    ],
    "messages": [{"role": "user", "content": [{"type": "text", "text": "hello"}]}],
    "tools": [VALID_TOOL],
}

# ORCHESTRATOR

def run_tests() -> None:
    results = []
    results.append(_test_unknown_top_level_key())
    results.append(_test_system_block_count())
    results.append(_test_system_block2_type())
    results.append(_test_messages_content_not_list())
    results.append(_test_tools_empty())
    results.append(_test_unknown_tool_key())

    print()
    for name, passed, detail in results:
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {name}: {detail}")

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    sys.exit(1 if failed else 0)

# FUNCTIONS

# Case 1: unknown top-level key triggers warning
def _test_unknown_top_level_key() -> tuple:
    payload = {**VALID_PAYLOAD, "extra_key_xyz": "value"}
    warnings = _check_payload_schema(payload)
    expected = "Unknown top-level keys"
    passed = any(expected in w for w in warnings)
    detail = f"warnings={warnings}" if not passed else f"got: {[w for w in warnings if expected in w]}"
    return ("unknown top-level key", passed, detail)

# Case 2: system block count != 4 triggers warning
def _test_system_block_count() -> tuple:
    payload = {**VALID_PAYLOAD, "system": [
        {"type": "text", "text": "only three"},
        {"type": "text", "text": "blocks"},
        {"type": "text", "text": "here"},
    ]}
    warnings = _check_payload_schema(payload)
    expected = "system has 3 blocks"
    passed = any(expected in w for w in warnings)
    detail = f"warnings={warnings}" if not passed else f"got: {[w for w in warnings if expected in w]}"
    return ("system block count != 4", passed, detail)

# Case 3: system[2].type != 'text' triggers warning
def _test_system_block2_type() -> tuple:
    system = list(VALID_PAYLOAD["system"])
    system[2] = {"type": "image", "source": {"type": "url", "url": "http://example.com"}}
    payload = {**VALID_PAYLOAD, "system": system}
    warnings = _check_payload_schema(payload)
    expected = "system[2].type="
    passed = any(expected in w for w in warnings)
    detail = f"warnings={warnings}" if not passed else f"got: {[w for w in warnings if expected in w]}"
    return ("system[2].type != text", passed, detail)

# Case 4: messages[0].content not a list triggers warning
def _test_messages_content_not_list() -> tuple:
    payload = {**VALID_PAYLOAD, "messages": [{"role": "user", "content": "plain string"}]}
    warnings = _check_payload_schema(payload)
    expected = "messages[0].content is str"
    passed = any(expected in w for w in warnings)
    detail = f"warnings={warnings}" if not passed else f"got: {[w for w in warnings if expected in w]}"
    return ("messages[0].content not list", passed, detail)

# Case 5: tools empty triggers warning
def _test_tools_empty() -> tuple:
    payload = {**VALID_PAYLOAD, "tools": []}
    warnings = _check_payload_schema(payload)
    expected = "tools is empty"
    passed = any(expected in w for w in warnings)
    detail = f"warnings={warnings}" if not passed else f"got: {[w for w in warnings if expected in w]}"
    return ("tools empty", passed, detail)

# Case 6: unknown key in tools[0] triggers warning
def _test_unknown_tool_key() -> tuple:
    tool_with_extra = {**VALID_TOOL, "unknown_field_xyz": "value"}
    payload = {**VALID_PAYLOAD, "tools": [tool_with_extra]}
    warnings = _check_payload_schema(payload)
    expected = "Unknown keys in tools[0]"
    passed = any(expected in w for w in warnings)
    detail = f"warnings={warnings}" if not passed else f"got: {[w for w in warnings if expected in w]}"
    return ("unknown key in tools[0]", passed, detail)


if __name__ == "__main__":
    run_tests()
