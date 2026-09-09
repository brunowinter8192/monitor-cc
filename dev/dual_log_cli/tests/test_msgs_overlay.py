"""
Regression suite for `duallog msgs`' strip/inject delta tail (src/dual_log_cli/render.py's
`_delta_tail` / `_msg_delta_tail` / `_block_overlay_totals`, fed by overlay.build_overlay).

Covers: an untouched msg or block line stays byte-identical to the pre-feature output (no tail at
all); a transformed line appends `  −N +M → Wc` (real minus sign, digit-grouped, wire size =
chars − stripped + injected) computed against THAT line's own chars value; a multi-block msg's
parent line carries the SUM over its blocks while untouched sub-lines stay bare; ` by REQ n` is
appended only when the transforming request differs from the group's own, and omitted on the
parent line when a msg's touched blocks disagree on which request touched them (never observed in
the corpus, but the omission is intentional, not an oversight).

All fixtures are hand-built dicts shaped like `render_msgs` expects (`boundaries`, `turns`, and an
`overlay` in the exact `{(msg_idx, blk_idx): {stripped, injected, req}}` shape `build_overlay`
returns) — no dual-log directory or MONITOR_CC_ROOT required.

Run (from project root):
    ./venv/bin/python dev/dual_log_cli/tests/test_msgs_overlay.py

Exit 0 = all checks pass. Exit 1 = at least one failure (printed by name).
"""

# INFRASTRUCTURE

import sys
from pathlib import Path

_HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from src.dual_log_cli.render_msgs import render_msgs

PASS_LIST = []
FAIL_LIST = []


# FUNCTIONS

def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASS_LIST.append(name)
    else:
        FAIL_LIST.append(name)
        print(f"  FAIL  {name}" + (f": {detail}" if detail else ""))


def _msg(index: int, role: str, chars: int, blocks: list) -> dict:
    return {"index": index, "role": role, "type": blocks[0]["type"], "chars": chars, "blocks": blocks}


def _block(type_: str, chars: int, label: str = None) -> dict:
    return {"label": label or type_, "type": type_, "chars": chars, "sig_chars": 0, "preview": ""}


def _boundary(start_index: int, message_count: int, timestamp: str, flow_id: str) -> dict:
    return {"start_index": start_index, "message_count": message_count, "timestamp": timestamp,
            "flow_id": flow_id, "restart": False}


# A single-block, untouched msg renders exactly the pre-feature line — no tail at all, even when
# an overlay dict is supplied but has nothing for this coordinate.
def test_untouched_singleblock_unchanged() -> None:
    data = {"boundaries": [], "turns": [_msg(0, "user", 100, [_block("text", 100)])]}
    got = render_msgs(data, 0, 0, overlay={(5, 0): {"stripped": ["x"], "injected": [], "req": 1}})
    check("untouched single-block msg has no tail", got == "[  0] user  text                  100c\n", got)


# The spec's own example: a single-block msg entirely stripped down to one injected char.
def test_transformed_singleblock_matches_spec_example() -> None:
    data = {
        "boundaries": [_boundary(0, 1, "2026-09-04T00:00:00Z", "f0")],
        "turns": [_msg(1, "system", 10116, [_block("system", 10116)])],
    }
    overlay = {(1, 0): {"stripped": ["x" * 10116], "injected": ["."], "req": 1}}
    got = render_msgs(data, 0, 0, overlay=overlay)
    check("transformed single-block tail matches −N +M → Wc, no by REQ (same group)",
          "10,116c  −10,116 +1 → 1c\n" in got, got)
    check("real minus sign U+2212 is used, not a hyphen", "−10,116" in got and "-10,116" not in got, got)


# A transformed block whose owning request differs from the group's own gets " by REQ n" appended.
def test_by_req_appended_when_different() -> None:
    data = {
        "boundaries": [_boundary(0, 1, "2026-09-04T00:00:00Z", "f0")],
        "turns": [_msg(0, "user", 50, [_block("text", 50)])],
    }
    overlay = {(0, 0): {"stripped": ["x" * 10], "injected": [], "req": 62}}
    got = render_msgs(data, 0, 0, overlay=overlay)
    check("by REQ appended when transforming request differs from the group's",
          "−10 +0 → 40c by REQ 62" in got, got)


# The SAME request performing the transform as the one that owns the group: no "by REQ" suffix.
def test_by_req_omitted_when_same() -> None:
    data = {
        "boundaries": [_boundary(0, 1, "2026-09-04T00:00:00Z", "f0")],
        "turns": [_msg(0, "user", 50, [_block("text", 50)])],
    }
    overlay = {(0, 0): {"stripped": ["x" * 10], "injected": [], "req": 1}}
    got = render_msgs(data, 0, 0, overlay=overlay)
    check("no by REQ when transforming request equals the group's own",
          "−10 +0 → 40c\n" in got and "by REQ" not in got, got)


