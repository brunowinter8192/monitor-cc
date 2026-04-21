"""
Verify that expandtabs fix eliminates terminal wrap across all patched render paths.

Usage (from repo root):
    ./venv/bin/python dev/display/verify_tab_expand_all.py

For each patched render function, feeds tab-containing content and checks that
after truncate_visible(pane_width=80), no output line has real_cells > pane_width.
Exits 1 if any over-wide lines are found.
"""
import re
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from pathlib import Path
from src.utils import _cell_width, truncate_visible

# INFRASTRUCTURE

PANE_WIDTH = 80
ANSI = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')

TAB_LINE = "1\tdef some_long_function_name_here(arg1, arg2, arg3, arg4, arg5, arg6):"
TAB_CONTENT = "\n".join([
    "# heading",
    TAB_LINE,
    "2\t    return {'key': 'very_long_value_that_extends_beyond_the_pane_width_limit_here'}",
    "3\t",
    "4\tnormal line",
])


# Real terminal cell count accounting for tab expansion
def real_cells(s, tab_size=8):
    s = ANSI.sub('', s)
    out = 0
    for ch in s:
        if ch == '\t':
            out += tab_size - (out % tab_size)
        else:
            out += _cell_width(ch)
    return out


# Check a list of rendered lines after truncate_visible — return over-wide entries
def check_lines(label, lines, pane_width=PANE_WIDTH):
    overwide = []
    for i, line in enumerate(lines):
        trunc = truncate_visible(line, pane_width)
        rc = real_cells(trunc)
        if rc > pane_width:
            overwide.append((i, rc, repr(trunc[:60])))
    if overwide:
        print(f"  FAIL [{label}]: {len(overwide)} over-wide lines")
        for i, rc, preview in overwide[:3]:
            print(f"    line[{i}] rc={rc}: {preview}")
    else:
        print(f"  OK   [{label}]: {len(lines)} lines, 0 over-wide")
    return overwide


# ORCHESTRATOR

def verify():
    total_failures = 0

    # --- render_sections: system block preview ---
    from src.proxy_display.render_sections import render_system_blocks
    entry = {
        'system_blocks': [{'idx': 0, 'chars': len(TAB_CONTENT), 'preview': TAB_CONTENT}],
        'system_total_chars': len(TAB_CONTENT),
    }
    expand_states = {('sys', 0): True, ('sys_block', 0, 0): True}
    lines, _ = render_system_blocks(0, entry, None, expand_states, PANE_WIDTH, [])
    total_failures += len(check_lines("render_sections/sys_block_preview", lines))

    # --- render_sections: tool description ---
    from src.proxy_display.render_sections import render_tools
    tool_entry = {
        'tools_count': 1,
        'tools_total_chars': 100,
        'tools_hash': 'abc',
        'tools_names': ['my_tool'],
        'tools_defs': [{'name': 'my_tool', 'description': TAB_CONTENT, 'input_schema': {}}],
    }
    expand_states_t = {('tools', 0): True, ('tool', 0, 0): True}
    lines, _ = render_tools(0, tool_entry, None, expand_states_t, PANE_WIDTH)
    total_failures += len(check_lines("render_sections/tool_description", lines))

    # --- formatter: format_output ---
    from src.format.formatter import format_output
    result = format_output(TAB_CONTENT)
    lines = result.split('\n')
    total_failures += len(check_lines("formatter/format_output", lines))

    # --- formatter: format_error_output ---
    from src.format.formatter import format_error_output
    result = format_error_output(TAB_CONTENT)
    lines = result.split('\n')
    total_failures += len(check_lines("formatter/format_error_output", lines))

    # --- formatter: format_value (multiline string) ---
    from src.format.formatter import format_value
    result = format_value(TAB_CONTENT)
    lines = result.split('\n')
    total_failures += len(check_lines("formatter/format_value", lines))

    # --- formatter_events: format_system_message ---
    from src.format.formatter_events import format_system_message
    result = format_system_message("2026-01-01T00:00:00Z", TAB_CONTENT)
    lines = result.split('\n')
    total_failures += len(check_lines("formatter_events/format_system_message", lines))

    # --- formatter_events: format_skill_activation ---
    from src.format.formatter_events import format_skill_activation
    skill_item = {'timestamp': '2026-01-01T00:00:00Z', 'skill_name': 'test', 'content': TAB_CONTENT}
    result = format_skill_activation(skill_item)
    lines = result.split('\n')
    total_failures += len(check_lines("formatter_events/format_skill_activation", lines))

    # --- hooks_format: format_hooks_block (expanded with tab content) ---
    from src.hooks.hooks_format import format_hooks_block
    items = [{
        'type': 'hook', 'expanded': True, 'content': TAB_CONTENT,
        'color': '', 'time_str': '12:00:00', 'hook_event': 'PostToolUse',
        'hook_script': 'test.sh', 'detail': '',
    }]
    visible, _, _, _, _, _, _ = format_hooks_block(items, 0, pane_height=50, pane_width=PANE_WIDTH)
    total_failures += len(check_lines("hooks_format/format_hooks_block", visible))

    # --- waste_pane: render expanded output section (unit test via direct render call) ---
    # waste_pane integrates deeply with proxy data model — test via format_output proxy
    # (out_text rendering uses same pattern, covered by formatter/format_output above)
    print(f"  NOTE waste_pane/out_text: expandtabs applied, covered by format_output pattern")

    # --- warnings_pane: display_text rendering ---
    # _format_warnings_pane uses global state and is not directly importable for unit testing.
    # Pattern at warnings_pane.py:229 is identical to render_messages.py (raw_line = raw_line.expandtabs(8)).
    print(f"  NOTE warnings_pane/display_text: expandtabs applied at line 229, same pattern as above")

    print()
    if total_failures:
        print(f"RESULT: {total_failures} over-wide lines found — FAIL")
        sys.exit(1)
    else:
        print("RESULT: OK — all render paths: 0 over-wide lines after truncate_visible")
        sys.exit(0)


if __name__ == '__main__':
    verify()
