# INFRASTRUCTURE
from cache_rebuild_context_parse import parse_timestamp

REBUILD_THRESHOLD = 0.2
TIME_GAP_THRESHOLD_SECONDS = 300

# FUNCTIONS

def preceding_event_category(msg, gap_seconds):
    if gap_seconds is not None and gap_seconds > TIME_GAP_THRESHOLD_SECONDS:
        return 'time gap >5min'
    label = msg['label']
    if label in ('task-notification', 'skill-activation', 'system-reminder', 'tool_result'):
        return label
    if msg['type'] == 'user' and label.startswith('text:'):
        return 'user prompt (text)'
    if msg['type'] == 'assistant':
        return f'assistant ({label})'
    return label

def compute_prev_assistant_total(messages, i):
    for j in range(i - 1, -1, -1):
        if messages[j]['type'] == 'assistant':
            m = messages[j]
            return m['cache_read'] + m['cache_creation'] + m.get('input_tokens', 0)
    return None

def compute_gap_from_prev_assistant(messages, i):
    rebuild_ts = messages[i]['timestamp']
    for j in range(i - 1, -1, -1):
        if messages[j]['type'] == 'assistant' and messages[j]['timestamp']:
            t_prev = parse_timestamp(messages[j]['timestamp'])
            t_curr = parse_timestamp(rebuild_ts)
            if t_prev and t_curr:
                return (t_curr - t_prev).total_seconds()
            break
    return None

def compute_preceding_event(messages, rebuild_idx, gap_seconds):
    if rebuild_idx == 0:
        return 'unknown', 'unknown'
    prev_msg = messages[rebuild_idx - 1]
    category = preceding_event_category(prev_msg, gap_seconds)
    return prev_msg['label'], category

def detect_rebuilds(messages):
    rebuilds = []
    prev_max_cr = 0
    first_assistant = True

    for i, msg in enumerate(messages):
        if msg['type'] != 'assistant':
            continue
        cr = msg['cache_read']
        cc = msg['cache_creation']

        if first_assistant:
            first_assistant = False
            prev_max_cr = max(prev_max_cr, cr)
            continue

        if prev_max_cr > 0 and cc > cr and cr < prev_max_cr * REBUILD_THRESHOLD:
            gap_seconds = compute_gap_from_prev_assistant(messages, i)
            preceding_label, preceding_category = compute_preceding_event(messages, i, gap_seconds)
            rebuild_total = cr + cc + msg.get('input_tokens', 0)
            prev_total = compute_prev_assistant_total(messages, i)
            if prev_total is not None and prev_total > 0:
                delta = rebuild_total - prev_total
                delta_pct = delta / prev_total * 100
            else:
                delta = None
                delta_pct = None
            rebuilds.append({
                'msg_index': i,
                'timestamp': msg['timestamp'],
                'cache_read': cr,
                'cache_creation': cc,
                'prev_max_cr': prev_max_cr,
                'gap_seconds': gap_seconds,
                'preceding_label': preceding_label,
                'preceding_category': preceding_category,
                'rebuild_total': rebuild_total,
                'prev_total': prev_total,
                'delta': delta,
                'delta_pct': delta_pct,
            })

        prev_max_cr = max(prev_max_cr, cr)

    return rebuilds
