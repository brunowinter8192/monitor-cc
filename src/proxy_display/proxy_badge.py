# INFRASTRUCTURE
import re

# Newer CC appends a fresh role='system' "<total_tokens>N tokens left</total_tokens>" message to the
# END of the message history on EVERY request; `_apply_role_system_strip` nukes it to "." (correct).
# The nuke lands at a NEW message index each request, so its loc_key is new each request and the
# write-side hash dedup structurally cannot suppress it — a messages_delta entry is written on
# virtually every request. Anchored FULL-match, never substring-anywhere: the same string is
# routinely quoted inside real content. Read-side note: the dual-log line carries no role, so the
# write side's second anchor (role=='system') is not available here — the full-match on a single
# stripped text is doing the whole job, which holds because no strip pass removes a bare, otherwise
# empty total_tokens marker from a non-system message.
_TOTAL_TOKENS_NUKE_RE = re.compile(r"^<total_tokens>\d+ tokens left</total_tokens>$")

# On model claude-f, CC's trailing role='system' message is no longer always the bare tag above —
# it can carry one or two (measured up to four, repeats and either order) fixed nudge sentences
# BEFORE the tag, e.g. "First privately list what you need next...\n\n<total_tokens>N tokens
# left</total_tokens>". On the next request CC re-sends the PREVIOUS trailing message with one
# sentence dropped, so the proxy strips a DIFFERENT text at a DIFFERENT index every time — the same
# structural hash-dedup defeat as the bare tag, just with prose in front of it now. Measured
# 2026-09-05 (dev/proxy_tool_stripping/probe_trailing_message_shapes.py against the three current
# `_stripped.jsonl` logs, see process-docs/proxy_tool_stripping/ for the counts): 24 distinct
# shapes total, all but a handful reducing to combinations of exactly these three sentences.
# Catalogued by EXACT sentence, same convention as strip_sr.py's SR-template catalog — a heuristic
# "generic prose" detector was rejected: it would also swallow a real notice that reads as plain
# prose (the mid-conversation nuke class already covered by TT03 carries no tag and is unaffected,
# but nothing rules out a future one that does). Deliberately NOT closed to future CC wording — see
# _is_total_tokens_nuke_text: a sentence not in this set fails the paragraph-decomposition test, so
# an unrecognized future nudge stays on the badge (fails open toward showing it) rather than being
# silently absorbed, until this catalog is updated against newly measured data.
_TOTAL_TOKENS_NUDGE_PARAGRAPHS = frozenset({
    "First privately list what you need next; then request every item that doesn't depend on "
    "another's result in this one response.",
    "Only you see that command's output — the user's terminal shows at most a few lines of it. "
    "If the user needs to read any of it, put it in your reply.",
    "The user hasn't heard from you in a while — say in a few words what you're doing, then continue.",
})

# The tag anchored to the END of the string only (trailing whitespace tolerated after it, same as
# _TOTAL_TOKENS_NUKE_RE's .strip() convention) — unlike that regex this one does NOT require the
# tag to be the ENTIRE string, since nudge prose may precede it.
_TOTAL_TOKENS_TRAILING_TAG_RE = re.compile(r"<total_tokens>\d+ tokens left</total_tokens>\s*\Z")


# FUNCTIONS

# Is `text` the bare total_tokens marker (existing rule), or the marker preceded ONLY by known CC
# nudge paragraphs, in any order and any repeat count? Shape test, not a whole-message sentence
# list: split everything before the tag on blank lines and require EVERY resulting paragraph to be
# catalogued — a real notice glued onto the tag (deferred-tools, skills-available, file-modified, a
# hook message) fails the moment ONE of its paragraphs is not in the catalog, so it stays counted.
# Verified against the corpus: at the exact position the lag correction targets, this test accepts
# 103 genuine nudge/bare cases and correctly rejects the 6 real-content cases measured there.
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

# Is ONE message index's delta entry substantial? Extracted from `_msgs_delta_is_substantial`,
# which is now an any-of over it — the split briefly also fed a per-index prepend filter
# (removed 2026-08-30 with the out-of-window prepend itself), so the badge is its only consumer
# again. Kept split because the per-index question is the meaningful one and reads clearer.
# `blks` is one messages_delta value: {blk_idx -> [stripped texts]} or {blk_idx -> [(tag, text)]}.
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


