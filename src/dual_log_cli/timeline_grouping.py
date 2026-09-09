# INFRASTRUCTURE
import bisect

from .timeline_markers import request_markers

# FUNCTIONS


# True for a turn-OPENING user msg (`reqs --turns`, 2026-09-08): a `user`-role msg carrying a
# `text` block and NO `tool_result` block — a real human/orchestrator prompt, never CC's own
# tool-result relay. A str-content pseudo-block (`system-reminder`/`task-notification`/etc, see
# `build_turns`) never carries the literal type `"text"`, so it is excluded for free, without a
# separate type-name check.
def _is_turn_opener(turn: dict) -> bool:
    if turn.get("role") != "user":
        return False
    types = {block.get("type") for block in turn.get("blocks", [])}
    return "text" in types and "tool_result" not in types


# Msg indices of every turn-opening msg, in msg-index (== chronological) order.
def turn_openers(turns: list) -> list:
    return [turn["index"] for turn in turns if _is_turn_opener(turn)]


# The preview text a turn's opener contributes — the LAST `text`-type block's own preview, not
# the first. A spawn prompt (verified: the only multi-text-block opener in the corpus this was
# checked against) carries a leading `<system-reminder>`-wrapped block ahead of the real prompt;
# taking the last text block is what surfaces "You are a WORKER." instead of the reminder wrapper,
# and is a no-op for every other opener observed (all single-text-block).
def _turn_preview(turn: dict) -> str:
    preview = ""
    for block in turn.get("blocks", []):
        if block.get("type") == "text":
            preview = block.get("preview", "")
    return preview


# Shared turn-assignment walk for `reqs --turns` (2026-09-10, `render._turn_grouped_lines`) —
# split out so the grouping logic lives in exactly one place regardless of which render function
# consumes it. Returns `(markers, openers, groups)`: `markers` is `request_markers`' own
# `{msg_index: marker}`, `openers` is `turn_openers`' own msg-index list, `groups[i]` is the SORTED
# list of msg-index keys (== request order) belonging to turn `i+1`.
#
# Turn ASSIGNMENT is the one non-obvious part (see Gotchas in DOCS.md): a request's msg-index KEY
# in `request_markers` (its `start_index`, the smallest index its OWN send first reveals) is NOT
# what decides which turn it belongs to — a request that answers with plain text and goes idle is
# never itself sent onward, so its reply only becomes visible bundled into the NEXT request's
# delta, which can carry a LOW start_index while its own `message_count` already reaches past the
# NEXT turn's opener. The correct test is therefore against `message_count` (this request's own
# SENT payload size, i.e. which openers its own send already carries), not `start_index`:
# `bisect_right(openers, message_count - 1)` gives the 1-based turn number directly — the count of
# openers already contained in that request's own payload. Verified against two real sessions
# (originally for the now-removed `turns` command, still true here — the assignment rule did not
# change, only what reads it): using `start_index` instead over-counted `reldist-power`'s turn 1
# by exactly the one request whose send bundled the turn's own idle-text reply together with the
# next turn's new prompt.
def _group_markers_by_turn(turns: list, boundaries: list) -> tuple:
    markers = request_markers(boundaries or [])
    openers = turn_openers(turns)
    groups = [[] for _ in openers]
    if openers:
        for msg_index in sorted(markers):
            marker = markers[msg_index]
            position = bisect.bisect_right(openers, marker["message_count"] - 1)
            position = max(1, min(position, len(openers))) - 1
            groups[position].append(msg_index)
    return markers, openers, groups
