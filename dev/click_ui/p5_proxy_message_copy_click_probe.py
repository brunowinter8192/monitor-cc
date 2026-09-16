"""
P5 -- proxy pane message-row, thinking-block AND generic-block copy-by-click probe (Milestone 5:
message-level copy inside an expanded REQ; extended for the thinking-block-level copy milestone
right after it; extended again for the fourth granularity -- a copy affordance on every other
block row: text, tool_use, tool_result, anything else).

Proves, per proxy pane (main `pane.py`, worker `worker_proxy_pane.py`), that after one real
render pass of an expanded REQ:
  1. every plain message-summary row (the `[msg_idx] role  type  chars` / `[msg_idx] role  type`
     rows built by `render_messages._render_new_messages`/`_render_modified_messages`) gets a
     `('msg', entry_idx, msg_idx)` key and a copy-row registration, alongside the pre-existing
     `('req', entry_idx)` row
  2. a synthetic click on a message row's copy column copies EXACTLY
     `proxy_pane_shared._serialize_proxy_message`'s real output for that key -- not hardcoded --
     and that output is a byte-exact match of the corresponding `--- msg[i] ... ---` segment(s)
     inside `_serialize_proxy_entry`'s own REQ-level output for the same message
  3. a click anywhere else on a message row (not the copy column) changes nothing -- no
     `expand_states` mutation, no clipboard write -- matching what these rows did before they had
     a key at all (key=None -> `_handle_proxy_mouse` returns immediately)
  4. copying one message row's flash timer is keyed by the message's own `('msg', ...)` key, not
     the shared `entry_idx` -- it must NOT flash the REQ header or a sibling message row
  5. the pre-existing whole-REQ copy path is completely unaffected (same key, same dispatch
     branch, same `_serialize_proxy_entry` output)
  6. a too-narrow pane renders no `⎘`/`✓` on a message row and registers no copy row for it
     (`utils.append_copy_symbol`'s existing width guard, inherited for free)
  7. a thinking block's own always-visible summary row (the `▶/▼ [bidx] thinking ...` row) gets a
     copy-row registration too, alongside its pre-existing `('think', entry_idx, msg_idx, bidx)`
     key
  8. a synthetic click on a thinking row's copy column copies EXACTLY
     `proxy_pane_shared._serialize_proxy_block`'s real output -- a byte-exact substring of the
     same message's `_serialize_proxy_message` output
  9. a click anywhere ELSE on a thinking row still toggles `expand_states[think_key]`, exactly as
     it already did before this row had a copy affordance -- the one behavior this milestone must
     NOT change, proven by asserting the toggle actually flips, not just that nothing crashes
 10. copying a thinking block's flash timer is keyed by its own `('think', ...)` key -- it must
     NOT flash the sibling message row, the REQ header, or a different block
 11. a too-narrow pane renders no `⎘`/`✓` on a thinking row and registers no copy row for it
 12. every other block row (text, tool_use, tool_result -- anything reaching the non-thinking
     branch of `render_messages._render_block_spans`) gets a `('block', entry_idx, msg_idx, bidx)`
     key and a copy-row registration, alongside its sibling message/REQ rows
 13. a synthetic click on a block row's copy column copies EXACTLY
     `proxy_pane_shared._serialize_proxy_block`'s real output for that key, and that output is a
     byte-exact substring of BOTH the owning message's own copy AND the REQ-level copy -- verified
     directly, not assumed via transitivity
 14. a click anywhere else on a block row changes nothing -- no `expand_states` mutation, no
     clipboard write -- the SAME shape as the message-row case (3), not the thinking-row case (9):
     a block row never toggled anything before it had a key, so it must not start now
 15. copying one block row's flash timer is keyed by its own `('block', ...)` key -- it must NOT
     flash the REQ header, the owning message row, or a sibling block row
 16. a too-narrow pane renders no `⎘`/`✓` on a block row and registers no copy row for it

`_serialize_proxy_block` is ONE function shared by both the `('think', ...)` and `('block', ...)`
key shapes, not two near-identical copies -- the pre-merge `_serialize_proxy_think` body had
nothing thinking-specific in it beyond its own guard (same `full_text`-with-`preview`-fallback
read, same header format, same block-index lookup), so widening the guard to
`_is_think_key(key) or _is_block_key(key)` was the deliberate choice over duplicating that body a
third time. The two key-shape predicates (`_is_think_key`, `_is_block_key`) stay SEPARATE from
each other and from the merged serializer, because they still drive a real fork elsewhere: each
pane's `_handle_*_mouse` non-copy-click dispatch treats a `('think', ...)` row and a `('block', ...)`
row oppositely (think falls through to the pre-existing expand-toggle branch, block returns a
no-op alongside `is_msg`) -- that fork is genuine and stays; only the serialization body, which
never varied, was collapsed.

No live tmux/terminal needed for parts 1-5/7-16 -- `format_proxy_block` and `_handle_*_mouse`
are called directly with synthetic entries, `os.get_terminal_size` is never invoked on that path.
`copy_to_clipboard` is monkeypatched per module to a capturing stub (no real pbcopy call, no OS
clipboard dependency).

Run from project root or worktree root:
    ./venv/bin/python dev/click_ui/p5_proxy_message_copy_click_probe.py
"""

