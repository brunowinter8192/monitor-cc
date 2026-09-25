# INFRASTRUCTURE
import re

from src.proxy.strip_walk import strip_content_tree

_HOOK_PREFIX_MARKER = 'PreToolUse:'

_HOOK_PREFIX_RE = re.compile(
    r'^PreToolUse:\w+ hook error: \[python3 [^\]]+\]:\s*',
    re.MULTILINE,
)


# ORCHESTRATOR

def _strip_hook_prefix(content):
    removed = []
    result = strip_content_tree(content, _strip_from_text, removed)
    return result, removed


# FUNCTIONS

def _strip_from_text(text, out_removed):
    if _HOOK_PREFIX_MARKER not in text:
        return text

    def _replace(m):
        out_removed.append(m.group(0).rstrip())
        return ''

    return _HOOK_PREFIX_RE.sub(_replace, text, count=1)
