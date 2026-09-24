# INFRASTRUCTURE
import time
from bisect import bisect_right
from itertools import accumulate, chain

from src.format.token_format import _format_turn_header_line, request_numbers_by_id, request_times_by_id
from src.pane_error_log import log_pane_note
from src.proxy_display.dual_log_accumulator import overlay_epoch
from src.proxy_display.format import _assign_turns_to_entries, _compute_collision_idxs, _is_standalone_entry, _shorten_model
from src.proxy_display.proxy_badge import badge_flags
from src.proxy_display.render_turn import _req_label, _resolve_prev_same_family, render_turn_expanded

# ORCHESTRATOR

def render_frozen(entries: list, groups: list, expand_states: dict, pane_width: int, turns, copy_feedback, search_match_set, search_current_entry_idx, search_query: str, request_id_by_flow, cache) -> dict:
    number_by_flow, time_by_flow = _resolve_flow_maps(turns, request_id_by_flow, cache)
    ctx = _build_context(expand_states, pane_width, copy_feedback, search_match_set, search_current_entry_idx, search_query, time.time())
    records, opus_labels = _resolve_records(groups, entries, turns, number_by_flow, time_by_flow, ctx, copy_feedback, cache)
    return _resolve_flat(records, opus_labels, cache)

# FUNCTIONS

def assign_groups(entries: list, turns, cache) -> list:
    if not turns:
        return [{'turn_idx': 0, 'timestamp': '', 'entry_pairs': list(enumerate(entries))}]
    stamps = [t.get('timestamp', '') for t in turns]
    if all(stamps[i] <= stamps[i + 1] for i in range(len(stamps) - 1)):
        _note_assign_path(cache, 'bisect')
        return _assign_bisect(entries, turns, stamps)
    _note_assign_path(cache, 'linear (turn timestamps not sorted)')
    return _assign_turns_to_entries(entries, turns)

def _note_assign_path(cache, path: str) -> None:
    if cache.assign_path != path:
        cache.assign_path = path
        log_pane_note(cache.name, f'turn assignment path: {path}')

def _assign_bisect(entries: list, turns: list, stamps: list) -> list:
    groups = [{'turn_idx': i, 'timestamp': stamps[i], 'entry_pairs': []} for i in range(len(turns))]
    for entry_idx, entry in enumerate(entries):
        turn_idx = max(0, bisect_right(stamps, entry.get('timestamp', '')) - 1)
        groups[turn_idx]['entry_pairs'].append((entry_idx, entry))
    return [g for g in groups if g['entry_pairs']]

def _resolve_flow_maps(turns, request_id_by_flow, cache) -> tuple:
    key = tuple(id(t) for t in (turns or []))
    if cache.flow_key != key or cache.flow_maps is None:
        cache.flow_turns = list(turns or [])
        cache.flow_key = key
        cache.flow_maps = (request_numbers_by_id(cache.flow_turns), request_times_by_id(cache.flow_turns))
    numbers, times = cache.flow_maps
    by_flow = request_id_by_flow or {}
    number_by_flow = {flow_id: numbers[rid] for flow_id, rid in by_flow.items() if rid in numbers}
    time_by_flow = {flow_id: times[rid] for flow_id, rid in by_flow.items() if rid in times}
    return number_by_flow, time_by_flow

def _key_entry_idx(key) -> int:
    if isinstance(key, int):
        return key
    if isinstance(key, tuple) and len(key) >= 2:
        if isinstance(key[0], str) and isinstance(key[1], int):
            return key[1]
        if isinstance(key[0], int):
            return key[0]
    raise ValueError(f'unclassifiable state key: {key!r}')

def _keys_by_entry(keys) -> dict:
    buckets = {}
    for key in keys:
        buckets.setdefault(_key_entry_idx(key), set()).add(key)
    return {idx: frozenset(ks) for idx, ks in buckets.items()}

def _build_context(expand_states: dict, pane_width: int, copy_feedback, search_match_set, search_current_entry_idx, search_query: str, now: float) -> dict:
    flashing = [k for k, until in (copy_feedback or {}).items() if until > now]
    return {
        'expand_states': expand_states,
        'width': pane_width,
        'feedback_off': copy_feedback is None,
        'expanded': _keys_by_entry(k for k, v in expand_states.items() if v),
        'flash': _keys_by_entry(flashing),
        'match_set': search_match_set,
        'current_idx': search_current_entry_idx,
        'query': search_query,
        'epoch': overlay_epoch(),
    }

def _label_group(group: dict, number_by_flow: dict, time_by_flow: dict, label_counts: dict, opus_labels: list) -> tuple:
    labels = []
    time_strs = []
    for entry_idx, entry in group['entry_pairs']:
        model_short = _shorten_model(entry.get('model', '?'))
        label = _req_label(entry, model_short, number_by_flow, label_counts)
        if model_short != 'haiku' and not _is_standalone_entry(entry) and label != 'REQ #?':
            opus_labels.append((entry_idx, label))
        labels.append(label)
        time_strs.append(time_by_flow.get(entry.get('flow_id'), '') if label.startswith('REQ #') else '')
    return labels, time_strs

