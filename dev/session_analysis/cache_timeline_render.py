# INFRASTRUCTURE
from collections import defaultdict

from cache_timeline_parse import parse_timestamp, format_time, parse_session_turns
from cache_timeline_analysis import cache_status, classify_cache_event, find_time_gaps, TIME_GAP_MINUTES

BAR_WIDTH = 40

# FUNCTIONS

def type_label(turn):
    if turn['block_type'] == 'tool_use':
        name = turn['tool_name'] or 'Unknown'
        if '__' in name:
            name = name.split('__')[-1]
        return name[:22]
    elif turn['block_type'] == 'thinking':
        return 'Thinking'
    return 'Text'

def format_turn_table(turns, flags=None, anomalies_only=False):
    if not turns:
        return '_No assistant turns found._'
    flags = flags or {}
    header = (
        f'{"Turn":>5}  {"Time":8}  {"Direct":>8}  {"CacheNew":>10}  '
        f'{"CacheHit":>10}  {"Output":>8}  {"Tool/Type":<22}  {"Cache Status":<24}  Anomalies'
    )
    sep = '-' * len(header)
    rows = [header, sep]
    for i, turn in enumerate(turns, 1):
        turn_flags = flags.get(i - 1, [])
        if anomalies_only and not turn_flags:
            continue
        tl = type_label(turn)
        status = cache_status(turn)
        flag_str = '  '.join(turn_flags)
        rows.append(
            f'{i:>5}  {format_time(turn["timestamp"]):8}  '
            f'{turn["input_tokens"]:>8,}  '
            f'{turn["cache_creation"]:>10,}  '
            f'{turn["cache_read"]:>10,}  '
            f'{turn["output_tokens"]:>8,}  '
            f'{tl:<22}  {status:<24}  {flag_str}'
        )
    return '\n'.join(rows)

def format_anomalies_section(anomaly_details):
    counts = {'STUCK_CACHE': [], 'FAILED_RESUME': [], 'PREMATURE_TTL': []}
    for d in anomaly_details:
        counts[d['type']].append(d)
    lines = ['## Anomalies\n']
    for atype, items in counts.items():
        if not items:
            lines.append(f'{atype}: 0 occurrences')
        else:
            turn_ranges = ', '.join(
                f'turns {d["turns"][0]}-{d["turns"][1]}' if d["turns"][0] != d["turns"][1]
                else f'turn {d["turns"][0]}'
                for d in items
            )
            lines.append(f'{atype}: {len(items)} occurrence{"s" if len(items) > 1 else ""} ({turn_ranges})')
            for d in items:
                lines.append(f'  {d["description"]}')
    return '\n'.join(lines)

def format_summary(turns, anomaly_details=None):
    if not turns:
        return ''
    total_turns = len(turns)
    total_input = sum(t['input_tokens'] for t in turns)
    total_cc = sum(t['cache_creation'] for t in turns)
    total_cr = sum(t['cache_read'] for t in turns)
    total_output = sum(t['output_tokens'] for t in turns)
    total_tokens = total_input + total_cc + total_output
    total_cache = total_cr + total_cc
    hit_rate = int(total_cr / total_cache * 100) if total_cache else 0
    miss_count = sum(1 for t in turns if classify_cache_event(t) == 'MISS')
    partial_count = sum(1 for t in turns if classify_cache_event(t) == 'PARTIAL')
    spike_turn = max(turns, key=lambda t: t['cache_creation'] + t['input_tokens'])
    spike_idx = turns.index(spike_turn) + 1
    spike_label = type_label(spike_turn)
    spike_tokens = spike_turn['cache_creation'] + spike_turn['input_tokens']
    gaps = find_time_gaps(turns, TIME_GAP_MINUTES)
    lines = ['## Summary']
    lines.append(f'- Turns: {total_turns}')
    lines.append(f'- Total tokens: {total_tokens:,}  (input: {total_input + total_cc:,} | output: {total_output:,})')
    lines.append(f'- Cache hit rate: {hit_rate}%  (read: {total_cr:,} | new: {total_cc:,})')
    lines.append(f'- MISS events: {miss_count}  |  PARTIAL events: {partial_count}')
    lines.append(f'- Biggest spike: Turn {spike_idx} ({spike_label}) — {spike_tokens:,} tokens')
    if gaps:
        gap_strs = [f'{g["before_time"]}→{g["after_time"]} ({g["minutes"]:.0f}m)' for g in gaps]
        lines.append(f'- Gaps >{TIME_GAP_MINUTES}m: {", ".join(gap_strs)}')
    else:
        lines.append(f'- Gaps >{TIME_GAP_MINUTES}m: none')
    result = '\n'.join(lines)
    if anomaly_details is not None:
        result += '\n\n' + format_anomalies_section(anomaly_details)
    return result

