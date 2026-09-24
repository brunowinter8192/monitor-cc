# INFRASTRUCTURE
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from proxy.message_passes import _apply_first_pass
from proxy.strip_bg_completed import _WAKEUP_TEXT
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from dev.refactoring.strand_runner import strand_workflow

_STRANDS = [
    'b01_completed_with_output_file',
    'b02_completed_no_output_file',
    'b03_failed_tn_single_block',
    'b04_failed_tn_with_output_file',
]

# ORCHESTRATOR

def proxy_bgcomplete_tests_workflow() -> int:
    return strand_workflow(globals(), __file__, _STRANDS, title='proxy_bgcomplete_tests')

# FUNCTIONS

def check(name, condition, detail=""):
    if not condition:
        print(f"  FAIL  {name}" + (f": {detail}" if detail != "" else ""))
        raise AssertionError(name)
    print(f"  PASS  {name}")
    return True

def _block_count(content) -> int:
    if isinstance(content, list):
        return len(content)
    return 1

def _all_text(content) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")

def b01_completed_with_output_file():
    print("B01 — completed TN + output-file + task-id → single block, wakeup + Output: + ID:")
    output_path = "/private/tmp/abc123/bi3f93ph9.output"
    task_id = "bfjvsrmpj"
    tn = (
        "<task-notification>\n"
        f"<task-id>{task_id}</task-id>\n"
        "<tool-use-id>toolu_01EdfmMHBunn3edcTPSTjFnE</tool-use-id>\n"
        f"<output-file>{output_path}</output-file>\n"
        "<status>completed</status>\n"
        '<summary>Background command "RAG: foo" completed (exit code 0)</summary>\n'
        "</task-notification>\n"
    )
    msgs = [{"role": "user", "content": [{"type": "text", "text": tn}]}]
    new_msgs, mods, removed, changed, injected, ops = _apply_first_pass(msgs)
    content = new_msgs[0]["content"]
    text = _all_text(content)
    wakeup_core = _WAKEUP_TEXT.rstrip('\n')
    expected_injected = wakeup_core + "\nOutput: " + output_path + "\nID: " + task_id + "\n"

    check("B01_single_block", _block_count(content) == 1, f"got {_block_count(content)} blocks")
    check("B01_wakeup_present", wakeup_core in text, repr(text[:80]))
    check("B01_output_line_present", f"Output: {output_path}" in text, repr(text[:120]))
    check("B01_id_line_present", f"ID: {task_id}" in text, repr(text[:160]))
    check("B01_line_order", text.index("Output:") < text.index("ID:"), repr(text[:160]))
    check("B01_summary_dropped", "exit code 0" not in text, repr(text[:120]))
    check("B01_mod_trimmed", "trimmed_task_notification" in mods, f"mods={mods}")
    check("B01_injected_correct", injected.get(0) == [expected_injected], f"injected={injected}")
    check("B01_removed_is_tn_block", removed.get(0) and removed[0][0].startswith("<task-notification>"),
          f"removed={removed}")
    print()

def b02_completed_no_output_file():
    print("B02 — completed TN, task-id only (no output-file) → single block, wakeup + ID: line")
    task_id = "bphrsnzu7"
    tn = (
        "<task-notification>\n"
        f"<task-id>{task_id}</task-id>\n"
        "<tool-use-id>toolu_01AYXvGYYd9QArLZ7wbRLvXQ</tool-use-id>\n"
        "<status>completed</status>\n"
        '<summary>Background command "sleep 10" completed (exit code 0)</summary>\n'
        "</task-notification>\n"
    )
    msgs = [{"role": "user", "content": [{"type": "text", "text": tn}]}]
    new_msgs, mods, removed, changed, injected, ops = _apply_first_pass(msgs)
    content = new_msgs[0]["content"]
    text = _all_text(content)
    wakeup_core = _WAKEUP_TEXT.rstrip('\n')
    expected_injected = wakeup_core + "\nID: " + task_id + "\n"

    check("B02_single_block", _block_count(content) == 1, f"got {_block_count(content)} blocks")
    check("B02_wakeup_present", wakeup_core in text, repr(text[:80]))
    check("B02_no_output_line", "Output:" not in text, repr(text[:80]))
    check("B02_id_line_present", f"ID: {task_id}" in text, repr(text[:120]))
    check("B02_summary_dropped", "exit code 0" not in text, repr(text[:80]))
    check("B02_mod_trimmed", "trimmed_task_notification" in mods, f"mods={mods}")
    check("B02_injected_correct", injected.get(0) == [expected_injected], f"injected={injected}")
    print()

