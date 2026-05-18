import re

# INFRASTRUCTURE

_BG_CMD_MARKER = 'Background command "'

# Match kill-notification lines in both known forms:
#   "Background command "CMD" failed with exit code 143/137"
#   "Background command "CMD" completed (exit code 143/137)"
# HTML-encoded && (&amp;&amp;) is handled transparently — regex matches any command text.
# Trailing newline consumed if present. Does NOT match exit code 0 (legitimate timer-done signal).
_BG_EXIT_RE = re.compile(
    r'Background command "[^"]*" '
    r'(?:failed with exit code (?:143|137)|completed \(exit code (?:143|137)\))\n?'
)


# ORCHESTRATOR

# Strip Background-command kill notifications from all 4 content shapes.
# Returns (new_content, removed_chunks) — removed_chunks is a list of stripped notification strings,
# each starting with 'Background command "' for BGK rule attribution via attribute_chunk.
def _strip_bg_exit_notifications(content):
    removed = []
    if isinstance(content, str):
        return _strip_bg_from_text(content, removed), removed
    if isinstance(content, list):
        result = []
        for block in content:
            if not isinstance(block, dict):
                result.append(block)
                continue
            btype = block.get('type')
            if btype == 'text':
                new_text = _strip_bg_from_text(block.get('text', ''), removed)
                result.append({**block, 'text': new_text or '.'})
            elif btype == 'tool_result':
                inner = block.get('content', '')
                if isinstance(inner, str):
                    new_inner = _strip_bg_from_text(inner, removed)
                    result.append({**block, 'content': new_inner} if new_inner != inner else block)
                elif isinstance(inner, list):
                    new_sub = []
                    for sub in inner:
                        if isinstance(sub, dict) and sub.get('type') == 'text':
                            new_text = _strip_bg_from_text(sub.get('text', ''), removed)
                            new_sub.append({**sub, 'text': new_text or '.'})
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

# Strip all BG-exit notification lines from a single string; appends removed chunks to out_removed.
# Returns text unchanged if no match fires (avoids stripping whitespace from unrelated BG-cmd lines).
def _strip_bg_from_text(text, out_removed):
    if _BG_CMD_MARKER not in text:
        return text
    before = len(out_removed)

    def _replace(m):
        out_removed.append(m.group(0).rstrip('\n'))
        return ''

    result = _BG_EXIT_RE.sub(_replace, text)
    if len(out_removed) == before:
        return text  # BG marker present but no kill-exit-code matched — leave unchanged
    return result.strip() or '.'
