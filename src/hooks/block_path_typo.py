# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fire_log import log_fire

# Two typo classes from Rule 13 (tool-use.md):
#   `.claire/`  — tokenizer typo of `.claude/`
#   `..letter`  — double-dot immediately followed by lowercase letter (in path context)
_CLAIRE_PATTERN = re.compile(r'\.claire/')
_DOTDOT_PATTERN = re.compile(r'(?:^|/|\s|=)\.\.[a-z]')
# Rewrite: capture (prefix-char | ^) + .. + letter; replace with same + ../ + letter
_DOTDOT_FIX_RE  = re.compile(r'(^|[/\s=])(\.\.)([a-z])', re.MULTILINE)


# ORCHESTRATOR

# Read tool_input from stdin; rewrite path typos via updatedInput; exit 0 always (fail-open rewriter)
def rewrite_path_typo_workflow() -> None:
    parsed = _parse_payload()
    if parsed is None:
        sys.exit(0)
    tool_name, inp, target, session_id = parsed
    stripped = _strip_quoted(target)
    has_claire = bool(_CLAIRE_PATTERN.search(stripped))
    has_dotdot = bool(_DOTDOT_PATTERN.search(stripped))
    if not (has_claire or has_dotdot):
        sys.exit(0)
    rewritten = _rewrite_typos(target, has_claire, has_dotdot)
    output = _emit_rewrite(tool_name, inp, target, rewritten, has_claire, has_dotdot)
    log_fire("block_path_typo", "rewrite", tool_name, target, rewritten=rewritten, session_id=session_id)
    print(json.dumps(output))
    sys.exit(0)


# FUNCTIONS

# Parse stdin JSON; return (tool_name, inp, target_str, session_id) or None on any error (fail-open)
def _parse_payload():
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        return None
    tool_name = payload.get("tool_name", "")
    inp = payload.get("tool_input", {})
    sid = payload.get("session_id")
    if tool_name == "Bash":
        cmd = inp.get("command")
        return (tool_name, inp, cmd, sid) if isinstance(cmd, str) else None
    if tool_name in ("Read", "Write", "Edit"):
        fp = inp.get("file_path")
        return (tool_name, inp, fp, sid) if isinstance(fp, str) else None
    return None

# Apply claire and dotdot rewrites to the original (unstripped) string
def _rewrite_typos(s: str, has_claire: bool, has_dotdot: bool) -> str:
    if has_claire:
        s = s.replace('.claire/', '.claude/')
    if has_dotdot:
        s = _DOTDOT_FIX_RE.sub(r'\1\2/\3', s)
    return s

# Build updatedInput for the tool; Edit carries all four fields per CC hook spec
def _build_updated_input(tool_name: str, inp: dict, rewritten: str) -> dict:
    if tool_name == "Bash":
        return {"command": rewritten}
    if tool_name == "Edit":
        return {
            "file_path":  rewritten,
            "old_string":  inp.get("old_string",  ""),
            "new_string":  inp.get("new_string",  ""),
            "replace_all": inp.get("replace_all", False),
        }
    return {"file_path": rewritten}  # Read, Write

# Build hookSpecificOutput + systemMessage dict; return it (caller handles print)
def _emit_rewrite(tool_name: str, inp: dict, original: str, rewritten: str,
                  has_claire: bool, has_dotdot: bool) -> dict:
    parts = []
    if has_claire:
        parts.append("`.claire/` → `.claude/`")
    if has_dotdot:
        parts.append("`..<letter>` → `../<letter>`")
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": _build_updated_input(tool_name, inp, rewritten),
        },
        "systemMessage": (
            f"Hook rewrote path typo: {' and '.join(parts)}. "
            f"Original: `{original}`. Rewritten: `{rewritten}`."
        ),
    }

# Strip content inside single/double quotes so quoted regex/text cannot trigger pattern matches.
# Not a full shell parser — handles balanced quotes with simple backslash-escape.
def _strip_quoted(s: str) -> str:
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c in ("'", '"'):
            quote, i = c, i + 1
            while i < n and s[i] != quote:
                if s[i] == "\\" and i + 1 < n:
                    i += 2
                else:
                    i += 1
            i += 1   # skip closing quote (or step past end if unbalanced)
        else:
            out.append(c)
            i += 1
    return "".join(out)


if __name__ == "__main__":
    rewrite_path_typo_workflow()
