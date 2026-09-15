# INFRASTRUCTURE
import json
from difflib import SequenceMatcher

RATIO_THRESHOLD = 0.1  # from src/proxy/diff_engine.py

# FUNCTIONS

# ── helpers (minimal copies from src/) ───────────────────────────────────────

def _strip_cache_control(obj):
    if isinstance(obj, dict):
        return {k: _strip_cache_control(v) for k, v in obj.items() if k != "cache_control"}
    if isinstance(obj, list):
        return [_strip_cache_control(i) for i in obj]
    return obj


def _normalize_msg_shape(msg: dict) -> dict:
    if msg.get("role") != "user":
        return msg
    content = msg.get("content")
    if not isinstance(content, list) or len(content) != 1:
        return msg
    block = content[0]
    if not isinstance(block, dict):
        return msg
    if set(block.keys()) == {"type", "text"} and block["type"] == "text":
        return {**msg, "content": block["text"]}
    return msg


def _get_text(element) -> str:
    """Production _get_text from diff_engine.py — returns JSON dump for non-text blocks."""
    if element is None:
        return ""
    if isinstance(element, str):
        return element
    if isinstance(element, dict):
        t = element.get("text")
        if t is not None:
            return str(t)
        return json.dumps(element, ensure_ascii=False)
    return json.dumps(element, ensure_ascii=False)


def _get_inner_text(block) -> str:
    """Inner content text the proxy actually operates on — used for GT spans.
    text blocks        → block["text"] (raw string, same as _get_text)
    tool_result blocks → block["content"] (raw string, avoids JSON-escape mismatch)
    other dicts        → json.dumps (same as _get_text)
    """
    if isinstance(block, str):
        return block
    if isinstance(block, dict):
        if "text" in block:
            return str(block["text"])
        if block.get("type") == "tool_result":
            c = block.get("content", "")
            if isinstance(c, str):
                return c
            if isinstance(c, list):
                return "\n".join(
                    b.get("text", "") for b in c
                    if isinstance(b, dict) and "text" in b
                )
        return json.dumps(block, ensure_ascii=False)
    return json.dumps(block, ensure_ascii=False)


# ── diff_text_word (current production, copied from green_overlay_probe) ─────

def diff_text_word(orig_text: str, fwd_text: str) -> list:
    if orig_text == fwd_text:
        return [("equal", orig_text)]
    if not orig_text:
        return [("injected", fwd_text)]
    if not fwd_text:
        return [("stripped", orig_text)]
    ratio = SequenceMatcher(None, orig_text, fwd_text).ratio()
    if ratio < RATIO_THRESHOLD:
        return [("stripped", orig_text), ("injected", fwd_text)]
    spans = []
    ow, fw = orig_text.split(), fwd_text.split()
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, ow, fw).get_opcodes():
        if tag == "equal":
            spans.append(("equal", " ".join(ow[i1:i2])))
        elif tag == "delete":
            spans.append(("stripped", " ".join(ow[i1:i2])))
        elif tag == "insert":
            spans.append(("injected", " ".join(fw[j1:j2])))
        else:
            spans.append(("stripped", " ".join(ow[i1:i2])))
            spans.append(("injected", " ".join(fw[j1:j2])))
    return spans


# ── GT algorithm under test ───────────────────────────────────────────────────

# Step 1: split orig_text at stripped_chunk positions → equal_segs + stripped_segs + flags
def _split_stripped_chunks(orig_text: str, stripped_chunks: list) -> tuple:
    flags = []
    equal_segs: list = []
    stripped_segs: list = []
    pos = 0
    for chunk in stripped_chunks:
        chunk_pos = orig_text.find(chunk, pos)
        if chunk_pos == -1:
            # Chunk not found at or after pos — may be nested inside a prior stripped segment
            # or a recording gap from intermediate-pass extraction
            if any(chunk in s for s in stripped_segs):
                flags.append(f"NESTED_CHUNK(len={len(chunk)}) '{chunk[:40]}...'")
            else:
                flags.append(f"CHUNK_NOT_IN_ORIG(len={len(chunk)}) '{chunk[:40]}...'")
            continue  # skip: already covered or unresolvable
        equal_segs.append(orig_text[pos:chunk_pos])
        stripped_segs.append(chunk)
        pos = chunk_pos + len(chunk)
    equal_segs.append(orig_text[pos:])  # final equal segment (may be "")
    return equal_segs, stripped_segs, flags


