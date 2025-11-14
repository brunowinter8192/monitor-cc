# Test TodoWrite special formatting

from formatter import format_tool_call

sample_input = {
    'todos': [
        {
            'content': 'Add format_warning() function to formatter.py',
            'status': 'completed',
            'activeForm': 'Adding format_warning()'
        },
        {
            'content': 'Update parse_jsonl_lines() to track malformed lines',
            'status': 'in_progress',
            'activeForm': 'Updating parse_jsonl_lines()'
        },
        {
            'content': 'Test with malformed JSONL data',
            'status': 'pending',
            'activeForm': 'Testing with malformed data'
        }
    ]
}

formatted = format_tool_call(
    tool_name='TodoWrite',
    input_data=sample_input,
    output_data='Todos have been modified successfully.',
    tool_use_id='toolu_123',
    timestamp='2025-11-14T23:00:00.000Z',
    call_number=42
)

print(formatted)
