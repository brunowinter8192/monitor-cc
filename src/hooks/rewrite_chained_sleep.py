# INFRASTRUCTURE
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

_SLEEP_RE = re.compile(r'\bsleep\s+\d+(?:\.\d+)?\b')
_CHAIN_RE = re.compile(r';|&&|\|\|')
_LOOP_RE  = re.compile(r'\b(for|while|until)\b')
_DONE_RE  = re.compile(r'\bdone\b')
_TRIVIAL  = frozenset({'echo', 'true', 'grep', 'cat', 'ls', 'wc', 'head', 'tail', 'find'})
_TRIVIAL_PAIRS = frozenset({
    ('git',        'status'),
    ('git',        'log'),
    ('git',        'diff'),
    ('git',        'show'),
    ('rag-cli',    'search_hybrid'),
    ('worker-cli', 'status'),
    ('worker-cli', 'list'),
    ('worker-cli', 'response'),
})


# ORCHESTRATOR

# Read Bash tool_input from stdin; strip trivial-sync sleeps; emit allow+updatedInput if any stripped
def rewrite_chained_sleep_workflow() -> None:
    command, run_in_background, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    if not _SLEEP_RE.search(stripped):
        sys.exit(0)
    ranges = _find_strip_ranges(command, stripped)
    if not ranges:
        sys.exit(0)
    rewritten = _apply_ranges(command, ranges)
    if rewritten == command:
        sys.exit(0)
    output = _emit_rewrite(rewritten, run_in_background)
    log_fire("rewrite_chained_sleep", "rewrite", "Bash", command, rewritten=rewritten, session_id=session_id)
    print(json.dumps(output))
    sys.exit(0)


# FUNCTIONS

# Parse stdin JSON; return (command, session_id); (None, None) on any error (fail-open)
def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        ti  = payload.get("tool_input", {})
        cmd = ti.get("command")
        bg  = ti.get("run_in_background", False)
        return (cmd if isinstance(cmd, str) else None), (bg if isinstance(bg, bool) else False), payload.get("session_id")
    except Exception:
        return None, False, None

# Return list of (start, end) spans in command to remove (trivial-sync sleep + preceding chain op)
def _find_strip_ranges(command: str, stripped: str) -> list:
    ops    = list(_CHAIN_RE.finditer(stripped))
    ranges = []

    for sleep_m in _SLEEP_RE.finditer(stripped):
        s_start = sleep_m.start()
        s_end   = sleep_m.end()

        # Find the chain op immediately before this sleep (only whitespace between op and sleep)
        prec = None
        for op in reversed(ops):
            if op.end() <= s_start and not stripped[op.end():s_start].strip():
                prec = op
                break
        if prec is None:
            continue  # sleep-first chain — intent is timing, not sync; do not strip

        # cmd_before: first token of the segment immediately preceding prec
        seg_start = 0
        for op in reversed(ops):
            if op.end() <= prec.start():
                seg_start = op.end()
                break
        seg = stripped[seg_start:prec.start()].strip()
        if not seg:
            continue
        tokens = seg.split()
        if tokens[0] not in _TRIVIAL and not (len(tokens) >= 2 and (tokens[0], tokens[1]) in _TRIVIAL_PAIRS):
            continue

        # Skip when sleep is inside a loop body
        if _in_loop(stripped, s_start):
            continue

        # Removal span: preceding op through end of sleep (+ trailing whitespace)
        r_end = s_end
        while r_end < len(command) and command[r_end] in ' \t':
            r_end += 1
        ranges.append((prec.start(), r_end))

    return ranges

# True if pos falls inside a for/while/until...done span in stripped
def _in_loop(stripped: str, pos: int) -> bool:
    for lm in _LOOP_RE.finditer(stripped):
        if lm.start() > pos:
            break
        dm = _DONE_RE.search(stripped, lm.start())
        if dm and lm.start() < pos < dm.end():
            return True
    return False

# Remove non-overlapping (merged) ranges from command and return result
def _apply_ranges(command: str, ranges: list) -> str:
    merged: list = []
    for s, e in sorted(ranges):
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    parts, pos = [], 0
    for s, e in merged:
        parts.append(command[pos:s])
        pos = e
    parts.append(command[pos:])
    return ''.join(parts)

# Build allow+updatedInput dict; return it (caller handles print)
def _emit_rewrite(rewritten: str, run_in_background: bool) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": {"command": rewritten, "run_in_background": run_in_background},
        },
    }


if __name__ == "__main__":
    rewrite_chained_sleep_workflow()
