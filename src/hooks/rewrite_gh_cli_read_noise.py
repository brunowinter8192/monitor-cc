# INFRASTRUCTURE
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shell_strip import _strip_non_shell_active
from _fire_log import log_fire

# Anchor: only `gh-cli get_issue` / `gh-cli list_issues` — READ commands where a truncating
# pipe means missing sources/context. `create_issue`/`update_issue` are writes with a one-line
# confirmation, no truncation risk, and intentionally out of scope.
_GH_CLI_RE = re.compile(r'\bgh-cli\s+(?:get_issue|list_issues)\b')

# Segment-end operators: terminate the gh-cli logical command.
# `(?<!>)&(?![&>])` matches a single backgrounding `&` but NOT `&&` (chain),
# `&>` (redirect), or `&` inside `2>&1` (redirect — `&` preceded by `>`).
_SEGMENT_END_RE = re.compile(r'&&|\|\||[;)\n]|(?<!>)&(?![&>])')

# Noise inside the segment: PIPES ONLY (excluding `||`).
# Redirects (`>`, `>>`, `&>`, `<`, `2>&1`) are LEGITIMATE — e.g.
# `gh-cli get_issue owner repo 36 > /tmp/file` saves the full output to disk. Do NOT strip them.
_NOISE_RE = re.compile(r'(?<!\|)\|(?!\|)')


# ORCHESTRATOR

# Read Bash tool_input from stdin; for each `gh-cli get_issue`/`gh-cli list_issues` invocation,
# strip any downstream pipes inside its logical segment.
# Redirects and chains around the segment are preserved.
def rewrite_gh_cli_read_noise_workflow() -> None:
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_non_shell_active(command)
    matches = list(_GH_CLI_RE.finditer(stripped))
    if not matches:
        sys.exit(0)

    ranges = []
    for m in matches:
        gh_end = m.end()
        end_m = _SEGMENT_END_RE.search(stripped, gh_end)
        seg_end = end_m.start() if end_m else len(stripped)
        noise_m = _NOISE_RE.search(stripped, gh_end, seg_end)
        if noise_m is None:
            continue
        # Strip from the noise marker to segment end.
        # Eat the leading whitespace only when the segment extends to end-of-command —
        # otherwise the space serves as separator to the trailing chain (`; echo done`).
        strip_start = noise_m.start()
        if seg_end == len(stripped):
            while strip_start > gh_end and command[strip_start - 1] in ' \t':
                strip_start -= 1
        ranges.append((strip_start, seg_end))

    if not ranges:
        sys.exit(0)

    rewritten = _apply_ranges(command, ranges)
    if rewritten == command:
        sys.exit(0)
    output = _emit_rewrite(rewritten)
    log_fire("rewrite_gh_cli_read_noise", "rewrite", "Bash", command,
             rewritten=rewritten, session_id=session_id)
    print(json.dumps(output))
    sys.exit(0)


# FUNCTIONS

# Parse stdin JSON; return (command, session_id); (None, None) on any error (fail-open)
def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return (cmd if isinstance(cmd, str) else None), payload.get("session_id")
    except Exception:
        return None, None

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
def _emit_rewrite(rewritten: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": {"command": rewritten},
        },
    }


if __name__ == "__main__":
    rewrite_gh_cli_read_noise_workflow()
