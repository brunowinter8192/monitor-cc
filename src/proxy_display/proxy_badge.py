# INFRASTRUCTURE
import re

_TOTAL_TOKENS_NUKE_RE = re.compile(r"^<total_tokens>\d+ tokens left</total_tokens>$")

_TOTAL_TOKENS_NUDGE_PARAGRAPHS = frozenset({
    "First privately list what you need next; then request every item that doesn't depend on "
    "another's result in this one response.",
    "Only you see that command's output — the user's terminal shows at most a few lines of it. "
    "If the user needs to read any of it, put it in your reply.",
    "The user hasn't heard from you in a while — say in a few words what you're doing, then continue.",
})

_TOTAL_TOKENS_TRAILING_TAG_RE = re.compile(r"<total_tokens>\d+ tokens left</total_tokens>\s*\Z")


# FUNCTIONS

def _is_total_tokens_nuke_text(text: str) -> bool:
    stripped = text.strip()
    if _TOTAL_TOKENS_NUKE_RE.match(stripped):
        return True
    m = _TOTAL_TOKENS_TRAILING_TAG_RE.search(text)
    if not m:
        return False
    paragraphs = [p.strip() for p in text[:m.start()].split('\n\n')]
    paragraphs = [p for p in paragraphs if p]
    return bool(paragraphs) and all(p in _TOTAL_TOKENS_NUDGE_PARAGRAPHS for p in paragraphs)

def _msg_delta_entry_is_substantial(blks, is_injected: bool) -> bool:
    if not isinstance(blks, dict):
        return False
    if is_injected:
        for spans in blks.values():
            if not isinstance(spans, list):
                continue
            texts = [
                s[1] for s in spans
                if isinstance(s, (list, tuple)) and len(s) == 2 and s[0] == 'injected' and s[1]
            ]
            if texts and ' '.join(texts) != '.':
                return True
        return False
    texts = [
        t for blk in blks.values() if isinstance(blk, list)
        for t in blk if isinstance(t, str)
    ]
    if texts and all(_is_total_tokens_nuke_text(t) for t in texts):
        return False
    return bool(texts)


def _is_total_tokens_nuke(blks) -> bool:
    if not isinstance(blks, dict):
        return False
    texts = [
        t for blk in blks.values() if isinstance(blk, list)
        for t in blk if isinstance(t, str)
    ]
    return len(texts) == 1 and _is_total_tokens_nuke_text(texts[0])


def _msgs_delta_is_substantial(msgs_delta: dict, entry_type: str) -> bool:
    is_injected = entry_type == 'injected_delta'
    return any(
        _msg_delta_entry_is_substantial(blks, is_injected)
        for blks in (msgs_delta or {}).values()
    )


def badge_flags(entry: dict) -> tuple:
    fid = entry.get('flow_id', '')
    show_strip = bool(entry.get('_strip_fns_lookup', {}).get(fid, False))
    show_inject = bool(entry.get('_inject_fns_lookup', {}).get(fid, False))
    if not show_inject and show_strip and entry.get('_inject_msgs_lookup', {}).get(fid):
        show_inject = True
    return show_strip, show_inject


def _chars_to_tokens(chars: int) -> int:
    return int(chars / 3.5)
