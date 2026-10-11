# INFRASTRUCTURE
import re

_TOTAL_TOKENS_CLOSE_MARKER = '</total_tokens>'

_TOTAL_TOKENS_TAIL_RE = re.compile(r'<total_tokens>\d+ tokens left</total_tokens>\s*\Z')


# ORCHESTRATOR

def _strip_total_tokens_tail(content):
    removed = []
    if isinstance(content, str):
        return _strip_tail_from_text(content, removed), removed
    if isinstance(content, list):
        return _strip_tail_from_last_block(content, removed), removed
    return content, removed


# FUNCTIONS

def _strip_tail_from_last_block(blocks, out_removed):
    if not blocks:
        return blocks
    last = blocks[-1]
    if not isinstance(last, dict) or last.get('type') != 'text':
        return blocks
    text = last.get('text', '')
    new_text = _strip_tail_from_text(text, out_removed)
    if new_text == text:
        return blocks
    return blocks[:-1] + [{**last, 'text': new_text}]


def _strip_tail_from_text(text, out_removed):
    if _TOTAL_TOKENS_CLOSE_MARKER not in text:
        return text
    match = _TOTAL_TOKENS_TAIL_RE.search(text)
    if not match:
        return text
    head = text[:match.start()].rstrip('\n')
    if not head.strip():
        return text
    out_removed.append(text[len(head):])
    return head