def _messages_signature(entry) -> tuple:
    messages = entry.get('messages') if entry is not None else None
    return (id(messages), -1 if messages is None else len(messages))

def _expanded_signature(entry_idx: int, entry: dict, entries: list, ctx: dict) -> tuple:
    prev_same = _resolve_prev_same_family(entries, entry_idx)
    return (ctx['epoch'], _messages_signature(entry), _messages_signature(prev_same), id(prev_same))

def _entry_fingerprint(entry_idx: int, entry: dict, label: str, time_str: str, entries: list, ctx: dict) -> tuple:
    match_set = ctx['match_set']
    is_match = bool(match_set) and entry_idx in match_set
    expanded_keys = ctx['expanded'].get(entry_idx, frozenset())
    base = (
        entry_idx, id(entry), label, time_str,
        'http_status' in entry, entry.get('http_status'),
        badge_flags(entry), entry.get('messages_total_chars'),
        is_match, ctx['current_idx'] == entry_idx if is_match else False, ctx['query'] if is_match else '',
        ctx['flash'].get(entry_idx, frozenset()), expanded_keys,
    )
    if ('req', entry_idx) in expanded_keys:
        return base + _expanded_signature(entry_idx, entry, entries, ctx)
    return base

def _group_fingerprint(group: dict, labels: list, time_strs: list, entries: list, turns, ctx: dict) -> tuple:
    turn = turns[group['turn_idx']] if turns else None
    header_sig = (id(turn), len(turn.get('api_calls', []))) if turn is not None else None
    entry_sigs = tuple(
        _entry_fingerprint(entry_idx, entry, label, time_str, entries, ctx)
        for (entry_idx, entry), label, time_str in zip(group['entry_pairs'], labels, time_strs)
    )
    return (group['turn_idx'], ctx['width'], ctx['feedback_off'], header_sig, entry_sigs)

def _render_record(group: dict, fp: tuple, labels: list, entries: list, turns, number_by_flow: dict, time_by_flow: dict, ctx: dict, copy_feedback) -> dict:
    turn_idx = group['turn_idx']
    lines = []
    keys = []
    if turns:
        lines.append(_format_turn_header_line(turn_idx, turns[turn_idx], ctx['width']))
        keys.append(None)
    t_lines, t_keys = render_turn_expanded(
        group, entries, ctx['expand_states'], ctx['width'], number_by_flow, {}, time_by_flow,
        turns=turns, turn_idx=turn_idx, rendered_opus_labels=None,
        copy_feedback=copy_feedback, copy_rows_out=None,
        search_match_set=ctx['match_set'], search_current_entry_idx=ctx['current_idx'],
        search_query=ctx['query'], labels=labels,
    )
    lines.extend(t_lines)
    keys.extend(t_keys)
    lines.append('')
    keys.append(None)
    return {'fp': fp, 'lines': lines, 'keys': keys, 'entry_pairs': group['entry_pairs'], 'turn': turns[turn_idx] if turns else None}

def _resolve_records(groups: list, entries: list, turns, number_by_flow: dict, time_by_flow: dict, ctx: dict, copy_feedback, cache) -> tuple:
    label_counts = {}
    opus_labels = []
    resolved = []
    for group in groups:
        labels, time_strs = _label_group(group, number_by_flow, time_by_flow, label_counts, opus_labels)
        fp = _group_fingerprint(group, labels, time_strs, entries, turns, ctx)
        record = cache.records.get(group['turn_idx'])
        if record is None or record['fp'] != fp:
            record = _render_record(group, fp, labels, entries, turns, number_by_flow, time_by_flow, ctx, copy_feedback)
        resolved.append((group['turn_idx'], record))
    cache.records = dict(resolved)
    return [record for _, record in resolved], opus_labels

def _same_records(previous: list, current: list) -> bool:
    return len(previous) == len(current) and all(a is b for a, b in zip(previous, current))

def _resolve_flat(records: list, opus_labels: list, cache) -> dict:
    if cache.flat is not None and _same_records(cache.flat['records'], records):
        return cache.flat
    all_lines = list(chain.from_iterable(r['lines'] for r in records))
    line_keys = list(chain.from_iterable(r['keys'] for r in records))
    while all_lines and all_lines[-1] == '':
        all_lines.pop()
        line_keys.pop()
    positions = {}
    for i, key in enumerate(line_keys):
        if key is not None:
            positions[key] = i
    parent_prefix = [0] + list(accumulate(1 if k is not None else 0 for k in line_keys))
    cache.flat = {
        'records': records, 'lines': all_lines, 'keys': line_keys, 'positions': positions,
        'parent_prefix': parent_prefix, 'collision': _compute_collision_idxs(opus_labels),
    }
    return cache.flat
