# Test malformed line detection and warning display

from pathlib import Path
from jsonl_parser import parse_new_tool_calls
from formatter import format_warning

test_jsonl = """{"type": "user", "message": {"role": "user", "content": "test"}, "timestamp": "2025-11-14T22:00:00.000Z"}
{"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "toolu_123", "name": "Bash", "input": {"command": "ls"}}]}, "timestamp": "2025-11-14T22:00:01.000Z"}
{"type": "user", "broken json here without closing brace
{"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_123", "content": "file1.txt"}]}, "timestamp": "2025-11-14T22:00:02.000Z"}
this is completely invalid json
{"type": "assistant", "message": {"role": "assistant", "content": "test"}, "timestamp": "2025-11-14T22:00:03.000Z"}
"""

test_file = Path('/tmp/test_malformed.jsonl')
test_file.write_text(test_jsonl)

tool_calls, _, malformed_warnings = parse_new_tool_calls(test_file, 0)

print(f"Found {len(tool_calls)} tool calls")
print(f"Found {len(malformed_warnings)} malformed lines\n")

for warning in malformed_warnings:
    formatted = format_warning(
        file_path=warning['file_path'],
        line_number=warning['line_number'],
        error_message=warning['error_message'],
        raw_line=warning['raw_line']
    )
    print(formatted)
    print()

test_file.unlink()
