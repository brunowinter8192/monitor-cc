# INFRASTRUCTURE
from .render_format import _clock
from .timeline_boundaries import _BILLING_HEADER_SYS_INDEX, _system_block_chars, _tool_chars
from .timeline_markers import request_markers

# Fixed columns of the `[idx] role type chars` msg line — reused to keep a block sub-line's chars
# figure right-aligned to the same column the parent line uses.
_MSG_PREFIX_WIDTH = 12  # "[idx] role  "
_MSG_LABEL_WIDTH = 20
_MSG_CHARS_WIDTH = 6
_BLOCK_INDENT = "        "  # 8 spaces — never matches `^[`, so `grep '^\['` keeps selecting msg lines only
_BLOCK_LABEL_WIDTH = _MSG_PREFIX_WIDTH + _MSG_LABEL_WIDTH - len(_BLOCK_INDENT)


# FUNCTIONS


# msgs: request groups — one REQ separator, then the msgs that request added. The msg line is
# `[idx] role type chars`, and a single-block msg gets nothing further. A multi-block msg shows its
# block COUNT in place of a type — the aggregated type would name just one of the blocks it stands
# for — and is followed by one indented sub-line per block: its label (already carrying the tool
# name or the `!err` marker via `timeline._block_label`) and its own char count, right-aligned to
# the same column the parent line's chars use. That is what makes the count legible: a 3,862c msg
# that is 2,451c thinking and 1,129c Bash input reads very differently from one that is mostly tool
# output. Pane grammar: role clipped to 4 chars. Chars carry the pane's `1,234c` spelling rather
# than fmt_chars' `1.2k`, since this view is for locating a msg by size, not for skimming
# magnitudes. The 6-wide chars column fits every value up to 99,999c; a wider one right-aligns past
# it and pushes its own line out by a character rather than truncating.
#
# A separator is emitted immediately before the first msg of its group that is actually PRINTED, so
# a group with no printed msgs (out of range, or trailing re-fires past the last msg) emits nothing.
# The FIRST printed msg is special: a FROM that lands mid-group would otherwise leave it with no
# separator at all, so it falls back to the group that GOVERNS it — the nearest one opening at or
# before it. A session whose _forwarded stream is missing or yields no boundaries prints no
# separators at all, which is exactly the pre-separator output.
#
# Directly under a separator, `_req_delta_lines` lists the system blocks and tools that request's
# `system_delta`/`tools_delta` named (`timeline.request_boundaries`, computed against the previous
# request of the same model family) — the prompt-cache prefix a rebuild most often traces back to.
# The family's first request lists every sys/tool block, no tag; a later request lists only what
# changed or is new, tagged accordingly, and prints no sys/tool lines at all when nothing did. The
# per-request billing header (system index 0) is excluded from that comparison on every request but
# the first — it changes on every request by construction and never invalidates the cache (see
# process-docs/cache/). A re-fire group shows only the OWNER boundary's lines, matching the
# timestamp and usage the separator itself carries.
#
# usage_by_flow is {flow_id: (cache_read, cache_creation)} from usage.build_usage_by_flow, keyed
# on the group owner's flow_id; a group whose flow_id is absent (usage unresolved, or no usage
# joined for the session at all) prints the separator without CR/CC — never a placeholder.
#
# overlay is {(msg_idx, blk_idx): {stripped, injected, req}} from overlay.build_overlay — the SAME
# dict `expand` uses, now also read here. A block with neither stripped nor injected text appends
# nothing, which is what keeps an untouched line byte-identical to the pre-overlay output; a
# transformed one appends "  −N +M → Wc" (chars stripped, chars injected, resulting wire size),
# plus " by REQ n" when the request that performed the transform differs from the group's own —
# the `expand` case where a msg arrives under one REQ and is overwritten by a later one.
#
# sys_tool_overlay is (sys_overlay, tools_overlay) from overlay.build_sys_tool_overlay (2026-09-04),
# read alongside `overlay` here. Its coordinates carry the SAME `−N +M → Wc` tail a msg/block line
# does, and a sys/tool line's leading chars column switches meaning to match: the ORIGINAL
# (client-sent) size, looked up by index/name in `data["payload"]`'s own system/tools lists — the
# last request's own copy, which the whole session's tool/system content is verified stable
# against (see `process-docs/dual_log_cli/`) — rather than the current wire size `_sys_lines`/
# `_tool_lines` compute. System index 0 (the billing header) is the one exception: it changes on
# EVERY request by construction, so it keeps its wire chars and no tail, unconditionally, exactly as
# before this feature. The tail's own wire figure `W` is always the MEASURED wire chars (`_tool_lines`/
# `_sys_lines`' own figure, 0 for a tool with no wire entry at all) — never derived from the
# overlay's recorded stripped/injected text, whose units (raw description characters) do not match a
# tool's JSON-encoded chars; see `_delta_line`. A tool the proxy stripped WHOLE never appears in the
# wire tools_delta at all (it is simply absent both before and after), so it never gets a line today;
# when the overlay names one, `_req_delta_lines` synthesizes a standalone `tool[Name]` line for it
# instead, full strip and wire 0 (e.g. `tool[Agent]  3,172c  −3,172 +0 → 0c`) — attached to the
# marker whose OWN flow_id the overlay recorded, never guessed onto the wrong separator. Absent,
# unresolvable, or untouched coordinates fall back to exactly the pre-2026-09-04 wire-chars line,
# byte-identical.
def render_msgs(data: dict, start: int, end: int, usage_by_flow: dict = None,
                overlay: dict = None, sys_tool_overlay: tuple = None) -> str:
    markers = request_markers(data.get("boundaries") or [])
    payload = data.get("payload") or {}
    orig_system = payload.get("system", []) or []
    orig_tools = payload.get("tools", []) or []
    sys_overlay, tools_overlay = sys_tool_overlay or ({}, {})
    lines = []
    group_req = None
    for offset, msg in enumerate(data["turns"][start:end + 1]):
        marker = markers.get(msg["index"])
        if marker is None and offset == 0:
            marker = _governing_marker(markers, msg["index"])
        if marker is not None:
            lines.append(_req_separator(marker, usage_by_flow))
            lines.extend(_req_delta_lines(marker, orig_system, orig_tools, sys_overlay, tools_overlay, marker["number"]))
            group_req = marker["number"]
        blocks = msg["blocks"]
        label = blocks[0]["type"] if len(blocks) == 1 else f"{len(blocks)} blocks"
        chars_value = msg["chars"]
        chars = f"{chars_value:,}c"
        tail = _msg_delta_tail(msg["index"], blocks, chars_value, overlay, group_req)
        lines.append(f"[{msg['index']:3d}] {msg['role'][:4]:<4}  {label:<{_MSG_LABEL_WIDTH}}{chars:>{_MSG_CHARS_WIDTH}}{tail}")
        if len(blocks) > 1:
            lines.extend(_block_sub_lines(msg["index"], blocks, overlay, group_req))
    return "\n".join(lines) + "\n"


