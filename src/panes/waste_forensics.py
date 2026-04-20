import json
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator


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


def tool_use_blocks(events: list) -> Iterator:
    """Yield deduplicated ToolUse objects (first occurrence of each id wins)."""
    seen: set = set()
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
    seen: dict = {}
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


def format_timestamp_local(ts_str: str) -> str:
    """Convert UTC ISO timestamp string to local HH:MM:SS."""
    if not ts_str:
        return '?'
    try:
        dt_utc = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        return dt_utc.astimezone().strftime('%H:%M:%S')
    except Exception:
        return ts_str[:19]
