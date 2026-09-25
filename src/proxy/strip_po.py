# INFRASTRUCTURE
import re

from src.proxy.strip_walk import strip_content_tree

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
    result = strip_content_tree(content, _strip_po_preview_from_text, removed, rebuild_text=True)
    return result, removed


# FUNCTIONS

def _strip_po_preview_from_text(text, out_removed):
    if _PO_OPEN_TAG not in text:
        return text

    def _replace(m):
        out_removed.append(m.group('preview').lstrip('\n'))
        return m.group('open') + m.group('close')

    return _PO_PREVIEW_RE.sub(_replace, text)
