# INFRASTRUCTURE
import bisect
import json
from pathlib import Path

from ..proxy.logging import _delta_hash
from ..proxy.message_summary import _summarize_message
from .reader import infer_family, iter_jsonl, load_last_request

PREVIEW_CHARS = 100
# The per-request billing header: a hash plus the previous request id, changing on every request
# by construction. It never invalidates the prompt cache, so it is excluded from the changed/new
# delta lines on every request but the first (see process-docs/cache/).
_BILLING_HEADER_SYS_INDEX = 0


class UnknownRequestNumberError(Exception):
    pass


class AmbiguousRequestNumberError(Exception):
    pass


# FUNCTIONS


# One-line preview: first non-empty line of the text, whitespace-collapsed and truncated
def _preview(text: str, limit: int = PREVIEW_CHARS) -> str:
    if not text:
        return ""
    line = ""
    for candidate in text.split("\n"):
        if candidate.strip():
            line = " ".join(candidate.split())
            break
    if not line:
        line = " ".join(text.split())
    return line[:limit] + ("…" if len(line) > limit else "")


# Display label for one content block
def _block_label(block: dict) -> str:
    btype = block.get("type", "text")
    if btype == "tool_use":
        return f"tool_use[{block.get('preview', '') or '?'}]"
    if btype == "tool_result" and block.get("is_error"):
        return "tool_result!err"
    return btype


# Preview text for one content block — tool_use shows its input, not just the tool name
def _block_preview(block: dict) -> str:
    full = block.get("full_text", "") or ""
    if block.get("type") == "tool_use":
        _, _, input_json = full.partition("\n")
        return _preview(input_json or full)
    return _preview(full)


# Compact rows for every message of a payload. full_text is dropped here — only the msgs of the
# expand window are re-summarized for their content dump, so peak memory stays near the parsed
# payload.
def build_turns(payload: dict) -> list:
    turns = []
    for index, message in enumerate(payload.get("messages", []) or []):
        summary = _summarize_message(message)
        blocks = [
            {
                "label": _block_label(block),
                "type": block.get("type", "text"),
                "chars": block.get("chars", 0),
                "sig_chars": block.get("sig_chars", 0),
                "preview": _block_preview(block),
            }
            for block in summary.get("blocks", [])
        ]
        if not blocks:
            # str content (CC delivers role='system' messages that way) — no block list exists
            blocks = [{
                "label": summary.get("type", "text"),
                "type": summary.get("type", "text"),
                "chars": summary.get("chars", 0),
                "sig_chars": 0,
                "preview": _preview(summary.get("content_preview", "")),
            }]
        turns.append({
            "index": index,
            "role": summary.get("role", "?"),
            "type": summary.get("type", "text"),
            "chars": summary.get("chars", 0),
            "blocks": blocks,
        })
    return turns


# Stream every block of every message as {turn, role, block_types, block, label, text, chars}.
# `block_types` is every block type the MESSAGE carries, so a caller can apply a block-level
# --only to whole messages without re-summarizing them. `chars` is the same original-payload chars
# value `build_turns`/`full_turn` read off the block (`block.get("chars", 0)`, or `summary["chars"]`
# for the no-blocks pseudo-block) — search reports it unchanged, never re-measuring `text`. A
# generator, so a 14 MB payload is never doubled by holding all full_text values at once —
# build_turns drops them for exactly the same reason.
def iter_block_texts(payload: dict):
    for index, message in enumerate(payload.get("messages", []) or []):
        summary = _summarize_message(message)
        role = summary.get("role", "?")
        blocks = summary.get("blocks", [])
        if blocks:
            block_types = [b.get("type", "text") for b in blocks]
            for position, block in enumerate(blocks):
                yield {
                    "turn": index,
                    "role": role,
                    "block_types": block_types,
                    "block": position,
                    "label": _block_label(block),
                    "text": block.get("full_text", "") or "",
                    "chars": block.get("chars", 0),
                }
        else:
            yield {
                "turn": index,
                "role": role,
                "block_types": [summary.get("type", "text")],
                "block": 0,
                "label": summary.get("type", "text"),
                "text": summary.get("content_preview", "") or "",
                "chars": summary.get("chars", 0),
            }


