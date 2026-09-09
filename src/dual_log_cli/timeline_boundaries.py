# INFRASTRUCTURE
import json
from pathlib import Path

from ..proxy.logging import _delta_hash
from .reader import infer_family, iter_jsonl

# The per-request billing header: a hash plus the previous request id, changing on every request
# by construction. It never invalidates the prompt cache, so it is excluded from the changed/new
# delta lines on every request but the first (see process-docs/cache/).
_BILLING_HEADER_SYS_INDEX = 0


# FUNCTIONS


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
