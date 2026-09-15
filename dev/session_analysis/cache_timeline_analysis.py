# INFRASTRUCTURE
from collections import defaultdict

from cache_timeline_parse import parse_timestamp, format_time

LARGE_CACHE_THRESHOLD = 10000
TIME_GAP_MINUTES = 5
TIME_GAP_SECONDS_SMALL = 5
TTL_MAX_MINUTES = 60

# FUNCTIONS

def cache_status(turn):
    cr = turn['cache_read']
    cc = turn['cache_creation']
    total_cache = cr + cc
    if cr == 0 and cc > LARGE_CACHE_THRESHOLD:
        return f'MISS ({format_k(cc)} new)'
    elif cc > LARGE_CACHE_THRESHOLD and cc > cr:
        hit_pct = int(cr / total_cache * 100) if total_cache else 0
        return f'PARTIAL ({hit_pct}% hit)'
    elif total_cache > 0:
        hit_pct = int(cr / total_cache * 100) if total_cache else 0
        return f'HIT ({hit_pct}%)'
    return 'NO CACHE'

def classify_cache_event(turn):
    cr = turn['cache_read']
    cc = turn['cache_creation']
    if cr == 0 and cc > LARGE_CACHE_THRESHOLD:
        return 'MISS'
    elif cc > LARGE_CACHE_THRESHOLD and cc > cr:
        return 'PARTIAL'
    return 'HIT'

def format_k(n):
    if n >= 1000:
        return f'{n/1000:.1f}k'
    return str(n)

def _detect_stuck_cache(turns):
    flags = defaultdict(list)
    details = []

    for i in range(4, len(turns)):
        cr_n = turns[i]['cache_read']
        cr_n2 = turns[i - 2]['cache_read']
        cr_n4 = turns[i - 4]['cache_read']
        cc_n = turns[i]['cache_creation']
        if cr_n == cr_n2 == cr_n4 and cc_n > cr_n:
            flags[i].append('STUCK_CACHE')

    stuck_indices = sorted(i for i, f in flags.items() if 'STUCK_CACHE' in f)
    if stuck_indices:
        ranges = []
        start = prev = stuck_indices[0]
        for idx in stuck_indices[1:]:
            if idx == prev + 1:
                prev = idx
            else:
                ranges.append((start, prev))
                start = prev = idx
        ranges.append((start, prev))
        for s, e in ranges:
            cr_stuck = turns[s]['cache_read']
            cc_s = turns[s]['cache_creation']
            cc_e = turns[e]['cache_creation']
            details.append({
                'type': 'STUCK_CACHE',
                'turns': (s + 1, e + 1),
                'description': (
                    f'cache_read stuck at {cr_stuck:,} for {e - s + 1} turns '
                    f'while cache_creation grew from {format_k(cc_s)} to {format_k(cc_e)}'
                ),
            })
    return flags, details

def _detect_failed_resume(turns):
    flags = defaultdict(list)
    details = []
    for i in range(1, len(turns) - 1):
        t_prev = parse_timestamp(turns[i - 1]['timestamp'])
        t_curr = parse_timestamp(turns[i]['timestamp'])
        if not (t_prev and t_curr):
            continue
        gap_seconds = (t_curr - t_prev).total_seconds()
        if gap_seconds <= TIME_GAP_SECONDS_SMALL:
            continue
        if turns[i]['cache_read'] != 0:
            continue
        cr_next = turns[i + 1]['cache_read']
        cc_next = turns[i + 1]['cache_creation']
        if cc_next > 0 and cr_next < cc_next * 0.5:
            flags[i + 1].append('FAILED_RESUME')
            details.append({
                'type': 'FAILED_RESUME',
                'turns': (i + 1, i + 2),
                'description': (
                    f'Resume at {format_time(turns[i]["timestamp"])} after '
                    f'{gap_seconds / 60:.0f}m gap, cache_read did not recover by turn {i + 2}'
                ),
            })
    return flags, details

def _detect_premature_ttl(turns):
    flags = defaultdict(list)
    details = []
    for i in range(1, len(turns)):
        t_prev = parse_timestamp(turns[i - 1]['timestamp'])
        t_curr = parse_timestamp(turns[i]['timestamp'])
        if not (t_prev and t_curr):
            continue
        gap_minutes = (t_curr - t_prev).total_seconds() / 60
        if not (TIME_GAP_MINUTES < gap_minutes < TTL_MAX_MINUTES):
            continue
        cr = turns[i]['cache_read']
        cc = turns[i]['cache_creation']
        if cr == 0 and cc > LARGE_CACHE_THRESHOLD:
            flags[i].append('PREMATURE_TTL')
            details.append({
                'type': 'PREMATURE_TTL',
                'turns': (i + 1, i + 1),
                'description': (
                    f'Full cache rebuild ({format_k(cc)} new) after {gap_minutes:.0f}m gap '
                    f'at turn {i + 1} ({format_time(turns[i]["timestamp"])})'
                ),
            })
    return flags, details

def detect_anomalies(turns):
    flags = defaultdict(list)
    details = []
    for detector in (_detect_stuck_cache, _detect_failed_resume, _detect_premature_ttl):
        sub_flags, sub_details = detector(turns)
        for i, fl in sub_flags.items():
            flags[i].extend(fl)
        details.extend(sub_details)
    return dict(flags), details

def find_time_gaps(turns, min_gap_minutes):
    gaps = []
    for i in range(1, len(turns)):
        t_prev = parse_timestamp(turns[i - 1]['timestamp'])
        t_curr = parse_timestamp(turns[i]['timestamp'])
        if t_prev and t_curr:
            diff = (t_curr - t_prev).total_seconds() / 60
            if diff >= min_gap_minutes:
                gaps.append({
                    'before_time': format_time(turns[i - 1]['timestamp']),
                    'after_time': format_time(turns[i]['timestamp']),
                    'minutes': diff,
                    'turn_before': i,
                    'turn_after': i + 1,
                })
    return gaps