# Full content of one turn: [(label, chars, full_text), ...]
def full_turn(payload: dict, turn_index: int) -> list:
    messages = payload.get("messages", []) or []
    if turn_index < 0 or turn_index >= len(messages):
        return []
    summary = _summarize_message(messages[turn_index])
    blocks = summary.get("blocks", [])
    if not blocks:
        return [(summary.get("type", "text"), summary.get("chars", 0), summary.get("content_preview", ""))]
    return [(_block_label(b), b.get("chars", 0), b.get("full_text", "") or "") for b in blocks]


# Wire chars of one system block in the forwarded payload — the text length. System blocks are
# {"type": "text", "text": ..., possibly "cache_control": ...} dicts in every observed case; a
# non-dict entry falls back to str() rather than raising, since this is a display measurement,
# not a schema check.
def _system_block_chars(block) -> int:
    if isinstance(block, dict):
        return len(block.get("text", "") or "")
    return len(str(block))


# Wire chars of one tool definition in the forwarded payload — its JSON serialisation
# (json.dumps, default separators), matching what the API actually receives on the wire.
def _tool_chars(tool) -> int:
    return len(json.dumps(tool))


# One request's SYSTEM delta lines, in index order — {"label", "chars", "tag"}. `tag` is None for
# the family's first request (every block is listed, nothing "changed" or "new" yet), else "new"
# for an index never before seen in `hash_by_index` and "changed" for one whose CONTENT hash now
# differs from what is stored there. Index 0 (the billing header, see _BILLING_HEADER_SYS_INDEX) is
# dropped on every request but the first — it changes by construction and never invalidates the
# cache. System blocks stay index-based (unlike tools, see `_tool_lines`): they carry no name, and
# a system block's own position has never been observed to shift the way a shrinking tool list does.
#
# `hash_by_index` is the content-hash map `request_boundaries` threads across the whole walk,
# MUTATED here — the caller's dict is the state, not a snapshot. Content is hashed with
# `_delta_hash`, the exact same normalisation `src/proxy/logging.py` uses to decide what belongs in
# `system_delta` in the first place (cache_control stripped), so a cache_control move alone never
# reads as a change here either.
#
# An index present in the raw delta but whose hash is UNCHANGED from what is stored is dropped
# entirely — no line, no tag. This is deliberate, not an edge case: the proxy's own delta chain is
# keyed by model family, so the request right after an interleaved sidecar call (see `_is_sidecar`)
# gets diffed against the SIDECAR's system on the write side, and every real block comes back
# "changed" even though its content never moved. `request_boundaries` already excludes the sidecar
# from becoming a boundary; this closes the matching write-side half of the same bug — a raw delta
# entry is not proof of a real change, only a hash comparison against OUR OWN last-seen content is.
def _sys_lines(delta: dict, hash_by_index: dict, is_first: bool) -> list:
    lines = []
    for key in sorted(delta, key=int):
        index = int(key)
        if index == _BILLING_HEADER_SYS_INDEX and not is_first:
            continue
        element = delta[key]
        content_hash = _delta_hash(element)
        if is_first:
            tag = None
        else:
            prev_hash = hash_by_index.get(index)
            if prev_hash == content_hash:
                continue  # write-side artifact — content unchanged since we last saw this index
            tag = "changed" if index in hash_by_index else "new"
        hash_by_index[index] = content_hash
        lines.append({"label": f"sys[{index}]", "chars": _system_block_chars(element), "tag": tag})
    return lines


