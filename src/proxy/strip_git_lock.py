# INFRASTRUCTURE
import re

from src.proxy.strip_walk import strip_content_tree

_GIT_LOCK_MARKER = 'Another git process seems to be running'

_GIT_LOCK_ADVICE = (
    "Another git process seems to be running in this repository, e.g.\n"
    "an editor opened by 'git commit'. Please make sure all processes\n"
    "are terminated then try again. If it still fails, a git process\n"
    "may have crashed in this repository earlier:\n"
    "remove the file manually to continue."
)


# ORCHESTRATOR

def _strip_git_lock_advice(content):
    removed = []
    result = strip_content_tree(content, _strip_git_lock_from_text, removed)
    return result, removed


# FUNCTIONS

def _strip_git_lock_from_text(text, out_removed):
    if _GIT_LOCK_MARKER not in text:
        return text
    for needle in (_GIT_LOCK_ADVICE + '\n', _GIT_LOCK_ADVICE):
        if needle in text:
            out_removed.append(needle.rstrip('\n'))
            return text.replace(needle, '', 1)
    return text