# The separator's sys/tool lines — one indented line per system block / tool the OWNING request's
# system_delta/tools_delta named (timeline.request_boundaries computes these per boundary; a
# marker carries its owner's copy). Empty for a request with no such delta at all — the billing
# header (sys[0]) excluded on every request but the first is what makes that the common case. Same
# indent/column layout as a block sub-line, tagged "  changed"/"  new" for anything but the
# family's first request, which carries no tag at all. A tool item can also carry `chars is None`
# ("removed" — the name-based tool comparison's tag for a tool no longer present at all): that item
# skips the chars column entirely rather than printing a size for content that no longer exists.
#
# Since 2026-09-04 each line's leading chars is looked up in the ORIGINAL system/tools lists
# (`orig_system`/`orig_tools`, from `data["payload"]`) by index/name, falling back to the item's own
# wire chars when the lookup can't resolve — which is always the case for a hand-built test fixture
# carrying no `"payload"` key at all, keeping every existing check byte-identical. The ONE exception
# is system index 0, the per-request billing header (`_BILLING_HEADER_SYS_INDEX`): it changes on
# EVERY request by construction, so the last request's own copy is not a valid "original" for any
# OTHER request's sys[0] line — it is left completely untouched (wire chars, no tail), exactly like
# before this feature. `sys_overlay`/`tools_overlay` (`overlay.build_sys_tool_overlay`) attach a
# `_delta_tail` when they cover a coordinate (2026-09-04, corrected): `W` is the MEASURED wire chars
# (`item["chars"]`, `_tool_lines`/`_sys_lines`' own JSON/text-length figure — 0 for a whole-stripped
# tool, which never has a wire item at all) rather than a derived guess, since a tool's original
# chars is a JSON-encoded size while its recorded stripped/injected TEXT is raw description length —
# not commensurable, so deriving `W` from them (the first cut of this feature) printed a wrong wire
# figure for every desc-stripped tool. `S` is instead DERIVED as `original − W + I`, which makes
# `_delta_tail`'s own internal arithmetic reconstruct exactly the measured `W` again. A whole-stripped
# tool with no wire entry at all is synthesized as its own line, appended after the wire-based tool
# lines, restricted to the overlay's OWN owning flow_id so it lands under the correct separator
# (never guessed from a req NUMBER alone, which a re-fire could make ambiguous) — skipped silently
# when the tool's name can't be resolved in `orig_tools` (fail toward showing nothing rather than a
# guessed size).
def _req_delta_lines(marker: dict, orig_system: list, orig_tools: list,
                     sys_overlay: dict, tools_overlay: dict, group_req) -> list:
    lines = []
    tools_by_name = {t.get("name", "?"): t for t in orig_tools if isinstance(t, dict)}
    seen_names = set()
    for item in marker.get("sys_lines") or []:
        idx = _sys_index_from_label(item["label"])
        if idx == _BILLING_HEADER_SYS_INDEX:
            lines.append(_delta_line(item, None, None, group_req))
            continue
        original = _system_block_chars(orig_system[idx]) if 0 <= idx < len(orig_system) else None
        lines.append(_delta_line(item, original, sys_overlay.get(str(idx)), group_req))
    for item in marker.get("tool_lines") or []:
        name = _tool_name_from_label(item["label"])
        seen_names.add(name)
        if item.get("chars") is None:
            lines.append(f"{_BLOCK_INDENT}{item['label']:<{_BLOCK_LABEL_WIDTH}}  {item['tag']}")
            continue
        original = _tool_chars(tools_by_name[name]) if name in tools_by_name else None
        lines.append(_delta_line(item, original, tools_overlay.get(name), group_req))
    for name in sorted(tools_overlay):
        slot = tools_overlay[name]
        if name in seen_names or not slot.get("whole") or slot.get("flow_id") != marker.get("flow_id"):
            continue
        if name not in tools_by_name:
            continue
        original = _tool_chars(tools_by_name[name])
        lines.append(_delta_line({"label": f"tool[{name}]", "tag": None}, original, slot, group_req))
    return lines


