import re

# INFRASTRUCTURE

_BG_CMD_MARKER = 'Background command "'

_BG_EXIT_RE = re.compile(
    r'Background command "[^"]*" '
    r'(?:failed with exit code (?:143|137)|completed \(exit code (?:143|137)\))\n?'
)

_WAKEUP_TEXT = 'background done — check worker or other process\n'


# ORCHESTRATOR

def _strip_bg_exit_notifications(content):
    removed = []
    injected = [False]
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
            else:
                result.append(block)
        return result, removed
    return content, removed


# FUNCTIONS

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
        return text
    return result.strip() or '.'
