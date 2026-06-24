"""Smoke tests for background-completion task-notification single-block fix.

Three cases:
  B01 — completed TN + output-file → single block, wakeup + Output line, summary dropped
  B02 — completed TN, no output-file → single block, wakeup only, summary dropped
  B03 — failed TN → behavior unchanged (wakeup present, mod=replaced_task_notification)

Run from project root:
    ./venv/bin/python dev/proxy_bgcomplete_tests.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from proxy.message_passes import _apply_first_pass
from proxy.strip_bg_completed import _WAKEUP_TEXT

_PASS = "\033[32mPASS\033[0m"
_FAIL = "\033[31mFAIL\033[0m"

def check(label, condition, detail=""):
    status = _PASS if condition else _FAIL
    suffix = f"  [{detail}]" if detail and not condition else ""
    print(f"    {status}  {label}{suffix}")
    return condition


def _block_count(content) -> int:
    if isinstance(content, list):
        return len(content)
    return 1  # string = one logical block


def _all_text(content) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")


# B01 — completed TN with output-file → single block, wakeup + Output line, summary dropped
def b01_completed_with_output_file():
    print("B01 — completed TN + output-file → single block, wakeup + Output: path")
    output_path = "/private/tmp/abc123/bi3f93ph9.output"
    tn = (
        "<task-notification>\n"
        "<task-id>bfjvsrmpj</task-id>\n"
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
    expected_injected = wakeup_core + "\nOutput: " + output_path + "\n"

    check("B01_single_block", _block_count(content) == 1, f"got {_block_count(content)} blocks")
    check("B01_wakeup_present", wakeup_core in text, repr(text[:80]))
    check("B01_output_line_present", f"Output: {output_path}" in text, repr(text[:120]))
    check("B01_summary_dropped", "exit code 0" not in text, repr(text[:120]))
    check("B01_mod_trimmed", "trimmed_task_notification" in mods, f"mods={mods}")
    check("B01_injected_correct", injected.get(0) == [expected_injected], f"injected={injected}")
    check("B01_removed_is_tn_block", removed.get(0) and removed[0][0].startswith("<task-notification>"),
          f"removed={removed}")
    print()


# B02 — completed TN, no output-file → single block, wakeup only, summary dropped
def b02_completed_no_output_file():
    print("B02 — completed TN, no output-file → single block, wakeup only")
    tn = (
        "<task-notification>\n"
        "<task-id>bphrsnzu7</task-id>\n"
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

    check("B02_single_block", _block_count(content) == 1, f"got {_block_count(content)} blocks")
    check("B02_wakeup_present", wakeup_core in text, repr(text[:80]))
    check("B02_no_output_line", "Output:" not in text, repr(text[:80]))
    check("B02_summary_dropped", "exit code 0" not in text, repr(text[:80]))
    check("B02_mod_trimmed", "trimmed_task_notification" in mods, f"mods={mods}")
    check("B02_injected_is_wakeup", injected.get(0) == [_WAKEUP_TEXT], f"injected={injected}")
    print()


# B03 — failed TN → behavior unchanged: wakeup present, mod=replaced_task_notification
def b03_failed_tn_unchanged():
    print("B03 — failed TN → unchanged (wakeup present, mod=replaced_task_notification)")
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

    check("B03_wakeup_present", wakeup_core in text, repr(text[:80]))
    check("B03_mod_replaced", "replaced_task_notification" in mods, f"mods={mods}")
    check("B03_injected_is_wakeup", injected.get(0) == [_WAKEUP_TEXT], f"injected={injected}")
    check("B03_removed_is_tn_block", removed.get(0) and removed[0][0].startswith("<task-notification>"),
          f"removed={removed}")
    print()


if __name__ == "__main__":
    b01_completed_with_output_file()
    b02_completed_no_output_file()
    b03_failed_tn_unchanged()
    print("Done.")
