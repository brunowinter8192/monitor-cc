"""Extract and cluster all rag-cli search calls from Opus proxy logs for helpfulness eval.

Input:  src/logs/api_requests_opus_monitor_cc_*.jsonl  (positional or default glob)
Output: dev/tool_use_analysis/<YYYYMMDD>_rag_query_audit.md  (--output or auto-dated)
"""

# INFRASTRUCTURE
import argparse
import glob
import json
import re
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional

# Matches: rag-cli <verb> "<query>" <collection> [--top-k N]
# Handles compound bash (;/&&) — scanned iteratively via findall
RAG_RE = re.compile(
    r'rag-cli\s+(search_hybrid|search_keyword|search_dense|search)'
    r'\s+"([^"]+)"\s+([^\s;|&]+?)(?:\s+--top-k\s+(\d+))?(?=\s|;|&&|\||$)'
)
CHUNK_RE  = re.compile(r'--- Result \d+')
TRUNC_RE  = re.compile(r'\[\d+ characters? truncated\]')

STOPWORDS = frozenset({
    'the', 'a', 'an', 'in', 'on', 'of', 'to', 'for', 'and', 'or',
    'is', 'are', 'was', 'were', 'it', 'its', 'with', 'from', 'by',
})

PLACEHOLDER = '_'   # fill in manual annotation columns


class RagCall(NamedTuple):
    tool_use_id: str
    verb:        str
    query:       str
    collection:  str
    top_k:       Optional[int]
    timestamp:   str
    source:      str   # short log label


class ResultInfo(NamedTuple):
    chars:     int
    chunks:    int
    truncated: bool


class Topic(NamedTuple):
    topic_id:  str   # T001, T002, …
    source:    str
    calls:     List[RagCall]


# ORCHESTRATOR

def run(jsonl_paths, output_path, jaccard_threshold):
    per_source_events: Dict[str, list] = {}
    all_events: list = []

    for path in jsonl_paths:
        label = _source_label(path)
        evs   = _load_proxy(path)
        per_source_events[label] = evs
        all_events.extend(evs)

    rag_calls   = _collect_rag_calls(all_events)
    results     = _collect_results(all_events, set(rag_calls))
    topics      = _cluster_topics(rag_calls, jaccard_threshold)
    report      = _build_report(jsonl_paths, per_source_events, rag_calls,
                                results, topics, jaccard_threshold)
    _write_output(report, output_path)


# FUNCTIONS

def _load_proxy(path):
    events = []
    label  = _source_label(path)
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get('raw_payload') is None:
                continue
            d['_source'] = label
            events.append(d)
    return events


def _source_label(path):
    base = os.path.basename(path)
    if base.startswith('api_requests_'):
        base = base[len('api_requests_'):]
    return base[:-len('.jsonl')] if base.endswith('.jsonl') else base


def _collect_rag_calls(events) -> Dict[str, RagCall]:
    """Return deduped {tool_use_id: RagCall} across all events."""
    out: Dict[str, RagCall] = {}
    for ev in events:
        ts  = ev.get('timestamp', '')
        src = ev.get('_source', '')
        for msg in ev.get('raw_payload', {}).get('messages', []):
            content = msg.get('content', [])
            if not isinstance(content, list):
                continue
            for blk in content:
                if not isinstance(blk, dict) or blk.get('type') != 'tool_use':
                    continue
                bid = blk.get('id', '')
                if not bid or bid in out:
                    continue
                cmd = blk.get('input', {}).get('command', '')
                for m in RAG_RE.finditer(cmd):
                    verb, query, coll, topk_s = m.group(1), m.group(2), m.group(3), m.group(4)
                    # Strip trailing backtick that occasionally appears in collection names
                    coll = coll.rstrip('`\\')
                    top_k = int(topk_s) if topk_s else None
                    # Use composite id when a single bash block holds multiple rag calls
                    uid = f"{bid}:{m.start()}"
                    out[uid] = RagCall(uid, verb, query, coll, top_k, ts, src)
    return out


