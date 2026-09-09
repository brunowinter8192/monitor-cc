# INFRASTRUCTURE
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

_CORPUS_PATH_RE = re.compile(r'(?:^|/)rag-[^/\s]*/data/documents(?=[/\s\'")]|$)')
_CORPUS_ANCHOR = 'data/documents'
_READ_COMMANDS = ("cat", "grep", "head", "tail", "sed", "awk", "rg", "less", "more")
_ASSIGN_TOKEN = r'[A-Za-z_][A-Za-z0-9_]*=\S*'
_ASSIGN_PREFIX = rf'(?:{_ASSIGN_TOKEN}\s+)*'
_READ_CMD_RE = re.compile(rf'^{_ASSIGN_PREFIX}(?:{"|".join(_READ_COMMANDS)})\b')
_SEPARATOR_RE = re.compile(r'&&|\|\||;|\n|\||\s&(?=\s|$)')

_BLOCK_MESSAGE = (
    "Reading rag-cli's document corpus directly (cat/grep/head/tail/sed/awk/rg/less/more on a "
    "rag-*/data/documents path) bypasses ranking/formatting and returns raw chunk-store files, "
    "not search results. Use `rag-cli search <query> <collection>` to find relevant chunks, or "
    "`rag-cli read_document <collection> <doc_id>` (add --before N/--after N for context) to "
    "read a specific document. File management (ls, rm, mv, mkdir) on the corpus stays allowed.\n"
)


# ORCHESTRATOR

def block_rag_corpus_read_workflow() -> None:
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    if _CORPUS_ANCHOR not in command:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    for stripped_seg, original_seg in _split_segments(stripped, command):
        if not _READ_CMD_RE.match(stripped_seg):
            continue
        if _CORPUS_PATH_RE.search(original_seg):
            _block(command, session_id)
    sys.exit(0)


# FUNCTIONS

def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return (cmd if isinstance(cmd, str) else None), payload.get("session_id")
    except Exception:
        return None, None


def _split_segments(stripped: str, original: str) -> list:
    pairs = []
    pos = 0
    for m in _SEPARATOR_RE.finditer(stripped):
        pairs.append(_trim_pair(stripped[pos:m.start()], original[pos:m.start()]))
        pos = m.end()
    pairs.append(_trim_pair(stripped[pos:], original[pos:]))
    return [p for p in pairs if p[0].strip()]


def _trim_pair(stripped_seg: str, original_seg: str) -> tuple:
    left = len(original_seg) - len(original_seg.lstrip())
    right = len(original_seg) - len(original_seg.rstrip())
    end = len(original_seg) - right
    return stripped_seg[left:end], original_seg[left:end]


def _block(command: str, session_id) -> None:
    print(_BLOCK_MESSAGE, file=sys.stderr, end="")
    log_fire("block_rag_corpus_read", "block", "Bash", command,
             reason=_BLOCK_MESSAGE, session_id=session_id)
    sys.exit(2)


if __name__ == "__main__":
    block_rag_corpus_read_workflow()
