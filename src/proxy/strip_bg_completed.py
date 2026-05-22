import re

# INFRASTRUCTURE

_BG_CMD_MARKER = 'Background command "'

# Match kill-notification lines in both known forms:
#   "failed with exit code 143/137"
#   "Background command "CMD" completed (exit code 143/137)"
# HTML-encoded && (&amp;&amp;) is handled transparently — regex matches any command text.
# Trailing newline consumed if present. Does NOT match exit code 0 (legitimate timer-done signal).
_BG_EXIT_RE = re.compile(
    r'Background command "[^"]*" '
    r'(?:failed with exit code (?:143|137)|completed \(exit code (?:143|137)\))\n?'
)

# Plain-text wake-up hint injected in place of the first matched kill notification.
# Trailing newline keeps it cleanly separated in multi-line content.
_WAKEUP_TEXT = 'worker idle\n'


# ORCHESTRATOR

# Replace the first Background-command kill notification with _WAKEUP_TEXT; strip any further ones.
# Traverses all 4 content shapes. Returns (new_content, removed_chunks) — removed_chunks is a list
# of the original notification strings (each starting with 'Background command "') for BGK rule
# attribution via attribute_chunk. Interface unchanged from the pure-strip version.
def _strip_bg_exit_notifications(content):
    removed = []
    injected = [False]  # mutable flag: True after first kill-notification has been replaced
    if isinstance(content, str):
        return _strip_bg_from_text(content, removed, injected), removed
    if isinstance(content, list):
        result = []
        for block in content:
            if not isinstance(block, dict):
                result.append(block)
                continue
            btype = block.get('type')
            if btype == 'text':
                new_text = _strip_bg_from_text(block.get('text', ''), removed, injected)
                result.append({**block, 'text': new_text or '.'})
            elif btype == 'tool_result':
                inner = block.get('content', '')
                if isinstance(inner, str):
                    new_inner = _strip_bg_from_text(inner, removed, injected)
                    result.append({**block, 'content': new_inner} if new_inner != inner else block)
                elif isinstance(inner, list):
                    new_sub = []
                    for sub in inner:
                        if isinstance(sub, dict) and sub.get('type') == 'text':
                            new_text = _strip_bg_from_text(sub.get('text', ''), removed, injected)
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

# Replace the first BG-exit kill notification in text with _WAKEUP_TEXT; strip subsequent ones.
# injected_holder is a [False] list — shared across all _strip_bg_from_text calls in one traversal
# so the wake-up text is injected at most once per _strip_bg_exit_notifications call.
# Returns text unchanged if no match fires (avoids touching unrelated BG-cmd lines).
def _strip_bg_from_text(text, out_removed, injected_holder):
    if _BG_CMD_MARKER not in text:
        return text
    before = len(out_removed)

    def _replace(m):
        out_removed.append(m.group(0).rstrip('\n'))
        if not injected_holder[0]:
            injected_holder[0] = True
            return _WAKEUP_TEXT
        return ''

    result = _BG_EXIT_RE.sub(_replace, text)
    if len(out_removed) == before:
        return text  # BG marker present but no kill-exit-code matched — leave unchanged
    return result.strip() or '.'
