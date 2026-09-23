# INFRASTRUCTURE
import re

_PASTED_CONTENT_OPEN_MARKER = '<pasted_content id="'

_PASTED_CONTENT_RE = re.compile(
    r'<pasted_content id="([^"]*)">(.*?)</pasted_content id="\1">',
    re.DOTALL,
)


# ORCHESTRATOR

def _strip_pasted_content_wrapper(content):
    removed = []
    if isinstance(content, str):
        return _strip_pasted_content_from_text(content, removed), removed
    if isinstance(content, list):
        return _strip_pasted_content_from_blocks(content, removed), removed
    return content, removed


# FUNCTIONS

def _strip_pasted_content_from_blocks(blocks, out_removed):
    result = []
    for block in blocks:
        if not isinstance(block, dict) or block.get('type') != 'text':
            result.append(block)
            continue
        text = block.get('text', '')
        new_text = _strip_pasted_content_from_text(text, out_removed)
        result.append({**block, 'text': new_text} if new_text != text else block)
    return result


def _strip_pasted_content_from_text(text, out_removed):
    if _PASTED_CONTENT_OPEN_MARKER not in text:
        return text

    def _replace(m):
        wrapper_id = m.group(1)
        out_removed.append(f'<pasted_content id="{wrapper_id}">')
        out_removed.append(f'</pasted_content id="{wrapper_id}">')
        return m.group(2)

    return _PASTED_CONTENT_RE.sub(_replace, text)