# One request's TOOL lines, NAME-based rather than index-based — 'tool[Name] Nc new'/'changed' for
# a name whose content is new/differs, 'tool[Name] removed' (no chars) for a name that was active
# before and is absent now, and nothing at all for a tool that merely shifted index with identical
# content. Index-based comparison could not tell a removal from its shifted neighbours: dropping one
# tool from the middle of the list renumbers every tool after it, so the proxy's own per-POSITION
# delta includes every one of them as "changed" even though only the removed tool's content is
# actually gone — exactly what `skill-help_1788343931` REQ 196 showed (SendFeedback removed at
# tools 6→5; Skill and Write, unmoved in content, merely renumbered into its wake and used to print
# `changed` for both).
#
# `name_by_index` is the FULL current index→name map — every valid index, not just the ones this
# request's delta touches — and `hash_by_name` is the content hash last seen under each name; both
# are `request_boundaries`' running state, MUTATED here. A removal is inferred purely from a set
# difference: the names active BEFORE this request (`name_by_index`'s values, snapshotted first)
# minus the names active AFTER (every valid index 0..counts.tools-1, taken from this request's delta
# where touched, carried forward from the old map otherwise). Blind spot: if the SAME request both
# removes a tool and adds a DIFFERENT, unrelated tool whose name happens to already exist elsewhere
# in the (still-shrinking) tool list, the set-difference can only see net membership change, not
# which specific slot did what — not observed in the corpus (a session would need two tool-list
# edits landing in one API call), recorded rather than guarded against.
def _tool_lines(delta: dict, tools_count: int, name_by_index: dict, hash_by_name: dict, is_first: bool) -> list:
    if is_first:
        lines = []
        for key in sorted(delta, key=int):
            element = delta[key]
            name = element.get("name", "?") if isinstance(element, dict) else "?"
            name_by_index[int(key)] = name
            hash_by_name[name] = _delta_hash(element)
            lines.append({"label": f"tool[{name}]", "chars": _tool_chars(element), "tag": None})
        return lines

    old_names = set(name_by_index.values())
    old_index_by_name = {name: index for index, name in name_by_index.items()}
    touched = {int(key): delta[key] for key in delta}

    new_name_by_index = {}
    for index in range(tools_count):
        if index in touched:
            element = touched[index]
            new_name_by_index[index] = element.get("name", "?") if isinstance(element, dict) else "?"
        elif index in name_by_index:
            new_name_by_index[index] = name_by_index[index]
    removed_names = old_names - set(new_name_by_index.values())

    lines = []
    for index in sorted(touched):
        element = touched[index]
        name = element.get("name", "?") if isinstance(element, dict) else "?"
        content_hash = _delta_hash(element)
        if name in old_names and hash_by_name.get(name) == content_hash:
            hash_by_name[name] = content_hash
            continue  # same tool, same content, only its position moved
        tag = "changed" if name in old_names else "new"
        hash_by_name[name] = content_hash
        lines.append({"label": f"tool[{name}]", "chars": _tool_chars(element), "tag": tag})
    for name in sorted(removed_names, key=lambda n: old_index_by_name.get(n, tools_count)):
        lines.append({"label": f"tool[{name}]", "chars": None, "tag": "removed"})

    name_by_index.clear()
    name_by_index.update(new_name_by_index)
    return lines


# A conversation request always carries tools; a zero-tool non-haiku forwarded line is a sidecar
# call multiplexed into the same model family — observed as a recurring "security monitor" review
# call (own short message list, own system prompt, no tools) that `infer_family` cannot tell apart
# from the real conversation since both share a plain model name. It is not a conversation turn and
# never appears in CC's own transcript, so it must never seed a REQ, a restart, a turn time or a
# sys/tool delta comparison.
def _is_sidecar(counts: dict) -> bool:
    return counts.get("tools", 0) == 0


# Request boundaries for the conversation family, read from the _forwarded delta log
# (counts.messages per request). Each boundary marks the message index at which that request's
# new messages start. A restart flag is set when the message count regressed — CC was restarted
# mid-log-id, so boundaries before that point do not align with the final message list.
#
# A sidecar entry (see `_is_sidecar`) is skipped entirely, before anything reads or updates
# `prev_count` or the sys/tool state — it never becomes a boundary, so it can neither fake a
# restart (its own tiny message count would otherwise regress against the real conversation's) nor
# seed a content hash the NEXT real request would be wrongly compared against.
#
# Each boundary also carries `sys_lines`/`tool_lines` — the system/tool blocks that request's
# `system_delta`/`tools_delta` names, content-compared against the LAST REAL (non-sidecar) request
# (see `_sys_lines`, index-based, and `_tool_lines`, name-based). `sys_hash_by_index` (system) and
# `tools_name_by_index`/`tools_hash_by_name` (tools) are this walk's running state, live across every
# boundary of the family — computed here rather than re-derived later, since the state is only
# available while walking the stream forward.
def request_boundaries(forwarded_path: Path, family: str) -> list:
    boundaries = []
    request_no = 0
    prev_count = 0
    sys_hash_by_index: dict = {}
    tools_name_by_index: dict = {}
    tools_hash_by_name: dict = {}
    for entry in iter_jsonl(forwarded_path):
        if entry.get("type") != "forwarded_delta":
            continue
        if infer_family(entry.get("model", "")) != family:
            continue
        counts = entry.get("counts", {}) or {}
        if _is_sidecar(counts):
            continue
        request_no += 1
        count = counts.get("messages", 0)
        restart = count < prev_count
        is_first = bool(entry.get("is_first", False))
        boundaries.append({
            "request_no": request_no,
            "flow_id": entry.get("flow_id", ""),
            "timestamp": entry.get("timestamp", ""),
            "model": entry.get("model", ""),
            "start_index": 0 if restart else prev_count,
            "message_count": count,
            "restart": restart,
            "sys_lines": _sys_lines(entry.get("system_delta") or {}, sys_hash_by_index, is_first),
            "tool_lines": _tool_lines(entry.get("tools_delta") or {}, counts.get("tools", 0),
                                       tools_name_by_index, tools_hash_by_name, is_first),
        })
        prev_count = count
    return boundaries


