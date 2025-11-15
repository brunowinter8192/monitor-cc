#!/usr/bin/env python3
"""
Debug script to analyze chronological ordering issue.
Simulates the problem where tool calls are displayed in response order
instead of request timestamp order.
"""

# INFRASTRUCTURE
from datetime import datetime, timedelta

# FUNCTIONS

# Simulate tool call data with different request/response timing
def create_mock_tool_calls():
    base_time = datetime.now()

    # Main Agent: Request at T1, Response at T4
    main_agent_call = {
        'tool_name': 'Read',
        'timestamp': (base_time + timedelta(seconds=1)).isoformat(),  # T1
        'response_timestamp': (base_time + timedelta(seconds=4)).isoformat(),  # T4
        'is_subagent': False,
        'agent_id': 'main',
        'tool_use_id': 'main-001'
    }

    # Subagent: Request at T2, Response at T3
    subagent_call = {
        'tool_name': 'Grep',
        'timestamp': (base_time + timedelta(seconds=2)).isoformat(),  # T2
        'response_timestamp': (base_time + timedelta(seconds=3)).isoformat(),  # T3
        'is_subagent': True,
        'agent_id': 'sub-001',
        'tool_use_id': 'sub-001'
    }

    return main_agent_call, subagent_call

# Simulate current behavior - output in response order
def simulate_current_behavior():
    main_call, sub_call = create_mock_tool_calls()

    # Current behavior: Sorted by response arrival
    # Subagent response comes first (T3), then main agent (T4)
    calls_in_response_order = [sub_call, main_call]

    return calls_in_response_order

# Simulate correct behavior - output in request order
def simulate_correct_behavior():
    main_call, sub_call = create_mock_tool_calls()

    # Correct behavior: Sorted by request timestamp
    # Main agent request first (T1), then subagent (T2)
    calls_sorted = sorted([main_call, sub_call], key=lambda x: x['timestamp'])

    return calls_sorted

# Display tool call info
def display_call_info(call, label):
    req_time = datetime.fromisoformat(call['timestamp'])
    resp_time = datetime.fromisoformat(call['response_timestamp'])
    agent_type = 'SUBAGENT' if call['is_subagent'] else 'MAIN'

    print(f"{label}:")
    print(f"  Agent: {agent_type}")
    print(f"  Tool: {call['tool_name']}")
    print(f"  Request:  {req_time.strftime('%H:%M:%S.%f')[:-3]}")
    print(f"  Response: {resp_time.strftime('%H:%M:%S.%f')[:-3]}")
    print()

# Run analysis
def analyze_chronology_issue():
    print("=" * 60)
    print("CHRONOLOGY ISSUE ANALYSIS")
    print("=" * 60)
    print()

    print("SCENARIO:")
    print("  Main Agent starts Read at T1, completes at T4")
    print("  Subagent starts Grep at T2, completes at T3")
    print()

    print("-" * 60)
    print("CURRENT BEHAVIOR (Response Order):")
    print("-" * 60)
    current = simulate_current_behavior()
    for i, call in enumerate(current, 1):
        display_call_info(call, f"Call #{i}")

    print("-" * 60)
    print("CORRECT BEHAVIOR (Request Order):")
    print("-" * 60)
    correct = simulate_correct_behavior()
    for i, call in enumerate(correct, 1):
        display_call_info(call, f"Call #{i}")

    print("=" * 60)
    print("ROOT CAUSE:")
    print("  Tool calls are added to output list when RESPONSE arrives,")
    print("  not when REQUEST is made. Even though we sort by request")
    print("  timestamp, the sorting only applies within a single batch.")
    print("  Calls from different batches are never sorted together.")
    print("=" * 60)

if __name__ == "__main__":
    analyze_chronology_issue()