# INFRASTRUCTURE
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from proxy_copy_probe_shared import _RESULTS
from proxy_copy_message_probe import (
    test_message_row_gets_key_and_copy_registration,
    test_message_copy_matches_serializer_and_req_subset,
    test_main_pane_message_copy_click,
    test_worker_pane_message_copy_click,
    test_width_guard_suppresses_msg_row_symbol,
)
from proxy_copy_thinking_probe import (
    test_thinking_row_gets_key_and_copy_registration,
    test_thinking_copy_matches_serializer_and_msg_subset,
    test_main_pane_thinking_copy_click,
    test_worker_pane_thinking_copy_click,
    test_width_guard_suppresses_thinking_row_symbol,
)
from proxy_copy_block_probe import (
    test_block_row_gets_key_and_copy_registration,
    test_block_copy_matches_serializer_and_nests_in_msg_and_req,
    test_main_pane_block_copy_click,
    test_worker_pane_block_copy_click,
    test_width_guard_suppresses_block_row_symbol,
)

# ORCHESTRATOR

def run_probe_workflow():
    print("=" * 70)
    print("proxy pane message-row and thinking-block copy-by-click probe")
    print("=" * 70)
    test_message_row_gets_key_and_copy_registration()
    test_message_copy_matches_serializer_and_req_subset()
    test_main_pane_message_copy_click()
    test_worker_pane_message_copy_click()
    test_width_guard_suppresses_msg_row_symbol()
    test_thinking_row_gets_key_and_copy_registration()
    test_thinking_copy_matches_serializer_and_msg_subset()
    test_main_pane_thinking_copy_click()
    test_worker_pane_thinking_copy_click()
    test_width_guard_suppresses_thinking_row_symbol()
    test_block_row_gets_key_and_copy_registration()
    test_block_copy_matches_serializer_and_nests_in_msg_and_req()
    test_main_pane_block_copy_click()
    test_worker_pane_block_copy_click()
    test_width_guard_suppresses_block_row_symbol()

    total = len(_RESULTS)
    passed = sum(1 for _, ok in _RESULTS if ok)
    print("\n" + "=" * 70)
    print(f"{passed}/{total} checks passed")
    print("=" * 70)

    _write_report(passed, total)
    return passed == total


def _write_report(passed, total):
    md_dir = WORKTREE_ROOT / "dev" / "click_ui" / "md"
    md_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = md_dir / f"p5_proxy_message_copy_click_probe_{stamp}.md"
    lines = [
        f"# P5 -- proxy pane message-row copy-by-click probe run ({datetime.now(timezone.utc).isoformat()})",
        "",
        f"**Result: {passed}/{total} checks passed**",
        "",
        "| Check | Result |",
        "|---|---|",
    ]
    for label, ok in _RESULTS:
        lines.append(f"| {label} | {'PASS' if ok else 'FAIL'} |")
    out_path.write_text("\n".join(lines) + "\n")
    print(f"\nReport written to: {out_path}")


if __name__ == "__main__":
    ok = run_probe_workflow()
    sys.exit(0 if ok else 1)
