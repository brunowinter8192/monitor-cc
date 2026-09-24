# INFRASTRUCTURE
import sys
from pathlib import Path

_HERE = Path(__file__).parent.resolve()

sys.path.insert(0, str(_HERE.parents[2]))
from src.dual_log_cli.render_search import render_search
from src.dual_log_cli.search import find_matches
from dev.refactoring.strand_runner import strand_workflow

_STRANDS = [
    'test_hit_carries_block_chars_not_count',
    'test_rendered_line_format',
    'test_small_artifact_distinguishable_from_prose_hit',
    'test_no_match_unchanged',
    'test_alignment_across_sessions',
]

# ORCHESTRATOR

def test_search_chars_workflow() -> int:
    return strand_workflow(globals(), __file__, _STRANDS, title='test_search_chars')

# FUNCTIONS

def check(name, condition, detail=""):
    if not condition:
        print(f"  FAIL  {name}" + (f": {detail}" if detail != "" else ""))
        raise AssertionError(name)
    print(f"  PASS  {name}")
    return True

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

def test_no_match_unchanged() -> None:
    got = render_search("nowhere", False, [])
    check("no match line present", "no match" in got, got)
    check("no × or chars column on empty result", "×" not in got and "c\n" not in got, got)

def test_alignment_across_sessions() -> None:
    session_a = {"stem": "session_a"}
    session_b = {"stem": "session_b"}
    hits_a = [{"turn": 1, "role": "assistant", "block": 0, "label": "text", "chars": 9}]
    hits_b = [{"turn": 2, "role": "user", "block": 0, "label": "tool_use[Bash]", "chars": 123456}]
    got = render_search("undefined", False, [(session_a, hits_a), (session_b, hits_b)])
    hit_lines = [l for l in got.split("\n") if l.startswith("#")]
    check("both sessions contribute one hit line each", len(hit_lines) == 2, hit_lines)
    check("chars column ends at the same offset on both lines", len(hit_lines[0]) == len(hit_lines[1]), hit_lines)

if __name__ == '__main__':
    sys.exit(test_search_chars_workflow())
