#!/usr/bin/env python3
"""Proxy JSONL forensic primitives — load, extract, filter, aggregate. No I/O side effects."""

# INFRASTRUCTURE
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator, Optional

CHAR_BUCKETS = [
    (500, 999, '500–999'),
    (1000, 1999, '1000–1999'),
    (2000, 4999, '2000–4999'),
    (5000, 9999, '5000–9999'),
    (10000, None, '10000+'),
]
PREFIX_EXAMPLE_CHARS = 200


# DATACLASSES

@dataclass(slots=True, frozen=True)
class ToolUse:
    id: str
    name: str
    input: dict
    session_file: str
    timestamp: str

    @property
    def input_chars(self) -> int:
        return len(json.dumps(self.input))

    @property
    def field_chars(self) -> dict:
        return {k: len(json.dumps(v)) for k, v in self.input.items()}


@dataclass(slots=True, frozen=True)
class ToolResult:
    tool_use_id: str
    content: object
    is_error: bool

    @property
    def output_chars(self) -> int:
        return len(json.dumps(self.content))


@dataclass(slots=True, frozen=True)
class Pair:
    tu: ToolUse
    tr: ToolResult

    @property
    def ratio(self) -> float:
        return self.tu.input_chars / max(self.tr.output_chars, 1)


@dataclass(slots=True, frozen=True)
class ToolStats:
    name: str
    count: int
    total_input: int
    total_output: int
    mean_ratio: float
    median_ratio: float
    max_ratio: float


@dataclass(slots=True)
class PrefixBucket:
    prefix: str
    tags: str
    count: int
    total_chars: int
    max_chars: int
    example: str

    @property
    def mean_chars(self) -> int:
        return self.total_chars // self.count


# FUNCTIONS

def load_proxy(paths: list) -> list:
    """Load events from one or more proxy JSONL paths; skip raw_payload == null entries.

    Each event is tagged with _session_file (basename of its source path)
    for downstream use in tool_use_blocks().
    """
    events = []
    for path in paths:
        session_file = os.path.basename(path)
        with open(path, 'r', encoding='utf-8') as f:
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
                d['_session_file'] = session_file
                events.append(d)
    return events


def tool_use_blocks(events: list) -> Iterator:
    """Yield deduplicated ToolUse objects (first occurrence of each id wins)."""
    seen = set()
    for event in events:
        ts = event.get('timestamp', '')
        session_file = event.get('_session_file', '')
        messages = event.get('raw_payload', {}).get('messages', [])
        for msg in messages:
            content = msg.get('content', [])
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get('type') != 'tool_use':
                    continue
                bid = block.get('id')
                if not bid or bid in seen:
                    continue
                seen.add(bid)
                yield ToolUse(
                    id=bid,
                    name=block.get('name', ''),
                    input=block.get('input', {}),
                    session_file=session_file,
                    timestamp=ts,
                )


def tool_result_blocks(events: list) -> dict:
    """Map tool_use_id -> first ToolResult found across all events."""
    seen = {}
    for event in events:
        messages = event.get('raw_payload', {}).get('messages', [])
        for msg in messages:
            content = msg.get('content', [])
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get('type') != 'tool_result':
                    continue
                tid = block.get('tool_use_id')
                if tid and tid not in seen:
                    seen[tid] = ToolResult(
                        tool_use_id=tid,
                        content=block.get('content', ''),
                        is_error=bool(block.get('is_error', False)),
                    )
    return seen


def pairs(events: list) -> Iterator:
    """Yield matched Pair(ToolUse, ToolResult); skips tool_uses with no result."""
    results = tool_result_blocks(events)
    for tu in tool_use_blocks(events):
        tr = results.get(tu.id)
        if tr is not None:
            yield Pair(tu=tu, tr=tr)


def filter_by(items: Iterator, tool: Optional[str] = None,
              min_input_chars: Optional[int] = None,
              max_input_chars: Optional[int] = None,
              ratio_gt: Optional[float] = None,
              ratio_lt: Optional[float] = None,
              name_contains: Optional[str] = None,
              exclude_tools: Optional[list] = None) -> Iterator:
    """Filter ToolUse or Pair items by common predicates.

    exclude_tools uses substring matching: pass 'worker_send' to exclude
    mcp__plugin_iterative-dev_iterative-dev__worker_send without the full name.
    ratio_gt / ratio_lt only apply to Pair items; silently ignored for ToolUse.
    """
    for item in items:
        tu = item.tu if isinstance(item, Pair) else item
        if tool is not None and tu.name != tool:
            continue
        if name_contains is not None and name_contains not in tu.name:
            continue
        if exclude_tools is not None and any(ex in tu.name for ex in exclude_tools):
            continue
        if min_input_chars is not None and tu.input_chars < min_input_chars:
            continue
        if max_input_chars is not None and tu.input_chars > max_input_chars:
            continue
        if isinstance(item, Pair):
            if ratio_gt is not None and item.ratio <= ratio_gt:
                continue
            if ratio_lt is not None and item.ratio >= ratio_lt:
                continue
        yield item