def _collect_results(events, rag_ids) -> Dict[str, ResultInfo]:
    """Pair each tool_use_id with its tool_result (deduped by tool_use_id prefix)."""
    # rag_ids are composite "tool_use_id:offset"; map base id → composite id
    base_to_uid: Dict[str, str] = {}
    for uid in rag_ids:
        base = uid.split(':')[0]
        base_to_uid.setdefault(base, uid)

    out: Dict[str, ResultInfo] = {}
    seen_bases: set = set()

    for ev in events:
        for msg in ev.get('raw_payload', {}).get('messages', []):
            content = msg.get('content', [])
            if not isinstance(content, list):
                continue
            for blk in content:
                if not isinstance(blk, dict) or blk.get('type') != 'tool_result':
                    continue
                base = blk.get('tool_use_id', '')
                if not base or base not in base_to_uid or base in seen_bases:
                    continue
                seen_bases.add(base)
                raw_c = blk.get('content', '')
                text  = (raw_c if isinstance(raw_c, str)
                         else ''.join(rc.get('text', '') if isinstance(rc, dict) else str(rc)
                                      for rc in raw_c))
                uid = base_to_uid[base]
                out[uid] = ResultInfo(
                    chars     = len(text),
                    chunks    = len(CHUNK_RE.findall(text)),
                    truncated = bool(TRUNC_RE.search(text)),
                )
    return out


def _jaccard(q1: str, q2: str) -> float:
    t1 = set(q1.lower().split()) - STOPWORDS
    t2 = set(q2.lower().split()) - STOPWORDS
    if not t1 or not t2:
        return 0.0
    return len(t1 & t2) / len(t1 | t2)


def _cluster_topics(rag_calls: Dict[str, RagCall], threshold: float) -> List[Topic]:
    """Greedy chain-link per session: new topic when max jaccard to any existing call < threshold."""
    # Group by source, sorted by timestamp then by uid for stability
    by_source: Dict[str, List[RagCall]] = defaultdict(list)
    for call in rag_calls.values():
        by_source[call.source].append(call)
    for calls in by_source.values():
        calls.sort(key=lambda c: (c.timestamp, c.tool_use_id))

    topics: List[Topic] = []
    counter = 1

    for source in sorted(by_source):
        calls = by_source[source]
        open_topics: List[List[RagCall]] = []   # list of in-progress topic buckets

        for call in calls:
            # Find best-matching open topic
            best_idx, best_j = -1, -1.0
            for i, bucket in enumerate(open_topics):
                j = max(_jaccard(call.query, c.query) for c in bucket)
                if j > best_j:
                    best_j, best_idx = j, i
            if best_j >= threshold:
                open_topics[best_idx].append(call)
            else:
                open_topics.append([call])

        for bucket in open_topics:
            topics.append(Topic(f'T{counter:03d}', source, bucket))
            counter += 1

    return topics


