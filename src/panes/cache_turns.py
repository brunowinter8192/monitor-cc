# INFRASTRUCTURE
from ..jsonl import read_new_lines, parse_jsonl_lines, extract_cache_turns

# FUNCTIONS

# The last existing turn was incomplete (streaming) when it was previously read — merge its
# api_calls with the freshly-parsed continuation of that same turn (matched by identical prompt).
# Returns the merged existing_turns list (last turn replaced, rest untouched).
def _merge_duplicate_turn(existing_turns: list, new_turns: list) -> list:
    merged = dict(existing_turns[-1])
    merged_calls = list(merged.get('api_calls', []))
    for call in new_turns[0].get('api_calls', []):
        new_rid = call.get('request_id', '')
        if new_rid:
            dup_idx = next(
                (i for i, c in enumerate(merged_calls) if c.get('request_id') == new_rid),
                None
            )
        else:
            dup_idx = next(
                (i for i, c in enumerate(merged_calls)
                 if c.get('cache_read') == call.get('cache_read')
                 and c.get('cache_creation') == call.get('cache_creation')
                 and c.get('direct') == call.get('direct')),
                None
            )
        if dup_idx is None:
            merged_calls.append(call)
        else:
            # Update output_tokens in case streaming advanced
            prev = dict(merged_calls[dup_idx])
            prev['output_tokens'] = max(prev.get('output_tokens', 0), call.get('output_tokens', 0))
            merged_calls[dup_idx] = prev
    merged['api_calls'] = merged_calls
    return existing_turns[:-1] + [merged] + new_turns[1:]


# Build cache turns incrementally — only reads new lines since last_position
def build_cache_turns(filepath, last_position: int, existing_turns: list):
    from ..jsonl import get_current_position
    lines = read_new_lines(filepath, last_position)
    new_position = get_current_position(filepath) if filepath.exists() else last_position
    if not lines:
        return existing_turns, last_position
    messages, _ = parse_jsonl_lines(lines)
    new_turns = extract_cache_turns(messages)
    if not new_turns and existing_turns and messages:
        # No user message in this batch → mid-turn requests (user message was read in a prior cycle)
        # Synthesize a user message from the last existing turn so extract_cache_turns
        # can set current_turn and process the assistant messages in this batch
        last_turn = existing_turns[-1]
        synthetic_user = {
            'type': 'user',
            'userType': 'external',
            'message': {'content': last_turn.get('prompt', '')},
            'timestamp': last_turn.get('timestamp', ''),
        }
        new_turns = extract_cache_turns([synthetic_user] + messages)
    if not new_turns:
        return existing_turns, new_position
    if existing_turns and new_turns[0].get('prompt') == existing_turns[-1].get('prompt'):
        result = _merge_duplicate_turn(existing_turns, new_turns)
    else:
        result = existing_turns + new_turns
    return result, new_position
