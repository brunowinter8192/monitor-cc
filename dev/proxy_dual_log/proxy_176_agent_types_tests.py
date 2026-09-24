# INFRASTRUCTURE
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from proxy.message_passes import _apply_cumulative_sr_strips
from proxy.strip_inject_delta import _process_messages_section, _MSG_CODE_TO_FN
from proxy.diff_engine import _diff_messages
from proxy.logging import _normalize_msg_shape_for_hash
from proxy.rule_ops import _ops_from_content_change
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from dev.refactoring.strand_runner import strand_workflow

_AGENT_TYPES_SR = (
    "<system-reminder>\n"
    "Available agent types for the Agent tool:\n"
    "- claude: Catch-all for any task that doesn't fit a more specific agent.\n"
    "- claude-code-guide: Use this agent when the user asks questions about Claude Code.\n"
    "- Explore: Fast read-only search agent for locating code.\n"
    "- general-purpose: General-purpose agent for researching complex questions.\n"
    "- Plan: Software architect agent for designing implementation plans.\n"
    "- statusline-setup: Use this agent to configure the user's Claude Code status line.\n"
    + "x" * 2200
    + "\n</system-reminder>\n"
)
_USER_MSG_WITH_SR = {
    "role": "user",
    "content": [
        {"type": "tool_result", "tool_use_id": "toolu_01", "content": "some tool result text"},
        {"type": "text", "text": _AGENT_TYPES_SR},
    ],
}
_USER_MSG_STRING = {
    "role": "user",
    "content": "preamble text\n" + _AGENT_TYPES_SR + "trailing text",
}

_STRANDS = [
    'test_agent_types_stripped_list_content',
    'test_agent_types_stripped_string_content',
    'test_assistant_untouched',
    'test_no_false_positive_on_unrelated_user_msg',
    'test_skills_and_agent_types_coexist',
    'test_attribution_at_code',
]

# ORCHESTRATOR

def proxy_176_agent_types_tests_workflow() -> int:
    return strand_workflow(globals(), __file__, _STRANDS, title='proxy_176_agent_types_tests')

# FUNCTIONS

def check(name, condition, detail=""):
    if not condition:
        print(f"  FAIL  {name}" + (f": {detail}" if detail != "" else ""))
        raise AssertionError(name)
    print(f"  PASS  {name}")
    return True

def test_agent_types_stripped_list_content():
    print("Item 3a — agent-types SR stripped from list-content user message")
    messages = [_USER_MSG_WITH_SR]
    result, mods, removed, changed, _, _ = _apply_cumulative_sr_strips(messages)
    content = result[0]["content"]
    text_block = next(b for b in content if b.get("type") == "text")
    check("SR block removed from text content", "Available agent types for the Agent tool" not in text_block.get("text", ""))
    check("<system-reminder> tag gone", "<system-reminder>" not in text_block.get("text", ""))
    check("tool_result block preserved", any(b.get("type") == "tool_result" for b in content))
    check("mod-name 'stripped_agent_types_sr' recorded", "stripped_agent_types_sr" in mods)
    check("index 0 in changed_indices", 0 in changed)
    check("original captured in removed[0]", removed.get(0) is not None and len(removed[0]) > 0)
    print()

def test_agent_types_stripped_string_content():
    print("Item 3b — agent-types SR stripped from plain-string user message")
    messages = [_USER_MSG_STRING]
    result, mods, removed, changed, _, _ = _apply_cumulative_sr_strips(messages)
    content = result[0]["content"]
    check("SR block removed from string content", "Available agent types for the Agent tool" not in content)
    check("<system-reminder> tag gone", "<system-reminder>" not in content)
    check("preamble preserved", "preamble text" in content)
    check("trailing text preserved", "trailing text" in content)
    check("mod-name recorded", "stripped_agent_types_sr" in mods)
    print()

def test_assistant_untouched():
    print("Item 3c — role=assistant message untouched")
    messages = [
        {"role": "assistant", "content": "Here is my response: " + _AGENT_TYPES_SR},
    ]
    result, mods, removed, changed, _, _ = _apply_cumulative_sr_strips(messages)
    check("assistant content unchanged", result[0]["content"] == messages[0]["content"])
    check("no mods", mods == [])
    check("no changed indices", changed == [])
    print()

def test_no_false_positive_on_unrelated_user_msg():
    print("Item 3d — unrelated user message not affected")
    messages = [
        {"role": "user", "content": "Please help me write some code."},
    ]
    result, mods, removed, changed, _, _ = _apply_cumulative_sr_strips(messages)
    check("content unchanged", result[0]["content"] == "Please help me write some code.")
    check("no mods", mods == [])
    print()

def test_skills_and_agent_types_coexist():
    print("Item 3e — skills SR and agent-types SR both stripped from same message")
    skills_sr = (
        "<system-reminder>\n"
        "The following skills are available for use with the Skill tool:\n"
        "- some_skill: does something\n"
        "</system-reminder>\n"
    )
    content = skills_sr + _AGENT_TYPES_SR + "user text"
    messages = [{"role": "user", "content": content}]
    result, mods, removed, changed, _, _ = _apply_cumulative_sr_strips(messages)
    out = result[0]["content"]
    check("agent-types SR removed", "Available agent types for the Agent tool" not in out)
    check("skills SR removed", "The following skills are available" not in out)
    check("user text preserved", "user text" in out)
    check("both mods recorded", "stripped_skills_sr" in mods and "stripped_agent_types_sr" in mods)
    print()

def test_attribution_at_code():
    print("Item 3f — attribution: agent-types chunk → code='AT', fn='_apply_cumulative_sr_strips'")
    orig_content = "intro\n" + _AGENT_TYPES_SR + "outro"
    from proxy.strip_sr import _strip_system_reminder
    fwd_content = _strip_system_reminder(orig_content, "Available agent types for the Agent tool")
    orig_msgs = [{"role": "user", "content": orig_content}]
    fwd_msgs  = [{"role": "user", "content": fwd_content}]
    orig_norm = [_normalize_msg_shape_for_hash(m) for m in orig_msgs]
    fwd_norm  = [_normalize_msg_shape_for_hash(m) for m in fwd_msgs]
    msg_diffs = _diff_messages(orig_norm, fwd_norm)
    all_ops = {0: _ops_from_content_change(orig_content, fwd_content)}
    _, _, _, _, s_fn, _ = _process_messages_section(
        msg_diffs, orig_norm, is_first=True, prev_stripped=None, prev_injected=None, all_ops=all_ops
    )
    fn_value = s_fn.get("msg.0.0")
    check("fn attributed to _apply_cumulative_sr_strips", fn_value == "_apply_cumulative_sr_strips")
    check("AT → _apply_cumulative_sr_strips in _MSG_CODE_TO_FN", _MSG_CODE_TO_FN.get('AT') == '_apply_cumulative_sr_strips')
    print()

if __name__ == '__main__':
    sys.exit(proxy_176_agent_types_tests_workflow())