# Multi-block msg: parent line sums stripped/injected over ALL blocks, a transformed sub-line
# carries its own figures, and an untouched sub-line in the SAME msg stays bare.
def test_multiblock_parent_sums_and_sublines_own_figures() -> None:
    data = {
        "boundaries": [_boundary(0, 1, "2026-09-04T00:00:00Z", "f0")],
        "turns": [_msg(0, "assistant", 300, [
            _block("thinking", 100), _block("tool_use", 200, label="tool_use[Bash]"),
        ])],
    }
    overlay = {
        (0, 0): {"stripped": ["x" * 30], "injected": [], "req": 1},
        (0, 1): {"stripped": ["y" * 20], "injected": ["z" * 5], "req": 1},
    }
    got = render_msgs(data, 0, 0, overlay=overlay)
    lines = got.rstrip("\n").split("\n")
    check("parent line sums both blocks' stripped/injected (30+20=50, 0+5=5, 300-50+5=255)",
          lines[1].endswith("−50 +5 → 255c"), lines[1])
    check("first sub-line carries its OWN figures (100-30=70)", lines[2].endswith("−30 +0 → 70c"), lines[2])
    check("second sub-line carries its OWN figures (200-20+5=185)", lines[3].endswith("−20 +5 → 185c"), lines[3])


# An untouched sub-line inside an otherwise-transformed multi-block msg stays exactly as before.
def test_multiblock_untouched_subline_stays_bare() -> None:
    data = {
        "boundaries": [_boundary(0, 1, "2026-09-04T00:00:00Z", "f0")],
        "turns": [_msg(0, "assistant", 300, [
            _block("thinking", 100), _block("tool_use", 200, label="tool_use[Bash]"),
        ])],
    }
    overlay = {(0, 0): {"stripped": ["x" * 30], "injected": [], "req": 1}}
    got = render_msgs(data, 0, 0, overlay=overlay)
    lines = got.rstrip("\n").split("\n")
    check("untouched sub-line has no tail", lines[3].endswith("200c") and "→" not in lines[3], lines[3])


# A msg whose touched blocks were transformed by TWO DIFFERENT requests never appears in the
# corpus (measured: 0 of 1949), but if it did, the parent's aggregate line must not guess a single
# REQ — only the sub-lines, which each know their own, carry "by REQ".
def test_multiblock_ambiguous_req_omits_parent_by_req() -> None:
    data = {
        "boundaries": [_boundary(0, 1, "2026-09-04T00:00:00Z", "f0")],
        "turns": [_msg(0, "assistant", 300, [
            _block("thinking", 100), _block("tool_use", 200, label="tool_use[Bash]"),
        ])],
    }
    overlay = {
        (0, 0): {"stripped": ["x" * 30], "injected": [], "req": 5},
        (0, 1): {"stripped": ["y" * 20], "injected": [], "req": 9},
    }
    got = render_msgs(data, 0, 0, overlay=overlay)
    lines = got.rstrip("\n").split("\n")
    check("parent line omits by REQ when touched blocks disagree", "by REQ" not in lines[1], lines[1])
    check("first sub-line still names its own REQ 5", "by REQ 5" in lines[2], lines[2])
    check("second sub-line still names its own REQ 9", "by REQ 9" in lines[3], lines[3])


# A default (missing) overlay renders exactly the pre-feature output — additive parameter.
def test_default_overlay_unchanged() -> None:
    data = {"boundaries": [], "turns": [_msg(0, "user", 100, [_block("text", 100)])]}
    got = render_msgs(data, 0, 0)
    check("no overlay argument -> unchanged output", got == "[  0] user  text                  100c\n", got)


# ORCHESTRATOR

def test_msgs_overlay_workflow() -> None:
    test_untouched_singleblock_unchanged()
    test_transformed_singleblock_matches_spec_example()
    test_by_req_appended_when_different()
    test_by_req_omitted_when_same()
    test_multiblock_parent_sums_and_sublines_own_figures()
    test_multiblock_untouched_subline_stays_bare()
    test_multiblock_ambiguous_req_omits_parent_by_req()
    test_default_overlay_unchanged()

    total = len(PASS_LIST) + len(FAIL_LIST)
    print(f"{len(PASS_LIST)}/{total} checks passed")
    if FAIL_LIST:
        print(f"\nFAILED: {FAIL_LIST}")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    test_msgs_overlay_workflow()
