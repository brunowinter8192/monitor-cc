# INFRASTRUCTURE
from src.jsonl.jsonl_cache_turns import extract_cache_turns
from src.jsonl.jsonl_reader import read_json_records
from src.pane_error_log import log_pane_note

_last_synthetic_key: tuple = ()

# FUNCTIONS

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
            prev = dict(merged_calls[dup_idx])
            prev['output_tokens'] = max(prev.get('output_tokens', 0), call.get('output_tokens', 0))
            prev['timestamp'] = max(prev.get('timestamp', ''), call.get('timestamp', ''))
            merged_calls[dup_idx] = prev
    merged['api_calls'] = merged_calls
    return existing_turns[:-1] + [merged] + new_turns[1:]


def build_cache_turns(filepath, last_position: int, existing_turns: list):
    if not filepath.exists():
        return existing_turns, last_position
    messages, new_position = read_json_records(filepath, last_position)
    if new_position == last_position:
        return existing_turns, last_position
    new_turns = extract_cache_turns(messages)
    if not new_turns and existing_turns and messages:
        _note_synthetic_user(filepath, existing_turns[-1])
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

def _note_synthetic_user(filepath, last_turn: dict) -> None:
    global _last_synthetic_key
    key = (str(filepath), last_turn.get('timestamp', ''))
    if key == _last_synthetic_key:
        return
    _last_synthetic_key = key
    log_pane_note('cache_turns', f'mid-turn batch without a user line in {filepath}: synthetic user prompt of the turn at {key[1]} prepended')