def format_minute_chart(turns):
    if not turns:
        return '_No assistant turns found._'
    buckets = defaultdict(lambda: {'input': 0, 'cache_creation': 0, 'cache_read': 0, 'output': 0, 'turns': 0})
    for turn in turns:
        ts = parse_timestamp(turn['timestamp'])
        if not ts:
            continue
        key = ts.strftime('%H:%M')
        buckets[key]['input'] += turn['input_tokens']
        buckets[key]['cache_creation'] += turn['cache_creation']
        buckets[key]['cache_read'] += turn['cache_read']
        buckets[key]['output'] += turn['output_tokens']
        buckets[key]['turns'] += 1
    if not buckets:
        return '_No timestamps found._'
    sorted_keys = sorted(buckets.keys())
    max_tokens = max(
        b['input'] + b['cache_creation'] + b['output']
        for b in buckets.values()
    )
    lines = [f'{"Time":5}  {"Turns":>5}  {"Total Tokens":>14}  Bar']
    lines.append('-' * 60)
    for key in sorted_keys:
        b = buckets[key]
        total = b['input'] + b['cache_creation'] + b['output']
        bar_len = int(total / max_tokens * BAR_WIDTH) if max_tokens else 0
        lines.append(f'{key:5}  {b["turns"]:>5}  {total:>14,}  {"#" * bar_len}')
    return '\n'.join(lines)

def format_project_summary(sessions):
    rows = []
    for session_path in sessions:
        turns = parse_session_turns(session_path)
        if not turns:
            continue
        total_input = sum(t['input_tokens'] + t['cache_creation'] for t in turns)
        total_output = sum(t['output_tokens'] for t in turns)
        total_cr = sum(t['cache_read'] for t in turns)
        total_cc = sum(t['cache_creation'] for t in turns)
        total_cache = total_cr + total_cc
        hit_rate = int(total_cr / total_cache * 100) if total_cache else 0
        miss_count = sum(1 for t in turns if classify_cache_event(t) == 'MISS')
        first_ts = format_time(turns[0]['timestamp']) if turns else '?'
        last_ts = format_time(turns[-1]['timestamp']) if turns else '?'
        rows.append({
            'name': session_path.name[:36],
            'turns': len(turns),
            'input': total_input,
            'output': total_output,
            'hit_rate': hit_rate,
            'miss': miss_count,
            'first': first_ts,
            'last': last_ts,
        })
    if not rows:
        return '_No sessions with data found._'
    header = f'{"Session":<38}  {"Turns":>5}  {"Input":>10}  {"Output":>8}  {"Hit%":>5}  {"MISS":>4}  Time Range'
    sep = '-' * len(header)
    lines = [header, sep]
    for r in rows:
        lines.append(
            f'{r["name"]:<38}  {r["turns"]:>5}  {r["input"]:>10,}  '
            f'{r["output"]:>8,}  {r["hit_rate"]:>4}%  {r["miss"]:>4}  '
            f'{r["first"]}–{r["last"]}'
        )
    return '\n'.join(lines)
