"""
Regression suite for `duallog search`'s hit-line format (src/dual_log_cli/search.py's
`find_matches`, src/dual_log_cli/render.py's `render_search`).

Covers: a hit reports the block's original-payload chars (the same value `msgs`/`expand` show for
that block) instead of an occurrence count and a text snippet; a block with several occurrences of
the term still stays exactly ONE hit; a small genuine artifact and a larger prose hit are
distinguishable by their chars column at a glance; the `no match` case and the per-session
`session <stem>` header stay unchanged; and hit-line column alignment holds across sessions with
different label/chars widths.

All fixtures are hand-built payloads run through the real `find_matches`/`render_search` pipeline
— no dual-log directory or MONITOR_CC_ROOT required.

Run (from project root):
    ./venv/bin/python dev/dual_log_cli/tests/test_search_chars.py

Exit 0 = all checks pass. Exit 1 = at least one failure (printed by name).
"""

# INFRASTRUCTURE

import sys
from pathlib import Path

_HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from src.dual_log_cli.render_search import render_search
from src.dual_log_cli.search import find_matches

PASS_LIST = []
FAIL_LIST = []


# FUNCTIONS

def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASS_LIST.append(name)
    else:
        FAIL_LIST.append(name)
        print(f"  FAIL  {name}" + (f": {detail}" if detail else ""))


# A hit carries the block's chars, not an occurrence count or a snippet — and a block the term
# appears in twice still yields exactly one hit.
def test_hit_carries_block_chars_not_count() -> None:
    payload = {"messages": [
        {"role": "assistant", "content": [
            {"type": "text", "text": "undefined"},
        ]},
    ]}
    hits = find_matches(payload, "undefined")
    check("one hit for one matching block", len(hits) == 1, hits)
    check("hit carries the block's chars (9), not a count", hits[0]["chars"] == 9, hits[0])
    check("hit carries no count field", "count" not in hits[0], hits[0])
    check("hit carries no snippet field", "snippet" not in hits[0], hits[0])

    payload_repeated = {"messages": [
        {"role": "assistant", "content": [
            {"type": "text", "text": "undefined is undefined, undefined again"},
        ]},
    ]}
    hits_repeated = find_matches(payload_repeated, "undefined")
    check("a block with 3 occurrences is still exactly one hit", len(hits_repeated) == 1, hits_repeated)
    check("its chars reflect the whole block, not the term length",
          hits_repeated[0]["chars"] == len("undefined is undefined, undefined again"), hits_repeated[0])


# The rendered hit line: msg index, role, block label, right-aligned chars — no `×N`, no snippet.
def test_rendered_line_format() -> None:
    session = {"stem": "monitor_cc_0001"}
    hits = [
        {"turn": 706, "role": "assistant", "block": 0, "label": "text", "chars": 9},
    ]
    got = render_search("undefined", False, [(session, hits)])
    check("no × occurrence marker", "×" not in got, got)
    check("no ellipsis snippet remnants", "…" not in got, got)
    check("hit line carries msg index, role, label and chars", "#706" in got and "assistant" in got and "text" in got and "9c" in got, got)
    check("session header unchanged", "session   monitor_cc_0001" in got, got)


# A genuine 9-char artifact and a larger prose hit are distinguishable by chars alone — the
# use-case this feature exists for.
def test_small_artifact_distinguishable_from_prose_hit() -> None:
    session = {"stem": "s1"}
    hits = [
        {"turn": 1, "role": "assistant", "block": 0, "label": "text", "chars": 9},
        {"turn": 2, "role": "user", "block": 0, "label": "text", "chars": 4200},
    ]
    got = render_search("undefined", False, [(session, hits)])
    lines = [l for l in got.split("\n") if l.startswith("#")]
    check("two hit lines rendered", len(lines) == 2, lines)
    check("small artifact reads 9c", lines[0].rstrip().endswith("9c"), lines[0])
    check("prose hit reads 4,200c, digit-grouped", lines[1].rstrip().endswith("4,200c"), lines[1])


# no match stays exactly "no match", untouched by this change.
def test_no_match_unchanged() -> None:
    got = render_search("nowhere", False, [])
    check("no match line present", "no match" in got, got)
    check("no × or chars column on empty result", "×" not in got and "c\n" not in got, got)


# Hit-line columns (label, chars) align across TWO sessions with different label/chars widths —
# both widths are computed over the combined result set, not per session.
def test_alignment_across_sessions() -> None:
    session_a = {"stem": "session_a"}
    session_b = {"stem": "session_b"}
    hits_a = [{"turn": 1, "role": "assistant", "block": 0, "label": "text", "chars": 9}]
    hits_b = [{"turn": 2, "role": "user", "block": 0, "label": "tool_use[Bash]", "chars": 123456}]
    got = render_search("undefined", False, [(session_a, hits_a), (session_b, hits_b)])
    hit_lines = [l for l in got.split("\n") if l.startswith("#")]
    check("both sessions contribute one hit line each", len(hit_lines) == 2, hit_lines)
    # the chars column ends at the same offset on both lines regardless of label/chars width
    check("chars column ends at the same offset on both lines", len(hit_lines[0]) == len(hit_lines[1]), hit_lines)


# ORCHESTRATOR

def test_search_chars_workflow() -> None:
    test_hit_carries_block_chars_not_count()
    test_rendered_line_format()
    test_small_artifact_distinguishable_from_prose_hit()
    test_no_match_unchanged()
    test_alignment_across_sessions()

    total = len(PASS_LIST) + len(FAIL_LIST)
    print(f"{len(PASS_LIST)}/{total} checks passed")
    if FAIL_LIST:
        print(f"\nFAILED: {FAIL_LIST}")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    test_search_chars_workflow()