# Map every turn to the timestamp of the request that FIRST carried it: turn N belongs to the
# earliest request whose counts.messages exceeds N. Returns {turn_index: iso_timestamp}; a turn
# absent from the dict has no reliable time and renders as "?".
#
# A restart (message count regressed — CC restarted inside one log id) discards the chain before
# it: those earlier requests described a different message list, so their counts cannot be walked
# against the final one. Only the chain from the LAST restart onward is used, and every turn below
# that restart's message count stays unmapped — the requests that first carried those messages are
# not in this chain at all, so such a turn renders its time as "?" rather than a wrong one.
def build_turn_times(boundaries: list) -> dict:
    chain = boundaries
    covered = 0
    for position, boundary in enumerate(boundaries):
        if boundary["restart"]:
            chain = boundaries[position:]
            covered = boundary["message_count"]
    times = {}
    for boundary in chain:
        count = boundary["message_count"]
        if count <= covered:
            continue
        for index in range(covered, count):
            times[index] = boundary["timestamp"]
        covered = count
    return times


# Which request opened each msg index -> {msg_index: {number, timestamp, refires, flow_id,
# sys_lines, tool_lines, message_count}}. flow_id is the owner's — what `usage.build_usage_by_flow`
# keys its {flow_id: (cr, cc)} map by, so a separator can look up its own request's prompt-cache
# usage without a second index. sys_lines/tool_lines are the OWNER boundary's own — a re-fire group
# shows only the owner's delta, matching the timestamp and usage the separator already carries.
# message_count (2026-09-08, for `reqs --turns`) is the owner's OWN total msg count as SENT — the
# msg count this request's payload already carried, which can run past the msg-index KEY this
# marker is grouped under (see `_group_markers_by_turn`'s Gotcha: a request whose own send bundles
# the previous turn's idle text reply together with the NEXT turn's new prompt keys a LOW msg
# index here but its message_count already covers the next turn's opener).
#
# Boundaries are grouped by the index they open. Several land on one index when a request re-fired
# without adding a msg (a retry/abort re-send) or when a restart reset the index to 0. At most ONE
# boundary of a group can add msgs, and it is always the LAST: every member shares the same
# prev_count, so the one that raises message_count ends the group. That member owns the group — its
# timestamp is when the msgs below actually arrived, and the earlier members are counted as refires.
#
# `number` counts only msg-ADDING requests, which is what makes it equal the proxy pane's `#N` for
# the same session (measured: 0 mismatches over 967 requests in 3 sessions, comparing number,
# message count and timestamp). The raw request_no would NOT match — it also counts re-fires, which
# the pane renders as `#N.M` without advancing N.
def request_markers(boundaries: list) -> dict:
    numbers = _running_request_numbers(boundaries)
    grouped: dict = {}
    for position, boundary in enumerate(boundaries):
        grouped.setdefault(boundary["start_index"], []).append(position)
    markers = {}
    for index, positions in grouped.items():
        owner = positions[-1]
        markers[index] = {
            "number": numbers[owner],
            "timestamp": boundaries[owner]["timestamp"],
            "refires": len(positions) - 1,
            "flow_id": boundaries[owner].get("flow_id", ""),
            "sys_lines": boundaries[owner].get("sys_lines", []),
            "tool_lines": boundaries[owner].get("tool_lines", []),
            "message_count": boundaries[owner].get("message_count", 0),
        }
    return markers


