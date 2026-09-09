# INFRASTRUCTURE
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire
from _known_cli import resolve_cli_segment, is_protected_segment, tool_sub_name

_CHAIN_SEPARATOR_RE = re.compile(r'&&|\|\||;|\n|\s&(?=\s|$)')
_PIPE_SEPARATOR_RE = re.compile(r'\|')
_REDIRECT_RE = re.compile(r'>>|2>&1|&>|(?<![0-9])>(?!>)|<(?!<)')
_REDIRECT_TARGET_RE = re.compile(r'(?:>>|&>|(?<![0-9])>(?!>))\s*([^\s;&|<>]+)')
_READBACK_TOOLS = {"head", "tail", "cat", "sed", "awk", "grep", "less", "more", "wc"}
_FIRST_TOKEN_RE = re.compile(r'^(\S+)')

_RULE1_MESSAGE = (
    "Chaining CLIs with ; or && is fine; piping a CLI's output into another command is not.\n"
    "Blocked segment: {segment}\n"
)
_RULE2_MESSAGE = (
    "Chaining CLIs with ; or && is fine; redirecting {tool_sub} to a file is not, "
    "its output belongs in context.\n"
    "Blocked segment: {segment}\n"
)
_RULE3_MESSAGE = (
    "Chaining CLIs with ; or && is fine; reading a CLI's redirected file back with "
    "head/tail/cat in the same call is not.\n"
    "Blocked segment: {segment}\n"
)


# ORCHESTRATOR

def block_cli_chained_workflow() -> None:
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    chain_segments = _build_chain_segments(stripped, command)
    if not any(_segment_stages_with_cli(seg, stripped) for seg in chain_segments):
        sys.exit(0)

    _check_rule1_pipe(chain_segments, stripped, command, session_id)
    _check_rule2_redirect(chain_segments, stripped, command, session_id)
    _check_rule3_readback(chain_segments, stripped, command, session_id)
    sys.exit(0)


# FUNCTIONS

def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return (cmd if isinstance(cmd, str) else None), payload.get("session_id")
    except Exception:
        return None, None

def _split_spans(text: str, sep_re) -> list:
    spans = []
    pos = 0
    for m in sep_re.finditer(text):
        spans.append((pos, m.start()))
        pos = m.end()
    spans.append((pos, len(text)))
    return spans

def _trim_span(text: str, s: int, e: int) -> tuple:
    while s < e and text[s].isspace():
        s += 1
    while e > s and text[e - 1].isspace():
        e -= 1
    return s, e

def _build_chain_segments(stripped: str, original: str) -> list:
    segments = []
    for s, e in _split_spans(stripped, _CHAIN_SEPARATOR_RE):
        s, e = _trim_span(stripped, s, e)
        if s >= e:
            continue
        chain_stripped = stripped[s:e]
        chain_original = original[s:e]
        stage_spans = []
        for ss, se in _split_spans(chain_stripped, _PIPE_SEPARATOR_RE):
            ss, se = _trim_span(chain_stripped, ss, se)
            if ss < se:
                stage_spans.append((ss, se))
        segments.append({
            'stripped': chain_stripped,
            'original': chain_original,
            'stage_spans': stage_spans,
        })
    return segments

def _segment_stages_with_cli(segment: dict, command_context: str) -> bool:
    for s, e in segment['stage_spans']:
        if resolve_cli_segment(segment['stripped'][s:e], command_context) is not None:
            return True
    return False

def _check_rule1_pipe(chain_segments: list, command_context: str, command: str, session_id) -> None:
    for segment in chain_segments:
        stages = segment['stage_spans']
        for i, (s, e) in enumerate(stages[:-1]):
            stage_stripped = segment['stripped'][s:e]
            if resolve_cli_segment(stage_stripped, command_context) is not None:
                blocked = segment['original'].strip()
                _block(_RULE1_MESSAGE.format(segment=blocked), command, session_id)

def _check_rule2_redirect(chain_segments: list, command_context: str, command: str, session_id) -> None:
    for segment in chain_segments:
        stages = segment['stage_spans']
        if not stages:
            continue
        s, e = stages[-1]
        stage_stripped = segment['stripped'][s:e]
        match = resolve_cli_segment(stage_stripped, command_context)
        if not is_protected_segment(match):
            continue
        if _REDIRECT_RE.search(stage_stripped):
            blocked = segment['original'][s:e].strip()
            tool_sub = tool_sub_name(match.group('tool'), match.group('sub'))
            _block(_RULE2_MESSAGE.format(tool_sub=tool_sub, segment=blocked), command, session_id)

def _check_rule3_readback(chain_segments: list, command_context: str, command: str, session_id) -> None:
    redirected_files = set()
    for segment in chain_segments:
        stages = segment['stage_spans']
        if not stages:
            continue
        s, e = stages[-1]
        stage_stripped = segment['stripped'][s:e]
        if resolve_cli_segment(stage_stripped, command_context) is None:
            continue
        target_match = _REDIRECT_TARGET_RE.search(stage_stripped)
        if target_match:
            redirected_files.add(target_match.group(1).strip('\'"'))
    if not redirected_files:
        return
    for segment in chain_segments:
        for s, e in segment['stage_spans']:
            stage_stripped = segment['stripped'][s:e]
            first_token = _first_token(stage_stripped)
            if os.path.basename(first_token) not in _READBACK_TOOLS:
                continue
            stage_original = segment['original'][s:e]
            for target in redirected_files:
                if target in stage_original:
                    blocked = stage_original.strip()
                    _block(_RULE3_MESSAGE.format(segment=blocked), command, session_id)

def _first_token(text: str) -> str:
    m = _FIRST_TOKEN_RE.match(text)
    return m.group(1) if m else ""

def _block(message: str, command: str, session_id) -> None:
    print(message, file=sys.stderr, end="")
    log_fire("block_cli_chained", "block", "Bash", command,
             reason=message, session_id=session_id)
    sys.exit(2)


if __name__ == "__main__":
    block_cli_chained_workflow()