def aggregate_by_tool(pair_iter: Iterator) -> dict:
    """Per-tool stats from Pair iterator. Returns dict[name, ToolStats]."""
    by_tool = {}
    for p in pair_iter:
        name = p.tu.name
        if name not in by_tool:
            by_tool[name] = {'count': 0, 'total_input': 0, 'total_output': 0,
                             'ratios': [], 'max_ratio': 0.0}
        s = by_tool[name]
        s['count'] += 1
        s['total_input'] += p.tu.input_chars
        s['total_output'] += p.tr.output_chars
        s['ratios'].append(p.ratio)
        s['max_ratio'] = max(s['max_ratio'], p.ratio)

    result = {}
    for name, s in by_tool.items():
        ratios = sorted(s['ratios'])
        mean_r = sum(ratios) / len(ratios)
        median_r = ratios[len(ratios) // 2]
        result[name] = ToolStats(
            name=name,
            count=s['count'],
            total_input=s['total_input'],
            total_output=s['total_output'],
            mean_ratio=mean_r,
            median_ratio=median_r,
            max_ratio=s['max_ratio'],
        )
    return result


def aggregate_by_prefix(bash_uses: Iterator) -> list:
    """Cluster Bash ToolUse items by command prefix. Returns list[PrefixBucket] sorted by total_chars desc."""
    clusters = {}
    for tu in bash_uses:
        cmd = tu.input.get('command', '')
        prefix, tags = extract_prefix(cmd)
        tag_str = ' '.join(tags)
        key = f'{prefix}\x00{tag_str}'
        if key not in clusters:
            example = cmd[:PREFIX_EXAMPLE_CHARS].replace('\n', ' ')
            clusters[key] = PrefixBucket(
                prefix=prefix, tags=tag_str, count=0,
                total_chars=0, max_chars=0, example=example,
            )
        b = clusters[key]
        b.count += 1
        b.total_chars += tu.input_chars
        b.max_chars = max(b.max_chars, tu.input_chars)
    return sorted(clusters.values(), key=lambda x: -x.total_chars)


def extract_prefix(command_str: str) -> tuple:
    """Extract command prefix and tags from a Bash command string.

    Returns (prefix: str, tags: list[str]).
    Tags: [heredoc], [abs-venv], [sourced-fn].
    """
    tags = []

    if '<<' in command_str:
        tags.append('[heredoc]')

    tokens = None
    for line in command_str.split('\n'):
        line = line.strip()
        if not line:
            continue
        line_tokens = line.split()
        while line_tokens and re.match(r'^[A-Z_][A-Z0-9_]*=', line_tokens[0]):
            line_tokens.pop(0)
        while line_tokens and line_tokens[0] in ('&&', '||', ';'):
            line_tokens.pop(0)
        if not line_tokens:
            continue
        if line_tokens[0].startswith('#'):
            continue
        tokens = line_tokens
        break

    if not tokens:
        return ('(empty)', tags)

    first = tokens[0]

    while first == 'cd' and len(tokens) >= 3 and tokens[2] == '&&':
        tokens = tokens[3:]
        if not tokens:
            return ('(empty)', tags)
        first = tokens[0]

    if '/' in first and re.search(r'python3?$', first):
        tags.append('[abs-venv]')
        return ('python', tags)

    if first == 'source':
        rest = ' '.join(tokens[1:])
        if '&&' in rest:
            fn_tokens = rest.split('&&', 1)[1].strip().split()
            if fn_tokens:
                tags.append('[sourced-fn]')
                return (fn_tokens[0], tags)

    if first.startswith('~') or first.startswith('/'):
        basename = first.rstrip('/').split('/')[-1]
        return (basename, tags)

    return (first, tags)


def bucket_distribution(items: Iterator) -> list:
    """Count ToolUse or Pair items per input char-bucket. Returns list[(label, count)] in bucket order."""
    counts = {label: 0 for _, _, label in CHAR_BUCKETS}
    for item in items:
        ic = item.input_chars if isinstance(item, ToolUse) else item.tu.input_chars
        for lo, hi, label in CHAR_BUCKETS:
            if hi is None and ic >= lo:
                counts[label] += 1
                break
            elif hi is not None and lo <= ic <= hi:
                counts[label] += 1
                break
    return [(label, counts[label]) for _, _, label in CHAR_BUCKETS]


def format_timestamp_local(ts_str: str) -> str:
    """Convert UTC ISO timestamp string to local HH:MM:SS."""
    if not ts_str:
        return '?'
    try:
        dt_utc = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        return dt_utc.astimezone().strftime('%H:%M:%S')
    except Exception:
        return ts_str[:19]
