# INFRASTRUCTURE
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.format.strip_marker import highlight_stripped
from src.colors import DIM_YELLOW_BG, RESET, ZEBRA_BG_B
from dev.refactoring.strand_runner import strand_workflow

SKILLS_SR = "<system-reminder>The following skills are available for use with the Skill tool:\n- bead-cli\n- iterative-dev\n</system-reminder>"
TOOL_RESULT_TEXT = "Found 3 matching files:\n  src/foo.py\n  src/bar.py\n  tests/test_foo.py"
PRE_STRIP_MSG2 = f"{SKILLS_SR}\n{TOOL_RESULT_TEXT}"

_STRAND_NAMES = [
    'test_highlight_stripped_basic',
    'test_highlight_stripped_multiline_chunk',
]
_TITLE = 'test_strip_markers: highlight_stripped'
_REPORT_PATH = Path(__file__).resolve().parent / 'md' / 'test_strip_markers.md'

# ORCHESTRATOR

def run_tests() -> None:
    sys.exit(strand_workflow(globals(), __file__, _STRAND_NAMES, _REPORT_PATH, _TITLE))

# FUNCTIONS

def section(title):
    print(f"\n\033[1;34m{'='*60}\n  {title}\n{'='*60}\033[0m")

def label(text):
    print(f"\033[2m  {text}\033[0m")

def test_highlight_stripped_basic():
    section("1. highlight_stripped — basic")
    label("outer_bg='' (ZEBRA_BG_A)")
    result = highlight_stripped(PRE_STRIP_MSG2, [SKILLS_SR], outer_bg='')
    print(result[:200] + ('...' if len(result) > 200 else ''))

    label("outer_bg=ZEBRA_BG_B")
    result2 = highlight_stripped(PRE_STRIP_MSG2, [SKILLS_SR], outer_bg=ZEBRA_BG_B)
    print(result2[:200] + ('...' if len(result2) > 200 else ''))

    label("no chunks → passthrough")
    result3 = highlight_stripped(PRE_STRIP_MSG2, [], outer_bg='')
    assert result3 == PRE_STRIP_MSG2, "passthrough failed"
    print(f"  ✓ unchanged: {result3[:60]}")

    label("chunk not found → graceful skip")
    result4 = highlight_stripped("foo bar", ["NOTHERE"], outer_bg='')
    assert result4 == "foo bar", "graceful skip failed"
    print(f"  ✓ unchanged: {result4}")

    label("multiple occurrences")
    text_multi = "AAA remove_me BBB remove_me CCC"
    result5 = highlight_stripped(text_multi, ["remove_me"], outer_bg='')
    count = result5.count(DIM_YELLOW_BG)
    assert count == 2, f"expected 2 highlights, got {count}"
    print(f"  ✓ 2 occurrences highlighted: {result5}")
    print(RESET, end='')

def test_highlight_stripped_multiline_chunk():
    section("1b. highlight_stripped — multi-line chunk per-line coverage")
    chunk_ml = "A\nB\nC"
    text_ml = f"PREFIX\n{chunk_ml}\nSUFFIX"
    result_ml = highlight_stripped(text_ml, [chunk_ml], outer_bg='')
    split_lines = result_ml.split('\n')
    label(f"input text lines: {len(text_ml.split(chr(10)))}, output split lines: {len(split_lines)}")
    for i, sl in enumerate(split_lines):
        has_bg = DIM_YELLOW_BG in sl
        label(f"  line {i}: bg={'YES' if has_bg else 'no '} | {repr(sl[:80])}")
    chunk_lines = result_ml.split('\n')[1:4]
    for i, cl in enumerate(chunk_lines):
        assert DIM_YELLOW_BG in cl, f"chunk line {i} ('{cl[:40]}') missing DIM_YELLOW_BG"
    print(f"  ✓ all 3 chunk lines carry DIM_YELLOW_BG")

    label("outer_bg=ZEBRA_BG_B — restored after final chunk line")
    result_ml2 = highlight_stripped(f"X{chunk_ml}Y", [chunk_ml], outer_bg=ZEBRA_BG_B)
    last_chunk_line = result_ml2.split('\n')[2]
    assert DIM_YELLOW_BG in last_chunk_line, "last chunk line missing DIM_YELLOW_BG"
    assert ZEBRA_BG_B in last_chunk_line, "outer_bg not restored after final chunk line"
    print(f"  ✓ outer_bg ZEBRA_BG_B present on final chunk line after SOFT_RESET")
    print(RESET, end='')


if __name__ == '__main__':
    run_tests()
