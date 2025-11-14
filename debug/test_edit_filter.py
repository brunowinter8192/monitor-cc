# Test Edit tool filtering

from pathlib import Path
from jsonl_parser import parse_new_tool_calls

session_file = Path.home() / '.claude/projects/-Users-user-Documents-ai-Monitor-CC/72df0293-b47e-4d6d-b98c-6e79e556c658.jsonl'

if session_file.exists():
    tool_calls, _, _ = parse_new_tool_calls(session_file, 0)

    total_calls = len(tool_calls)
    edit_calls = [tc for tc in tool_calls if tc['tool_name'] == 'Edit']

    print(f"Total tool calls: {total_calls}")
    print(f"Edit tool calls: {len(edit_calls)}")
    print(f"\nEdit filtering: {'✓ WORKING' if len(edit_calls) == 0 else '✗ NOT WORKING'}")

    print(f"\nTool breakdown:")
    tool_counts = {}
    for tc in tool_calls:
        tool_name = tc['tool_name']
        tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

    for tool_name, count in sorted(tool_counts.items()):
        print(f"  {tool_name}: {count}")
