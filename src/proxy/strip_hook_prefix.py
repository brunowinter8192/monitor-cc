import re

# INFRASTRUCTURE

# Fast-path marker — cheap contains check before regex
_HOOK_PREFIX_MARKER = 'PreToolUse:'

# Match CC's hook-error wrapper line: PreToolUse:<Tool> hook error: [python3 <path>]: <msg>
# re.MULTILINE so ^ anchors at line start; count=1 strips only the first occurrence per block.
_HOOK_PREFIX_RE = re.compile(
    r'^PreToolUse:\w+ hook error: \[python3 [^\]]+\]:\s*',
    re.MULTILINE,
)


# ORCHESTRATOR

# Strip hook-error prefix from all 4 content shapes.
# Returns (new_content, removed_chunks) — removed_chunks is a list of stripped prefix strings,
# one per match, for stripped_hook_error_prefix mod attribution via attribute_chunk.
def _strip_hook_prefix(content):
    removed = []
    if isinstance(content, str):
        return _strip_from_text(content, removed), removed
    if isinstance(content, list):
        result = []
        for block in content:
            if not isinstance(block, dict):
                result.append(block)
                continue
            btype = block.get('type')
            if btype == 'text':
                new_text = _strip_from_text(block.get('text', ''), removed)
                result.append({**block, 'text': new_text} if new_text != block.get('text', '') else block)
            elif btype == 'tool_result':
                inner = block.get('content', '')
                if isinstance(inner, str):
                    new_inner = _strip_from_text(inner, removed)
                    result.append({**block, 'content': new_inner} if new_inner != inner else block)
                elif isinstance(inner, list):
                    new_sub = []
                    for sub in inner:
                        if isinstance(sub, dict) and sub.get('type') == 'text':
                            new_text = _strip_from_text(sub.get('text', ''), removed)
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

# Strip hook-error prefix from a single string; append removed prefix(es) to out_removed.
def _strip_from_text(text, out_removed):
    if _HOOK_PREFIX_MARKER not in text:
        return text

    def _replace(m):
        out_removed.append(m.group(0).rstrip())
        return ''

    return _HOOK_PREFIX_RE.sub(_replace, text, count=1)