# Is this delta entry the per-request total_tokens nuke — exactly ONE stripped text that is either
# the bare marker or the marker preceded only by known CC nudge prose (see
# _is_total_tokens_nuke_text)? The narrow shape the lag correction below keys on; see
# `dual_log_accumulator.accumulate_dual_log`. Widened 2026-09-05 alongside
# `_msg_delta_entry_is_substantial` so both stay in agreement on the class — measured that the
# re-sent trailing message at the exact position this function is asked about is nudge-shaped MORE
# often than bare-shaped in the current claude-f corpus (55 vs 48 occurrences), so leaving this
# narrow would have left the majority of the in-window span correction broken for exactly the
# sessions this milestone targets.
def _is_total_tokens_nuke(blks) -> bool:
    if not isinstance(blks, dict):
        return False
    texts = [
        t for blk in blks.values() if isinstance(blk, list)
        for t in blk if isinstance(t, str)
    ]
    return len(texts) == 1 and _is_total_tokens_nuke_text(texts[0])


# Does this line's messages_delta carry anything BADGE-worthy? Badge-only helper — the overlay
# dicts and _msg_idx_by_flow_id are populated from the raw delta regardless, so the expanded view
# keeps rendering IN-WINDOW every span this filters out here. Out-of-window there is nothing left
# to render: the expanded body is the request's payload delta only (2026-08-30), so for a strip
# outside that window this function's verdict decides whether ANY trace reaches the reader.
# Two classes are not substantial (2026-08-29, widened 2026-09-05):
#   - stripped side: a message whose blocks' stripped texts are ALL either the bare total_tokens
#     marker or the marker preceded only by known CC nudge prose (`_is_total_tokens_nuke_text`) —
#     the per-request CC token-budget nuke, noise on nearly every request. Two or more such
#     messages in the same delta are still non-substantial (each is checked independently and ALL
#     must qualify — a real strip anywhere in the delta still counts, see `_msg_delta_entry_is_substantial`).
#   - injected side: a block whose injected spans are only ".", the API-required empty-block filler
#     that `strip_sr.py` / `_apply_role_system_strip` leave behind (same principle the fn_map "."
#     skips already encode write-side).
# Everything else counts, so a real content injection and a real strip badge exactly as before.
# NOTE this is the per-line signal, NOT the final badge. Suppressing every "."-only injection would
# also silence the nag/deferred/date-changed nukes, whose "." IS injected and DOES render green.
# `badge_flags` below re-adds exactly those by coordinating with the flow's stripped side; only the
# total_tokens class ends up with both badge words off.
def _msgs_delta_is_substantial(msgs_delta: dict, entry_type: str) -> bool:
    is_injected = entry_type == 'injected_delta'
    return any(
        _msg_delta_entry_is_substantial(blks, is_injected)
        for blks in (msgs_delta or {}).values()
    )


# Resolve the REQ-header's two badge booleans for one entry -> (show_strip, show_inject).
# Reads the per-flow lookups pane.py / worker_proxy_pane.py attach; falls back to False for any
# lookup a caller did not attach.
#
# The inject side needs the strip side to decide, because an `injected_delta` line CANNOT identify
# the total_tokens class on its own — a total_tokens nuke and a task-tools-nag nuke both inject the
# identical literal "." and the marker text lives only on the stripped side. So the two are
# coordinated by flow_id here, at the consumer, where both lookups are in hand:
#
#   show_inject = real (non-".") injection   OR   ("."-filler present AND the strip side is substantial)
#
# `_inject_fns_lookup` is already the "real injection" bool (`_msgs_delta_is_substantial` treats a
# "."-only block as insubstantial), and a non-empty `_inject_msgs_lookup` entry means the injected
# side touched a message block at all — which, given the writer only records a block when it has an
# injected span, is exactly "a '.'-filler is present" once the real-injection case is excluded.
#
# Resulting behavior, one line per class:
#   - total_tokens nuke  -> strip False, inject False (strip side is the non-substantial one)
#   - task-tools nag / deferred / date-changed / mid-conv nuke -> strip True, inject True
#   - total_tokens + a real strip in the same request -> strip True, inject True
#   - real content injection (bg-exit wake-up, TN wake-up, system rules) -> inject True regardless
#
# Computed per render rather than stored at accumulation time on purpose: the two dual-log files are
# tailed independently, so at accumulation time the peer line for a flow may not have been read yet.
# Deriving it here is order-independent and self-correcting for the running session.
def badge_flags(entry: dict) -> tuple:
    fid = entry.get('flow_id', '')
    show_strip = bool(entry.get('_strip_fns_lookup', {}).get(fid, False))
    show_inject = bool(entry.get('_inject_fns_lookup', {}).get(fid, False))
    if not show_inject and show_strip and entry.get('_inject_msgs_lookup', {}).get(fid):
        show_inject = True
    return show_strip, show_inject


# Estimate token count from char count (chars/3.5 heuristic, ~±15%)
def _chars_to_tokens(chars: int) -> int:
    return int(chars / 3.5)