# Step 2 + 3: walk fwd_text matching each equal segment; gaps = injected
def _walk_forward_spans(fwd_text: str, equal_segs: list, stripped_segs: list) -> tuple:
    flags = []
    spans: list = []
    fwd_pos = 0

    for i, eq_seg in enumerate(equal_segs):
        # Emit preceding stripped segment (if any)
        if i > 0:
            spans.append(("stripped", stripped_segs[i - 1]))

        if eq_seg:
            eq_fwd_pos = fwd_text.find(eq_seg, fwd_pos)
            if eq_fwd_pos == -1:
                flags.append(f"EQUAL_NOT_IN_FWD(len={len(eq_seg)}) '{eq_seg[:40]}...'")
                spans.append(("equal", eq_seg))  # best-effort
                continue
            if eq_fwd_pos > fwd_pos:
                spans.append(("injected", fwd_text[fwd_pos:eq_fwd_pos]))
            spans.append(("equal", eq_seg))
            fwd_pos = eq_fwd_pos + len(eq_seg)

    # Any remaining fwd_text = injected
    if fwd_pos < len(fwd_text):
        spans.append(("injected", fwd_text[fwd_pos:]))

    # Safety: if the loop emitted nothing (all equal_segs empty AND stripped_segs non-empty),
    # emit stripped_segs directly. This handles the full-replace case where o_text == chunk.
    if not spans and stripped_segs:
        for s in stripped_segs:
            spans.append(("stripped", s))
        if fwd_text:
            spans.append(("injected", fwd_text))

    return spans, flags


def build_message_spans(orig_text: str, fwd_text: str, stripped_chunks: list) -> tuple:
    """Build ground-truth spans from exact stripped chunks.

    Returns: (spans, flags) where
      spans = [(tag, text), ...] tags: 'equal' / 'stripped' / 'injected'
      flags = list of issue strings (NESTED_CHUNK / EQUAL_NOT_IN_FWD / CHUNK_NOT_IN_ORIG)
    """
    if not stripped_chunks:
        if orig_text == fwd_text:
            return ([("equal", orig_text)] if orig_text else []), []
        return [("equal", orig_text)], []  # no-strip fallback

    equal_segs, stripped_segs, split_flags = _split_stripped_chunks(orig_text, stripped_chunks)
    spans, walk_flags = _walk_forward_spans(fwd_text, equal_segs, stripped_segs)

    return spans, split_flags + walk_flags


# ── fidelity check ─────────────────────────────────────────────────────────

def check_fidelity(orig_text: str, fwd_text: str, spans: list) -> tuple:
    """Lossless: equal+stripped must rebuild orig_text; equal+injected must rebuild fwd_text."""
    orig_recon = "".join(t for tag, t in spans if tag in ("equal", "stripped"))
    fwd_recon = "".join(t for tag, t in spans if tag in ("equal", "injected"))
    return orig_recon == orig_text, fwd_recon == fwd_text


def check_fidelity_diff(orig_text: str, fwd_text: str, spans: list) -> tuple:
    """Fidelity for diff_text_word — same check but compensates for whitespace join loss."""
    orig_recon = " ".join(t for tag, t in spans if tag in ("equal", "stripped"))
    fwd_recon = " ".join(t for tag, t in spans if tag in ("equal", "injected"))
    return orig_recon == orig_text, fwd_recon == fwd_text
