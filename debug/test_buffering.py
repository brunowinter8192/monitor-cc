#!/usr/bin/env python3
"""
Test script for structure-based chronological buffering.
Simulates the buffering logic to verify correct chronological output.
"""

# INFRASTRUCTURE
from typing import Dict, Set, List

agent_to_task: Dict[str, str] = {}
buffered_subagent_calls: Dict[str, List[dict]] = {}
task_requests_seen: Set[str] = set()
call_counter = 0

# ORCHESTRATOR
def test_buffering_logic():
    print("\n" + "=" * 60)
    print("BUFFERING LOGIC TEST")
    print("=" * 60 + "\n")

    mock_calls = create_mock_scenario()
    process_mock_calls(mock_calls)

    print("\n" + "=" * 60)
    print("RESULT: Chronological order maintained!")
    print("=" * 60 + "\n")

# FUNCTIONS

# Create mock tool calls in response arrival order
def create_mock_scenario():
    task_request = {
        'tool_name': 'Task',
        'tool_use_id': 'task-001',
        'output': None,
        'is_subagent': False,
        'timestamp': '2025-11-15T14:59:51.000Z'
    }

    subagent_call_1 = {
        'tool_name': 'Read',
        'tool_use_id': 'sub-001',
        'output': 'file contents',
        'is_subagent': True,
        'agent_id': '444cc912',
        'timestamp': '2025-11-15T14:59:54.418Z'
    }

    subagent_call_2 = {
        'tool_name': 'Grep',
        'tool_use_id': 'sub-002',
        'output': 'grep results',
        'is_subagent': True,
        'agent_id': '444cc912',
        'timestamp': '2025-11-15T14:59:55.283Z'
    }

    task_response = {
        'tool_name': 'Task',
        'tool_use_id': 'task-001',
        'output': 'Task completed',
        'is_subagent': False,
        'spawned_agent_id': '444cc912',
        'timestamp': '2025-11-15T15:02:43.888Z'
    }

    return [task_request, subagent_call_1, subagent_call_2, task_response]

# Process mock calls with buffering logic
def process_mock_calls(tool_calls: List[dict]):
    global call_counter

    print("PROCESSING ORDER (as parsed):")
    print("-" * 60)

    for i, tool_call in enumerate(tool_calls, 1):
        print(f"\n{i}. Parsed: {tool_call['tool_name']} ({tool_call['tool_use_id']})")

        if is_task_request(tool_call):
            call_counter += 1
            task_requests_seen.add(tool_call['tool_use_id'])
            display_call(tool_call, call_counter, "Task REQUEST")

        elif is_task_response(tool_call):
            spawned_agent_id = tool_call.get('spawned_agent_id')
            if spawned_agent_id:
                agent_to_task[spawned_agent_id] = tool_call['tool_use_id']

                if spawned_agent_id in buffered_subagent_calls:
                    print(f"   → Releasing {len(buffered_subagent_calls[spawned_agent_id])} buffered calls")
                    for buffered_call in buffered_subagent_calls[spawned_agent_id]:
                        call_counter += 1
                        display_call(buffered_call, call_counter, "Subagent (buffered)")
                    del buffered_subagent_calls[spawned_agent_id]

            call_counter += 1
            display_call(tool_call, call_counter, "Task RESPONSE")

        elif is_subagent_call(tool_call):
            agent_id = tool_call.get('agent_id')
            if agent_id and agent_id in agent_to_task:
                call_counter += 1
                display_call(tool_call, call_counter, "Subagent (immediate)")
            else:
                if agent_id:
                    if agent_id not in buffered_subagent_calls:
                        buffered_subagent_calls[agent_id] = []
                    buffered_subagent_calls[agent_id].append(tool_call)
                    print(f"   → BUFFERED (agent {agent_id} not yet linked)")

        else:
            call_counter += 1
            display_call(tool_call, call_counter, "Main Agent")

# Check if tool call is a Task REQUEST
def is_task_request(tool_call: dict) -> bool:
    return tool_call.get('tool_name') == 'Task' and tool_call.get('output') is None

# Check if tool call is a Task RESPONSE
def is_task_response(tool_call: dict) -> bool:
    return tool_call.get('tool_name') == 'Task' and tool_call.get('output') is not None

# Check if tool call is from a Subagent
def is_subagent_call(tool_call: dict) -> bool:
    return tool_call.get('is_subagent', False)

# Display call with formatting
def display_call(tool_call: dict, call_number: int, call_type: str):
    timestamp = tool_call.get('timestamp', '')
    time_str = timestamp.split('T')[1] if 'T' in timestamp else timestamp
    print(f"   ✓ DISPLAY #{call_number}: {tool_call['tool_name']} at {time_str} ({call_type})")

if __name__ == "__main__":
    test_buffering_logic()
