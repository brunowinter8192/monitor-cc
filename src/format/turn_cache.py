# INFRASTRUCTURE
import datetime
import itertools
import operator
import time
from typing import Callable, Optional

# ORCHESTRATOR

def sync_document(cache: dict, turns: list, inputs: dict, render_turn: Callable) -> dict:
    signature = _global_signature(inputs)
    _reset_on_signature_change(cache, signature)
    dirty, structure_changed = _turn_structure_changes(cache, turns)
    dirty |= _expand_changes(cache, inputs)
    dirty |= _flash_changes(cache, inputs)
    dirty |= _search_changes(cache, inputs)
    dirty |= _response_data_changes(cache, turns, inputs)
    _render_dirty_turns(cache, turns, inputs, dirty, render_turn)
    if dirty or structure_changed or cache['document'] is None:
        cache['document'] = _assemble_document(cache, inputs)
        cache['generation'] += 1
    return cache['document']

# FUNCTIONS

def new_turn_cache() -> dict:
    return {
        'signature': None, 'entries': [], 'bases': [], 'document': None, 'generation': 0,
        'expanded': frozenset(), 'flash': frozenset(), 'rid_fingerprints': {},
        'search_ref': None, 'search_len': -1, 'search_keys': frozenset(),
        'search_current': None, 'search_query': '',
        'nav_owner': None, 'nav_generation': -1,
    }

def publish_nav(cache: dict, nav_out: dict) -> None:
    document = cache['document']
    if cache['nav_owner'] is nav_out and cache['nav_generation'] == cache['generation'] and len(nav_out) == len(document['nav']):
        return
    nav_out.clear()
    nav_out.update(document['nav'])
    cache['nav_owner'] = nav_out
    cache['nav_generation'] = cache['generation']

def _global_signature(inputs: dict) -> tuple:
    return (inputs['pane_width'], inputs['wide'], inputs['copy_feedback'] is None, tuple(inputs['preamble_lines']))

def _reset_on_signature_change(cache: dict, signature: tuple) -> None:
    if cache['signature'] == signature:
        return
    cache['signature'] = signature
    cache['entries'] = []
    cache['bases'] = []
    cache['document'] = None

def _turn_structure_changes(cache: dict, turns: list) -> tuple:
    entries = cache['entries']
    if len(entries) == len(turns) and all(map(operator.is_, (e['turn'] if e else None for e in entries), turns)):
        return set(), False
    bases = list(itertools.accumulate((len(t.get('api_calls', [])) for t in turns), initial=0))
    dirty = set()
    for i, turn in enumerate(turns):
        entry = entries[i] if i < len(entries) else None
        if entry is None or entry['turn'] is not turn or entry['base'] != bases[i]:
            dirty.add(i)
    del entries[len(turns):]
    entries.extend([None] * (len(turns) - len(entries)))
    cache['bases'] = bases
    return dirty, True

def _key_turn_index(key: tuple) -> int:
    return key[1] if key[0] == 'turn' else key[0]

def _turn_indices(keys) -> set:
    return {_key_turn_index(k) for k in keys if k is not None}

def _expand_changes(cache: dict, inputs: dict) -> set:
    expanded = frozenset(k for k, v in inputs['expand_states'].items() if v)
    changed = expanded ^ cache['expanded']
    cache['expanded'] = expanded
    return _turn_indices(changed)

def _flash_changes(cache: dict, inputs: dict) -> set:
    copy_feedback = inputs['copy_feedback']
    if copy_feedback is None:
        flash = frozenset()
    else:
        now = time.time()
        flash = frozenset(k for k, until in copy_feedback.items() if until > now)
    changed = flash ^ cache['flash']
    cache['flash'] = flash
    return _turn_indices(changed)

def _search_changes(cache: dict, inputs: dict) -> set:
    match_set = inputs['search_match_set']
    current = inputs['search_current_key']
    query = inputs['search_query']
    unchanged = (
        match_set is cache['search_ref'] and len(match_set or ()) == cache['search_len']
        and current == cache['search_current'] and query == cache['search_query']
    )
    if unchanged:
        return set()
    new_keys = frozenset(match_set or ())
    old_keys = cache['search_keys']
    changed = new_keys ^ old_keys
    changed |= {cache['search_current'], current}
    if query != cache['search_query']:
        changed |= new_keys | old_keys
    cache['search_ref'] = match_set
    cache['search_len'] = len(match_set or ())
    cache['search_keys'] = new_keys
    cache['search_current'] = current
    cache['search_query'] = query
    return _turn_indices(changed)

def _response_data_changes(cache: dict, turns: list, inputs: dict) -> set:
    response_rid_map = inputs['response_rid_map'] or {}
    today = datetime.date.today().isoformat()
    fingerprints = {}
    for key in cache['expanded']:
        turn_idx, call_idx = key
        calls = turns[turn_idx].get('api_calls', []) if turn_idx < len(turns) else []
        if call_idx >= len(calls):
            continue
        rid = calls[call_idx].get('request_id', '')
        entry = response_rid_map.get(rid) if rid else None
        fingerprints[key] = (repr(entry), today)
    previous = cache['rid_fingerprints']
    changed = {k for k in fingerprints.keys() | previous.keys() if fingerprints.get(k) != previous.get(k)}
    cache['rid_fingerprints'] = fingerprints
    return _turn_indices(changed)

def _render_dirty_turns(cache: dict, turns: list, inputs: dict, dirty: set, render_turn: Callable) -> None:
    entries = cache['entries']
    bases = cache['bases']
    for i in sorted(dirty):
        if i >= len(turns):
            continue
        turn = turns[i]
        number_row = list(range(bases[i] + 1, bases[i] + 1 + len(turn.get('api_calls', []))))
        lines, keys, nav = [], [], {}
        render_turn(i, turn, number_row, inputs, lines, keys, nav)
        entries[i] = {'turn': turn, 'base': bases[i], 'lines': lines, 'keys': keys, 'nav': nav}

def _assemble_document(cache: dict, inputs: dict) -> dict:
    lines = list(inputs['preamble_lines'])
    keys = [None] * len(lines)
    nav = {}
    for entry in cache['entries']:
        offset = len(lines)
        for key, rel in entry['nav'].items():
            nav[key] = rel + offset
        lines.extend(entry['lines'])
        keys.extend(entry['keys'])
    while lines and lines[-1] == '':
        lines.pop()
        keys.pop()
    nav['total_lines'] = len(lines)
    prefix = list(itertools.accumulate((k is not None for k in keys), initial=0))
    return {'lines': lines, 'keys': keys, 'nav': nav, 'parent_prefix': prefix}