def b03_failed_tn_single_block():
    print("B03 — failed TN, no task-id / no output-file → single block, wakeup only, summary dropped")
    tn = (
        "<task-notification>\n"
        "<status>failed</status>\n"
        "<summary></summary>\n"
        "</task-notification>\n"
    )
    msgs = [{"role": "user", "content": [{"type": "text", "text": tn}]}]
    new_msgs, mods, removed, changed, injected, ops = _apply_first_pass(msgs)
    content = new_msgs[0]["content"]
    text = _all_text(content)
    wakeup_core = _WAKEUP_TEXT.rstrip('\n')

    check("B03_single_block", _block_count(content) == 1, f"got {_block_count(content)} blocks")
    check("B03_wakeup_present", wakeup_core in text, repr(text[:80]))
    check("B03_no_output_line", "Output:" not in text, repr(text[:80]))
    check("B03_no_id_line", "ID:" not in text, repr(text[:80]))
    check("B03_summary_dropped", "<summary>" not in text and "<status>" not in text, repr(text[:80]))
    check("B03_mod_replaced", "replaced_task_notification" in mods, f"mods={mods}")
    check("B03_injected_is_wakeup", injected.get(0) == [_WAKEUP_TEXT], f"injected={injected}")
    check("B03_removed_is_tn_block", removed.get(0) and removed[0][0].startswith("<task-notification>"),
          f"removed={removed}")
    print()

def b04_failed_tn_with_output_file():
    print("B04 — failed TN + output-file + task-id → single block, wakeup + Output: + ID:")
    output_path = "/private/tmp/abc123/fail_output.output"
    task_id = "xyzfail"
    tn = (
        "<task-notification>\n"
        f"<task-id>{task_id}</task-id>\n"
        f"<output-file>{output_path}</output-file>\n"
        "<status>failed</status>\n"
        "<summary></summary>\n"
        "</task-notification>\n"
    )
    msgs = [{"role": "user", "content": [{"type": "text", "text": tn}]}]
    new_msgs, mods, removed, changed, injected, ops = _apply_first_pass(msgs)
    content = new_msgs[0]["content"]
    text = _all_text(content)
    wakeup_core = _WAKEUP_TEXT.rstrip('\n')
    expected_injected = wakeup_core + "\nOutput: " + output_path + "\nID: " + task_id + "\n"

    check("B04_single_block", _block_count(content) == 1, f"got {_block_count(content)} blocks")
    check("B04_wakeup_present", wakeup_core in text, repr(text[:80]))
    check("B04_output_line_present", f"Output: {output_path}" in text, repr(text[:120]))
    check("B04_id_line_present", f"ID: {task_id}" in text, repr(text[:160]))
    check("B04_line_order", text.index("Output:") < text.index("ID:"), repr(text[:160]))
    check("B04_summary_dropped", "<summary>" not in text and "<status>" not in text, repr(text[:120]))
    check("B04_mod_replaced", "replaced_task_notification" in mods, f"mods={mods}")
    check("B04_injected_correct", injected.get(0) == [expected_injected], f"injected={injected}")
    check("B04_removed_is_tn_block", removed.get(0) and removed[0][0].startswith("<task-notification>"),
          f"removed={removed}")
    print()

if __name__ == '__main__':
    sys.exit(proxy_bgcomplete_tests_workflow())
