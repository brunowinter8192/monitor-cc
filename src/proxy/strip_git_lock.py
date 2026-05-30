import re

# INFRASTRUCTURE

# Fast-path marker — cheap contains check before literal match
_GIT_LOCK_MARKER = 'Another git process seems to be running'

# Exact 5-line git advice block — hardcoded in git's lockfile.c, constant across all repos/versions.
# Strip this block only; the variable 'Warning: auto-export: ...' line above it is preserved.
_GIT_LOCK_ADVICE = (
    "Another git process seems to be running in this repository, e.g.\n"
    "an editor opened by 'git commit'. Please make sure all processes\n"
    "are terminated then try again. If it still fails, a git process\n"
    "may have crashed in this repository earlier:\n"
    "remove the file manually to continue."
)


# ORCHESTRATOR

# Strip git index.lock advice block from all 4 content shapes.
# Returns (new_content, removed_chunks) — removed_chunks is a list of stripped block strings,
# one per match, for stripped_git_lock_advice mod attribution via attribute_chunk.
def _strip_git_lock_advice(content):
    removed = []
    if isinstance(content, str):
        return _strip_git_lock_from_text(content, removed), removed
    if isinstance(content, list):
        result = []
        for block in content:
            if not isinstance(block, dict):
                result.append(block)
                continue
            btype = block.get('type')
            if btype == 'text':
                new_text = _strip_git_lock_from_text(block.get('text', ''), removed)
                result.append({**block, 'text': new_text} if new_text != block.get('text', '') else block)
            elif btype == 'tool_result':
                inner = block.get('content', '')
                if isinstance(inner, str):
                    new_inner = _strip_git_lock_from_text(inner, removed)
                    result.append({**block, 'content': new_inner} if new_inner != inner else block)
                elif isinstance(inner, list):
                    new_sub = []
                    for sub in inner:
                        if isinstance(sub, dict) and sub.get('type') == 'text':
                            new_text = _strip_git_lock_from_text(sub.get('text', ''), removed)
                            new_sub.append({**sub, 'text': new_text} if new_text != sub.get('text', '') else sub)
                        else:
                            new_sub.append(sub)
                    result.append({**block, 'content': new_sub})
                else:
                    result.append(block)
            else:
                result.append(block)
        return result, removed
    return content, removed


# FUNCTIONS

# Strip git lock advice block from a single string; append removed block(s) to out_removed.
# Tries with trailing newline first (standard git output), then without (edge case).
def _strip_git_lock_from_text(text, out_removed):
    if _GIT_LOCK_MARKER not in text:
        return text
    for needle in (_GIT_LOCK_ADVICE + '\n', _GIT_LOCK_ADVICE):
        if needle in text:
            out_removed.append(needle.rstrip('\n'))
            return text.replace(needle, '', 1)
    return text