# "sys[3]" -> 3
def _sys_index_from_label(label: str) -> int:
    return int(label[len("sys["):-1])


# "tool[Foo]" -> "Foo" ("tool[" is 5 chars — distinct from a block's "tool_use[...]" label)
def _tool_name_from_label(label: str) -> str:
    return label[len("tool["):-1]


# One sys/tool delta line: leading chars (original size when resolved, else the item's own wire
# chars — see `_req_delta_lines`), an optional `_delta_tail` when `slot` covers this coordinate, and
# the item's own tag suffix (changed/new), if any.
#
# `W` (the tail's wire figure) is the MEASURED value — `item["chars"]` (the existing wire chars
# `_tool_lines`/`_sys_lines` already compute) for a wire-based line, or 0 for a whole-stripped tool
# (`slot["whole"]`, no wire item at all) — never derived from the overlay's recorded stripped/
# injected TEXT, whose units do not match a JSON-encoded tool's chars (a tool's chars is
# `len(json.dumps(tool))`; its recorded stripped text is the raw description substring — the two do
# not correspond 1:1). `S` is instead derived as `original − W + I`, so `_delta_tail`'s own internal
# `chars − S + I` reconstructs exactly this measured `W` again — self-consistent by construction,
# and correct because `W` itself was never guessed.
def _delta_line(item: dict, original_chars, slot, group_req) -> str:
    label = f"{item['label']:<{_BLOCK_LABEL_WIDTH}}"
    chars_value = original_chars if original_chars is not None else item["chars"]
    chars = f"{chars_value:,}c"
    tail = ""
    if slot:
        wire_chars = 0 if slot.get("whole") else item["chars"]
        injected_chars = sum(len(t) for t in slot.get("injected") or [])
        stripped_chars = chars_value - wire_chars + injected_chars
        if stripped_chars or injected_chars:
            tail = _delta_tail(stripped_chars, injected_chars, chars_value, slot.get("req"), group_req)
    tag_suffix = f"  {item['tag']}" if item.get("tag") else ""
    return f"{_BLOCK_INDENT}{label}{chars:>{_MSG_CHARS_WIDTH}}{tail}{tag_suffix}"


