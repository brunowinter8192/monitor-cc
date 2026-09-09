# INFRASTRUCTURE
import datetime
import json
import os
import re
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

_RAG_RE = re.compile(r'\brag-cli\s+(index|delete)\b')

_SEGMENT_END_RE = re.compile(r'&&|\|\||[;)\n]|(?<!>)&(?![&>])')
_NOISE_RE = re.compile(r'2>&1|2>|&>|>>|<<|>|<|(?<!\|)\|(?!\|)')

_WINDOW_SECS = 600
_THRESHOLD = 2

_STATE_FILE = os.environ.get(
    "MONITOR_CC_RAG_DOC_REPEAT_STATE",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'logs', 'rag_doc_repeat_state.jsonl',
    ),
)

_BLOCK_MESSAGE_TEMPLATE = (
    "Repeated single-document `rag-cli {subcommand} --collection {collection} --document ...` "
    "calls detected — this is the 2nd such call to this collection within 10 minutes, the "
    "opening move of a per-file loop (an observed incident issued ~40/~48 of these instead "
    "of one call). Use the collection-wide form instead: "
    "`rag-cli {subcommand} --collection {collection}` (no --document). A single one-off "
    "--document call remains fine; it's the repeat that is blocked.\n"
)


# ORCHESTRATOR

def block_rag_cli_document_repeat_workflow() -> None:
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    matches = list(_RAG_RE.finditer(stripped))
    if not matches:
        sys.exit(0)
    for m in matches:
        subcommand = m.group(1)
        seg_end = _segment_end(stripped, m.end())
        original_segment = command[m.start():seg_end]
        target = _extract_target(subcommand, original_segment)
        if target is None:
            continue
        count = _record_and_count(session_id or "", target)
        if count >= _THRESHOLD:
            _block(command, session_id, target)
    sys.exit(0)


# FUNCTIONS

def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return (cmd if isinstance(cmd, str) else None), payload.get("session_id")
    except Exception:
        return None, None


def _segment_end(stripped: str, rag_end: int) -> int:
    end_m = _SEGMENT_END_RE.search(stripped, rag_end)
    seg_end = end_m.start() if end_m else len(stripped)
    noise_m = _NOISE_RE.search(stripped, rag_end, seg_end)
    if noise_m is not None:
        seg_end = min(seg_end, noise_m.start())
    return seg_end


def _extract_target(subcommand: str, original_segment: str):
    try:
        tokens = shlex.split(original_segment)
    except ValueError:
        return None
    collection = _find_flag_value(tokens, '--collection')
    if collection is None:
        return None
    if _find_flag_value(tokens, '--document') is None:
        return None
    return f"{subcommand}:{collection}"


def _find_flag_value(tokens: list, flag: str):
    for i, tok in enumerate(tokens):
        if tok == flag and i + 1 < len(tokens):
            return tokens[i + 1]
        if tok.startswith(flag + '='):
            return tok.split('=', 1)[1]
    return None


def _record_and_count(session_id: str, target: str) -> int:
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        cutoff = now - datetime.timedelta(seconds=_WINDOW_SECS)
        entries = _read_recent_entries(cutoff)
        entries.append({
            'ts': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'session_id': session_id,
            'target': target,
        })
        _write_entries(entries)
        return sum(
            1 for e in entries
            if e.get('session_id') == session_id and e.get('target') == target
        )
    except Exception:
        return 0


def _read_recent_entries(cutoff: datetime.datetime) -> list:
    if not os.path.exists(_STATE_FILE):
        return []
    entries = []
    try:
        with open(_STATE_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    ts = datetime.datetime.fromisoformat(entry.get('ts', '').replace('Z', '+00:00'))
                    if ts >= cutoff:
                        entries.append(entry)
                except Exception:
                    continue
    except Exception:
        return []
    return entries


def _write_entries(entries: list) -> None:
    try:
        os.makedirs(os.path.dirname(_STATE_FILE), exist_ok=True)
        with open(_STATE_FILE, 'w', encoding='utf-8') as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception:
        return


def _block(command: str, session_id: str, target: str) -> None:
    subcommand, collection = target.split(':', 1)
    message = _BLOCK_MESSAGE_TEMPLATE.format(subcommand=subcommand, collection=collection)
    print(message, file=sys.stderr, end="")
    log_fire("block_rag_cli_document_repeat", "block", "Bash", command,
              reason=message, session_id=session_id)
    sys.exit(2)


if __name__ == "__main__":
    block_rag_cli_document_repeat_workflow()