def _build_report(jsonl_paths, per_source_events, rag_calls, results, topics, threshold) -> str:
    ts    = datetime.now().strftime('%Y-%m-%dT%H:%M')
    lines = []

    lines.append(f'# RAG Query Audit — {ts}')
    lines.append('')

    # Source block (CONVENTION.md §2)
    lines.append('## Source JSONLs')
    lines.append('')
    total_events = 0
    for path in jsonl_paths:
        label = _source_label(path)
        evs   = per_source_events.get(label, [])
        n_rag = sum(1 for c in rag_calls.values() if c.source == label)
        lines.append(f'- `{os.path.basename(path)}` ({len(evs)} events, {n_rag} rag-cli calls)')
        total_events += len(evs)
    total_calls  = len(rag_calls)
    total_topics = len(topics)
    lines.append('')
    lines.append(f'Total sessions analyzed: {len(jsonl_paths)}. '
                 f'Total events: {total_events}. '
                 f'Total rag-cli calls (unique): {total_calls}. '
                 f'Unique topics (jaccard≥{threshold}): {total_topics}.')
    lines.append('')

    # Summary
    multi_topics   = [t for t in topics if len(t.calls) > 1]
    single_topics  = [t for t in topics if len(t.calls) == 1]
    follow_up_calls = sum(len(t.calls) for t in multi_topics)
    all_colls: Dict[str, int] = defaultdict(int)
    for c in rag_calls.values():
        all_colls[c.collection] += 1
    miss_count  = sum(1 for r in results.values() if r.chunks == 0)
    trunc_count = sum(1 for r in results.values() if r.truncated)
    no_result   = total_calls - len(results)

    lines.append('## Summary')
    lines.append('')
    lines.append(f'- Single-query topics: {len(single_topics)} / Multi-query topics: {len(multi_topics)}')
    lines.append(f'- Calls in multi-query topics (follow-up rounds): {follow_up_calls} / {total_calls} '
                 f'({100*follow_up_calls//max(total_calls,1)}%)')
    lines.append(f'- Collections used: '
                 + ', '.join(f'{k} ({v})' for k, v in sorted(all_colls.items(), key=lambda x: -x[1])))
    lines.append(f'- Calls with chunk_count=0 (Miss): {miss_count}')
    lines.append(f'- Calls with truncated result (CC 5k/5k split): {trunc_count}')
    if no_result:
        lines.append(f'- Calls with no tool_result found in logs: {no_result}')
    lines.append('')

    # Topic Overview table
    lines.append('## Topic Overview')
    lines.append('')
    lines.append(f'Clustering: greedy chain-link per session, jaccard ≥ {threshold} on word tokens (stopwords excluded).')
    lines.append('')
    lines.append('| Topic | Session-Log | Queries | Follow-up? | Collections | classification (manual) |')
    lines.append('|-------|------------|---------|-----------|-------------|------------------------|')
    for t in topics:
        colls = ', '.join(sorted({c.collection for c in t.calls}))
        fu    = 'yes' if len(t.calls) > 1 else '—'
        src   = t.source.replace('opus_monitor_cc_', '')
        lines.append(f'| {t.topic_id} | `{src}` | {len(t.calls)} | {fu} | {colls} | {PLACEHOLDER} |')
    lines.append('')

    # Per-topic detail
    lines.append('## Per-Topic Detail')
    lines.append('')
    lines.append('Manual columns: **hit_quality** = Brauchbar / Zu-eng / Zu-breit / Miss. '
                 '**classification** per topic = WIN-RAG / WIN-Direct / Tie.')
    lines.append('')

    for t in topics:
        src = t.source.replace('opus_monitor_cc_', '')
        lines.append(f'### {t.topic_id} — {src}')
        if len(t.calls) > 1:
            lines.append(f'*{len(t.calls)} queries — follow-up topic*')
        lines.append('')
        lines.append('| # | Query | Collection | top-k | result_chars | chunks | truncated | hit_quality |')
        lines.append('|---|-------|-----------|-------|-------------|--------|-----------|------------|')
        for i, call in enumerate(t.calls, 1):
            ri     = results.get(call.tool_use_id)
            chars  = ri.chars    if ri else '—'
            chunks = ri.chunks   if ri else '—'
            trunc  = 'yes'       if ri and ri.truncated else '—'
            topk   = str(call.top_k) if call.top_k else 'def'
            query  = call.query.replace('|', '\\|')[:80]
            lines.append(f'| {i} | {query} | {call.collection} | {topk} | {chars} | {chunks} | {trunc} | {PLACEHOLDER} |')
        lines.append('')
        lines.append(f'**classification (manual):** {PLACEHOLDER}')
        lines.append('')

    return '\n'.join(lines) + '\n'


def _write_output(report, path):
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(path)
    else:
        sys.stdout.write(report)


# CLI entry point

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Cluster rag-cli search calls from Opus proxy logs for helpfulness eval.'
    )
    parser.add_argument(
        'proxy_jsonl', nargs='*',
        help='Proxy JSONL path(s). Default: src/logs/api_requests_opus_monitor_cc_*.jsonl'
    )
    parser.add_argument(
        '--output', default='',
        help='Output markdown file (default: auto-dated in dev/tool_use_analysis/)'
    )
    parser.add_argument(
        '--jaccard', type=float, default=0.20, metavar='T',
        help='Jaccard threshold for topic clustering (default: 0.20)'
    )
    args = parser.parse_args()

    if args.proxy_jsonl:
        paths = args.proxy_jsonl
    else:
        root  = Path(__file__).parent.parent.parent
        paths = sorted(glob.glob(str(root / 'src/logs/api_requests_opus_monitor_cc_*.jsonl')))
        if not paths:
            print('No proxy logs found under src/logs/', file=sys.stderr)
            sys.exit(1)

    out = args.output or str(
        Path(__file__).parent / f'{datetime.now().strftime("%Y%m%d")}_rag_query_audit.md'
    )

    run(paths, out, args.jaccard)
