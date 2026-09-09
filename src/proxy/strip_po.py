import re

# INFRASTRUCTURE

_PO_OPEN_TAG = '<persisted-output>'

_PO_PREVIEW_RE = re.compile(
    r'(?P<open><persisted-output>\nOutput too large[^\n]+)'
    r'(?P<preview>\n+Preview \(first [^\n]+\):\n.*?)'
    r'(?P<close>\n?</persisted-output>)',
    re.DOTALL,
)


# ORCHESTRATOR

def _strip_persisted_output_previews(content):
    removed = []
    if isinstance(content, str):
        return _strip_po_preview_from_text(content, removed), removed
    if isinstance(content, list):
        result = []
        for block in content:
            if not isinstance(block, dict):
                result.append(block)
                continue
            btype = block.get('type')
            if btype == 'text':
                new_text = _strip_po_preview_from_text(block.get('text', ''), removed)
                result.append({**block, 'text': new_text})
            elif btype == 'tool_result':
                inner = block.get('content', '')
                if isinstance(inner, str):
                    new_inner = _strip_po_preview_from_text(inner, removed)
                    result.append({**block, 'content': new_inner} if new_inner != inner else block)
                elif isinstance(inner, list):
                    new_sub = []
                    for sub in inner:
                        if isinstance(sub, dict) and sub.get('type') == 'text':
                            new_text = _strip_po_preview_from_text(sub.get('text', ''), removed)
                            new_sub.append({**sub, 'text': new_text})
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

def _strip_po_preview_from_text(text, out_removed):
    if _PO_OPEN_TAG not in text:
        return text

    def _replace(m):
        out_removed.append(m.group('preview').lstrip('\n'))
        return m.group('open') + m.group('close')

    return _PO_PREVIEW_RE.sub(_replace, text)
