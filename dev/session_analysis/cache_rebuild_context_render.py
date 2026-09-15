# INFRASTRUCTURE
from collections import defaultdict

from cache_rebuild_context_parse import format_time, format_gap

# FUNCTIONS

def _format_rebuild_header(rebuild, rebuild_num):
    time_str = format_time(rebuild['timestamp'])
    cr = rebuild['cache_read']
    cc = rebuild['cache_creation']
    prev_max = rebuild['prev_max_cr']
    gap = rebuild['gap_seconds']

    lines = [f'=== REBUILD #{rebuild_num} at {time_str} ===']
    lines.append(f'  CR: {cr:,}  CC: {cc:,}  (prev max CR was {prev_max:,})')
    if rebuild.get('prev_total') is not None and rebuild.get('delta') is not None:
        prev_t = rebuild['prev_total']
        reb_t = rebuild['rebuild_total']
        delta = rebuild['delta']
        delta_pct = rebuild['delta_pct']
        sign = '+' if delta >= 0 else ''
        lines.append(f'  Total input: {prev_t:,} → {reb_t:,}  (delta: {sign}{delta:,}, {sign}{delta_pct:.1f}%)')
    if gap is not None:
        lines.append(f'  Gap from previous API call: {format_gap(gap)}')
    return lines

def _format_context_row(msg, idx, j):
    offset = j - idx
    ts = format_time(msg['timestamp'])

    if offset == 0:
        offset_str = '*0'
    elif offset > 0:
        offset_str = f'+{offset}'
    else:
        offset_str = str(offset)

    type_col = msg['type'][:10]
    suffix = '  ← REBUILD' if offset == 0 else ''

    if msg['type'] == 'assistant':
        mcr = msg['cache_read']
        mcc = msg['cache_creation']
        cache_part = f'CR: {mcr:,} CC: {mcc:,}'
        return f'  [{offset_str:>3}] [{ts}] {type_col:<10}  {cache_part}  {msg["label"]}{suffix}'
    return f'  [{offset_str:>3}] [{ts}] {type_col:<10}  {msg["label"]}{suffix}'

def format_rebuild_block(rebuild, messages, rebuild_num, context_window):
    idx = rebuild['msg_index']
    lines = _format_rebuild_header(rebuild, rebuild_num)

    lines.append('')
    lines.append(f'  Context ({context_window} before → rebuild → {context_window} after):')

    start = max(0, idx - context_window)
    end = min(len(messages) - 1, idx + context_window)

    for j in range(start, end + 1):
        lines.append(_format_context_row(messages[j], idx, j))

    return '\n'.join(lines)

def format_pattern_summary(rebuilds):
    if not rebuilds:
        return '_No rebuilds to summarize._'
    counts = defaultdict(int)
    total = len(rebuilds)
    for r in rebuilds:
        counts[r['preceding_category']] += 1
    rows = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    w = max(len('Event before rebuild'), max(len(label) for label, _ in rows))
    lines = [f'\n## Preceding Event Patterns (event immediately before rebuild)']
    lines.append(f'| {"Event before rebuild":<{w}} | {"Count":>5} | {"Percentage":>10} |')
    lines.append(f'|{"-"*(w+2)}|{"-"*7}|{"-"*12}|')
    for label, count in rows:
        pct = int(count / total * 100)
        lines.append(f'| {label:<{w}} | {count:>5} | {pct:>9}% |')
    return '\n'.join(lines)

def format_delta_summary(rebuilds):
    cats = {'Same (±1%)': 0, 'Grew (>1%)': 0, 'Shrunk (<-1%)': 0}
    total = 0
    for r in rebuilds:
        if r.get('delta_pct') is None:
            continue
        total += 1
        pct = r['delta_pct']
        if abs(pct) <= 1:
            cats['Same (±1%)'] += 1
        elif pct > 1:
            cats['Grew (>1%)'] += 1
        else:
            cats['Shrunk (<-1%)'] += 1
    if total == 0:
        return ''
    ordered = list(cats.items())
    w = max(len('Category'), max(len(k) for k, _ in ordered))
    lines = ['\n## Total Input Delta Analysis']
    lines.append(f'| {"Category":<{w}} | {"Count":>5} | {"Percentage":>10} |')
    lines.append(f'|{"-"*(w+2)}|{"-"*7}|{"-"*12}|')
    for label, count in ordered:
        pct_val = int(count / total * 100) if total else 0
        lines.append(f'| {label:<{w}} | {count:>5} | {pct_val:>9}% |')
    return '\n'.join(lines)

def format_session_rebuild_table(session_rows):
    if not session_rows:
        return '_No sessions with cache rebuilds found._'
    lines = [f'| {"Session":<52} | {"Rebuilds":>8} |']
    lines.append(f'|{"-"*54}|{"-"*10}|')
    for session_path, count in session_rows:
        name = session_path.name[:50]
        lines.append(f'| {name:<52} | {count:>8} |')
    return '\n'.join(lines)