# Running REQ number per boundary position — the shared counting rule: only a msg-ADDING request
# advances the number, which is what keeps it equal to the proxy pane's `#N`. A re-fire carries the
# number of the request before it.
def _running_request_numbers(boundaries: list) -> list:
    numbers = []
    adding = 0
    for boundary in boundaries:
        if boundary["start_index"] < boundary["message_count"]:
            adding += 1
        numbers.append(adding)
    return numbers


# {flow_id: REQ number} for the boundaries of one session — the same numbering `msgs` prints, so an
# overlay attributed to a flow can name the request a reader already sees there. A re-fire maps to
# the number of the msg-adding request before it; the overlay renderer shows "?" for a flow absent
# here entirely (a sidecar the boundary list never carried).
def request_numbers_by_flow(boundaries: list) -> dict:
    numbers = _running_request_numbers(boundaries)
    return {
        boundary["flow_id"]: numbers[position]
        for position, boundary in enumerate(boundaries)
        if boundary.get("flow_id")
    }


# Msg-index range [start, end] spanned by REQ numbers req_from..req_to inclusive, for `msgs --req`.
# `markers` is `request_markers`'s own {msg_index: {number, ...}}; `start` is req_from's own msg
# index, `end` is the msg index right before the NEXT marker (by msg-index order) after req_to's
# own, or `last_msg_index` when req_to's group is the last one — the exact msg-index range the
# equivalent `FROM TO` positionals would need to select the same request groups, so the caller
# hands it straight to the unmodified `render_msgs`.
#
# Raises UnknownRequestNumberError when req_from/req_to names no marker at all, and
# AmbiguousRequestNumberError when it names MORE than one — proven possible even without a
# restart: a re-fire that adds no NEW msg opens its own group (a start_index no earlier group
# used) but `_running_request_numbers`' counter does not advance for a non-adding boundary, so
# that group's owner is assigned the SAME number as the group before it. A genuine restart can
# produce the identical symptom when the restarted boundary itself adds nothing. Refusing to guess
# either way is the point — see the callers in __main__.py for the reported message.
def request_msg_range(markers: dict, req_from: int, req_to: int, last_msg_index: int) -> tuple:
    by_number: dict = {}
    for msg_index, marker in markers.items():
        by_number.setdefault(marker["number"], []).append(msg_index)
    for number in (req_from, req_to):
        candidates = by_number.get(number)
        if not candidates:
            raise UnknownRequestNumberError(f"REQ {number} not found")
        if len(candidates) > 1:
            indices = ", ".join(str(i) for i in sorted(candidates))
            raise AmbiguousRequestNumberError(
                f"REQ {number} is ambiguous — msg indices {indices} all carry it "
                f"(a re-fire or restart repeated the number; refusing to guess)")
    start = by_number[req_from][0]
    to_start = by_number[req_to][0]
    later_starts = sorted(idx for idx in markers if idx > to_start)
    end = later_starts[0] - 1 if later_starts else last_msg_index
    return start, end


# Convenience wrapper: builds `request_markers` from `boundaries` and delegates to
# `request_msg_range` — the one call `__main__.py` needs for `msgs --req`.
def resolve_req_range(boundaries: list, req_from: int, req_to: int, last_msg_index: int) -> tuple:
    markers = request_markers(boundaries or [])
    return request_msg_range(markers, req_from, req_to, last_msg_index)


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


# Load everything a command needs for one session: the last request's payload plus its msg rows
def load_timeline(session: dict) -> dict:
    original = session["streams"].get("original")
    if original is None:
        raise FileNotFoundError(f"no _original stream for {session['stem']}")
    entry, line_bytes, skipped = load_last_request(original)
    if entry is None:
        raise ValueError(f"no non-haiku request line in {original.name}")
    payload = entry.get("payload", {}) or {}
    family = infer_family(entry.get("model", ""))
    forwarded = session["streams"].get("forwarded")
    boundaries = request_boundaries(forwarded, family) if forwarded else []
    return {
        "session": session,
        "entry": entry,
        "payload": payload,
        "family": family,
        "line_bytes": line_bytes,
        "haiku_lines_skipped": skipped,
        "turns": build_turns(payload),
        "boundaries": boundaries,
        "turn_times": build_turn_times(boundaries),
    }