# One indented sub-line per block of a multi-block msg — label and chars, plus the block's own
# strip/inject delta when the overlay touched it, no previews
def _block_sub_lines(msg_index: int, blocks: list, overlay: dict, group_req) -> list:
    lines = []
    for blk_index, block in enumerate(blocks):
        chars_value = block["chars"]
        chars = f"{chars_value:,}c"
        totals = _block_overlay_totals(overlay, msg_index, blk_index)
        if totals:
            stripped_chars, injected_chars, req = totals
            tail = _delta_tail(stripped_chars, injected_chars, chars_value, req, group_req)
        else:
            tail = ""
        lines.append(f"{_BLOCK_INDENT}{block['label']:<{_BLOCK_LABEL_WIDTH}}{chars:>{_MSG_CHARS_WIDTH}}{tail}")
    return lines


# The msg-level delta tail: the SUM of stripped/injected chars over every block the overlay
# touched, measured against the msg's own printed chars value (so the arithmetic on that one line
# is self-consistent regardless of how msg-level chars relate to the sum of block chars
# elsewhere). "" when no block of this msg was touched at all.
#
# "by REQ" is added only when every touched block shares the SAME request — a msg split across
# two transforming requests has never been observed in the corpus (measured: 0 of 1949 transformed
# msgs), and summarizing an ambiguous case with one REQ number would be a guess, so it is omitted
# instead; the per-block sub-lines still carry it individually.
def _msg_delta_tail(msg_index: int, blocks: list, chars_value: int, overlay: dict, group_req) -> str:
    total_stripped = 0
    total_injected = 0
    reqs = set()
    touched = False
    for blk_index in range(len(blocks)):
        totals = _block_overlay_totals(overlay, msg_index, blk_index)
        if totals is None:
            continue
        touched = True
        stripped_chars, injected_chars, req = totals
        total_stripped += stripped_chars
        total_injected += injected_chars
        if req is not None:
            reqs.add(req)
    if not touched:
        return ""
    req = next(iter(reqs)) if len(reqs) == 1 else None
    return _delta_tail(total_stripped, total_injected, chars_value, req, group_req)


# One block's overlay totals as (stripped_chars, injected_chars, req), or None when the overlay
# has nothing for this coordinate or recorded zero chars on both sides (a strip/inject slot with
# only empty strings, which build_overlay's own _texts already filters out, but zero is treated as
# untouched here too rather than trusted blindly).
def _block_overlay_totals(overlay: dict, msg_index: int, blk_index: int):
    slot = (overlay or {}).get((msg_index, blk_index))
    if not slot:
        return None
    stripped_chars = sum(len(t) for t in slot.get("stripped") or [])
    injected_chars = sum(len(t) for t in slot.get("injected") or [])
    if not stripped_chars and not injected_chars:
        return None
    return stripped_chars, injected_chars, slot.get("req")


# "  −N +M → Wc" appended after a chars column — N/M/W digit-grouped like every other chars figure
# in `msgs`, the real minus sign (U+2212) rather than a hyphen, and W computed as
# chars − stripped + injected. " by REQ n" only when that request differs from the group's own.
def _delta_tail(stripped_chars: int, injected_chars: int, chars_value: int, req, group_req) -> str:
    wire_chars = chars_value - stripped_chars + injected_chars
    tail = f"  −{stripped_chars:,} +{injected_chars:,} → {wire_chars:,}c"
    if req is not None and req != group_req:
        tail += f" by REQ {req}"
    return tail


# The group covering a msg index — the nearest one opening at or before it. None when the msg sits
# below every boundary, which happens only if the _forwarded stream does not reach back that far.
def _governing_marker(markers: dict, index: int):
    starts = [s for s in markers if s <= index]
    return markers[max(starts)] if starts else None


# One REQ separator: the request that opened this msg index, when it was sent, and — when
# resolved — its prompt-cache usage. The re-fire suffix stays OUTSIDE the closing "──", exactly
# where it sat before usage was added; CR/CC sits inside, between the clock and the "──".
def _req_separator(marker: dict, usage_by_flow: dict = None) -> str:
    refires = marker["refires"]
    extra = ""
    if refires:
        extra = f"  (+{refires} re-fire{'s' if refires != 1 else ''})"
    usage = (usage_by_flow or {}).get(marker.get("flow_id"))
    usage_part = f"  {_fmt_usage(*usage)}" if usage else ""
    return f"── REQ {marker['number']}  {_clock(marker['timestamp'])}{usage_part} ──{extra}"


# "CR 9,096  CC 1,928" — cache_read_input_tokens / cache_creation_input_tokens of the response
# that owns the group, same 1,234 digit-grouping the msg lines use for chars
def _fmt_usage(cache_read: int, cache_creation: int) -> str:
    return f"CR {cache_read:,}  CC {cache_creation:,}"
