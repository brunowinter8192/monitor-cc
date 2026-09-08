# INFRASTRUCTURE
from .reader import local_datetime
from .timeline import request_markers, _system_block_chars, _tool_chars, _BILLING_HEADER_SYS_INDEX

# FUNCTIONS


# Char count as a short human string
def fmt_chars(count: int) -> str:
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}k"
    return str(count)


# "YYYY-MM-DD HH:MM:SS" LOCAL wall clock for a UTC ISO timestamp (2026-09-04: was a raw
# `timestamp[:19]` UTC substring — see `reader.local_datetime`, the one shared conversion point).
# "?" for an empty/unparseable timestamp, same width (19 chars) either way.
def fmt_timestamp(timestamp: str) -> str:
    dt = local_datetime(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "?"


# One line per session, newest first
def render_sessions(sessions: list) -> str:
    if not sessions:
        return "no sessions found\n"
    context_width = max(len(s["context"]) for s in sessions)
    # SESSION is the last column — left unpadded so no line carries trailing whitespace
    lines = [f"{'START':19}  {'CONTEXT':{context_width}}  SESSION"]
    for session in sessions:
        lines.append(
            f"{fmt_timestamp(session['start']):19}  "
            f"{session['context']:{context_width}}  "
            f"{session['stem']}"
        )
    lines.append("")
    lines.append(f"{len(sessions)} sessions")
    return "\n".join(lines) + "\n"


# Fixed columns of the `[idx] role type chars` msg line — reused to keep a block sub-line's chars
# figure right-aligned to the same column the parent line uses.
_MSG_PREFIX_WIDTH = 12  # "[idx] role  "
_MSG_LABEL_WIDTH = 20
_MSG_CHARS_WIDTH = 6
_BLOCK_INDENT = "        "  # 8 spaces — never matches `^[`, so `grep '^\['` keeps selecting msg lines only
_BLOCK_LABEL_WIDTH = _MSG_PREFIX_WIDTH + _MSG_LABEL_WIDTH - len(_BLOCK_INDENT)


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


# Search result: header plus one line per matching block
# Search results across one or more sessions. results is [(session, hits), …] in listing order,
# already filtered to sessions that HAVE hits. The term line is printed once overall; each session
# then contributes its own "session <stem>" line plus its hit lines. skipped counts sessions whose
# timeline could not be loaded — reported only when non-zero, so a clean run stays clean.
#
# A hit line is `#msg role label  chars` — msg index, role, block label, and the block's original
# chars (`f"{n:,}c"`, the same digit-grouped spelling `msgs`' block sub-lines use for the same
# value) — an eyeball filter for deciding which msg is worth `expand`ing, not a text preview: a
# genuine small artifact and a large prose hit differ in chars at a glance, no snippet needed.
def render_search(term: str, case_sensitive: bool, results: list, skipped: int = 0) -> str:
    mode = "case-sensitive" if case_sensitive else "case-insensitive"
    lines = [f'term      "{term}"  ({mode})', ""]
    if not results:
        lines.append("no match")
        return "\n".join(lines + _skipped_lines(skipped)) + "\n"
    # one width across ALL sessions, so hit lines stay aligned when several sessions are shown
    label_width = max(len(hit["label"]) for _session, hits in results for hit in hits)
    chars_width = max(len(f"{hit['chars']:,}c") for _session, hits in results for hit in hits)
    for session, hits in results:
        lines.append(f"session   {session['stem']}")
        for hit in hits:
            chars = f"{hit['chars']:,}c"
            lines.append(
                f"#{hit['turn']:<4} {hit['role']:9} {hit['label']:{label_width}}  "
                f"{chars:>{chars_width}}"
            )
        lines.append("")
    return "\n".join(lines[:-1] + _skipped_lines(skipped)) + "\n"


# Trailing note about unreadable sessions; empty when nothing was skipped
def _skipped_lines(skipped: int) -> list:
    if not skipped:
        return []
    return ["", f"({skipped} session{'s' if skipped != 1 else ''} skipped — timeline could not be loaded)"]


# Fixed width of the REQ number field — a 4-char left-justified number directly followed by the
# clock, no extra space needed (the padding itself is the gap): "REQ 1   20:16:02". Same narrow-
# default-with-occasional-jog convention `msgs`' own chars column uses — a 5-digit REQ number
# pushes its own clock one column right rather than widening every shorter line permanently.
_REQ_NUMBER_WIDTH = 4


# reqs: one line per session ("session <stem>"), then one "REQ n   HH:MM:SS" line per request —
# the exact numbers and timestamps `msgs`' own separators print, in the SAME order (msg-index
# order, which is also chronological order within the session) — re-fires already collapsed and a
# restart already handled exactly the way `request_markers` handles it for `msgs`, since this is
# the SAME dict, just walked here instead of interleaved with msg lines. No other columns, no
# counts, no CR/CC — `results` is [(session, boundaries), …] in listing order (already scope/date/
# family-filtered and skip-on-unloadable exactly like `search`), `skipped` the same trailing note.
#
# `gap_minutes` (2026-09-04, `--gap MINUTES`) is additive and `None` by default, reproducing the
# plain listing byte-for-byte. When set, `_gap_lines` replaces the full per-session listing with
# only the REQs bracketing a qualifying gap — see `_bracket_gap_lines` for the exact rule.
#
# `rebuild`/`drop` (later addition, both `False` by default — reproduces the pre-existing listing
# byte-for-byte when neither is set, `usage_by_stem` unused in that case) route through the
# `_entries_for_session`/`_rebuild_drop_lines`/`_rebuild_drop_gap_lines` path instead — see the
# comment above `_rebuild_drop_qualifies` for the shared predicate both this and `render_reqs_merged`
# apply. `--drop`'s predecessor is always the SAME session's own previous REQ (`_entries_for_session`
# precomputes it while still walking one session in isolation) — trivially true here since this
# function never merges sessions to begin with.
def render_reqs(results: list, skipped: int = 0, gap_minutes: int = None,
                usage_by_stem: dict = None, rebuild: bool = False, drop: bool = False) -> str:
    if not results:
        lines = ["no sessions found"]
        return "\n".join(lines + _skipped_lines(skipped)) + "\n"
    filtering = rebuild or drop
    lines = []
    for session, boundaries in results:
        lines.append(f"session {session['stem']}")
        markers = request_markers(boundaries or [])
        if filtering:
            usage_map = (usage_by_stem or {}).get(session.get("stem", ""), {})
            entries = _entries_for_session(markers, usage_map)
            if gap_minutes is None:
                lines.extend(_rebuild_drop_lines(entries, rebuild, drop))
            else:
                lines.extend(_rebuild_drop_gap_lines(entries, gap_minutes, rebuild, drop))
        else:
            ordered = [(msg_index, markers[msg_index]) for msg_index in sorted(markers)]
            if gap_minutes is None:
                lines.extend(_req_line(marker) for _msg_index, marker in ordered)
            else:
                lines.extend(_gap_lines(ordered, gap_minutes))
        lines.append("")
    return "\n".join(lines[:-1] + _skipped_lines(skipped)) + "\n"


# reqs --merged (2026-09-04): ALL sessions in scope combined into ONE chronological REQ chain,
# instead of one listing per session — because the prompt cache hangs on the shared prefix (system
# blocks + tools) every worker of a project sends, so a request from ANY session in scope keeps
# that prefix warm for every OTHER one; the gap that actually matters for cache health is between
# consecutive requests of ANY session, not within one. "merged <N> sessions" header (N = sessions
# that actually loaded, i.e. `len(results)` — `skipped` is reported separately, as always), then
# either every REQ across every session as a `_req_line` tagged with its own session (plain
# listing), or, with `gap_minutes` set, `_bracket_gap_lines` over that SAME merged, globally-sorted
# sequence — which is what makes a within-session gap that a DIFFERENT session's request happens
# to fall inside no longer qualify (its two new neighbors are the bridging request, not each
# other), and a gap that only exists ACROSS sessions qualify correctly, with no special-casing
# either way: both are just consequences of pairing GLOBAL chronological neighbors.
#
# `rebuild`/`drop` route through the SAME filtered entry list, `usage_by_stem` threaded into
# `_merged_entries` (which threads it further into each session's own `_entries_for_session` call).
# `--drop`'s predecessor stays the SAME session's own previous REQ even here — the merged chain only
# changes ORDER (chronological interleaving) and adds the `  <tag>` column; the shared prefix a
# cache-drop is measuring is system blocks + tools, never the conversation itself, so comparing one
# session's CR against a DIFFERENT session's CR+CC is not meaningful (see Gotchas). `--gap` is the
# one thing that DOES use cross-session chronological neighbors here, via `_bracket_gap_positions`
# reading `entries[i][0]` (the dt) — unaffected by this, since gap health and drop health measure
# different things.
def render_reqs_merged(results: list, skipped: int = 0, gap_minutes: int = None,
                       usage_by_stem: dict = None, rebuild: bool = False, drop: bool = False) -> str:
    if not results:
        lines = ["no sessions found"]
        return "\n".join(lines + _skipped_lines(skipped)) + "\n"
    filtering = rebuild or drop
    entries = _merged_entries(results, usage_by_stem if filtering else None)
    lines = [f"merged {len(results)} sessions"]
    if filtering:
        if gap_minutes is None:
            lines.extend(_rebuild_drop_lines(entries, rebuild, drop))
        else:
            lines.extend(_rebuild_drop_gap_lines(entries, gap_minutes, rebuild, drop))
    elif gap_minutes is None:
        lines.extend(_req_line(marker, tag=tag) for _dt, marker, tag, _usage, _prev_usage in entries)
    else:
        lines.extend(_bracket_gap_lines(entries, gap_minutes))
    return "\n".join(lines + _skipped_lines(skipped)) + "\n"


# One "REQ n   HH:MM:SS" line, optionally carrying "  <tag>" (--merged, e.g. a worker name), then
# "  +Nm" (--gap, on the AFTER line of a qualifying pair), then "  CR c  CC c[  −N]" (--rebuild/
# --drop) — clock, tag, gap tail, usage tail, in that order, so every combination reads as a single
# growing tail rather than needing its own layout.
def _req_line(marker: dict, tag: str = "", gap_tail: str = "", usage_tail: str = "") -> str:
    tag_part = f"  {tag}" if tag else ""
    return f"REQ {marker['number']:<{_REQ_NUMBER_WIDTH}}{_clock(marker['timestamp'])}{tag_part}{gap_tail}{usage_tail}"


# The session's own short --merged tag: its context after the LAST "/" — a worker's name
# ("worker/monitor_cc/proxy-tn-wrap" -> "proxy-tn-wrap") or a main session's project
# ("opus/monitor_cc" -> "monitor_cc") — no shape-specific branching needed, both contexts happen
# to put the identifying piece last. Falls back to the stem when context is empty (never crashes
# on a context with no "/" at all — rsplit on a slash-free string returns it unchanged).
def _session_tag(session: dict) -> str:
    context = session.get("context") or ""
    return context.rsplit("/", 1)[-1] if context else session.get("stem", "")


# One session's own markers as [(dt, marker, tag, usage, prev_usage), …], in msg-index order
# (already chronological within a session) — the shared entry shape `_rebuild_drop_lines`/
# `_rebuild_drop_gap_lines`/`_bracket_gap_positions` all consume, whether built here for a single
# session or flattened across many by `_merged_entries`. `usage` is `usage_map.get(marker's
# flow_id)`, `None` when the map is empty/absent or the flow never resolved — exactly what
# `_rebuild_drop_qualifies` reads as "unresolved, skip". `prev_usage` is PRECOMPUTED here, while
# this function is still walking ONE session in msg-index order — it is this marker's own session's
# immediately preceding request's `usage` (`None` for the session's own first request) — and stays
# fixed on the tuple from this point on, regardless of whatever order the entry later ends up in
# once `_merged_entries` flattens and re-sorts across sessions by `dt`. This is what makes a
# `--drop` predecessor always the SAME session's own previous request, even under `--merged`: the
# shared prompt-cache prefix a cache drop is measuring is system blocks + tools, never the
# conversation itself, so comparing one session's CR against a DIFFERENT session's CR+CC would be
# meaningless (see Gotchas — this was corrected after an initial cut compared cross-session
# chronological neighbors instead). A marker whose timestamp fails to parse is dropped, same as
# `_merged_entries` already does for its own chronological-ordering need — real dual-log timestamps
# are never malformed, so this never fires on genuine data; such a drop also skips one position in
# the same-session `prev_usage` chain, exactly like a genuine `_is_sidecar` exclusion would.
def _entries_for_session(markers: dict, usage_map: dict, tag: str = "") -> list:
    entries = []
    prev_usage = None
    for msg_index in sorted(markers):
        marker = markers[msg_index]
        dt = local_datetime(marker["timestamp"])
        if dt is None:
            continue
        usage = (usage_map or {}).get(marker.get("flow_id"))
        entries.append((dt, marker, tag, usage, prev_usage))
        prev_usage = usage
    return entries


# --merged's flattened, chronologically SORTED [(dt, marker, tag, usage, prev_usage), …] across
# every session in `results` — the merge point every render (plain, --gap, and --rebuild/--drop)
# built on top of it shares. `usage_by_stem` (a --rebuild/--drop-only param, `None` for the
# plain/--gap paths, which never read the usage/prev_usage elements) is `{session_stem: {flow_id:
# (cr, cc)}}` — looked up once per session here rather than per marker, then threaded through
# `_entries_for_session`, which computes `prev_usage` PER SESSION before this function's own sort
# ever runs — the sort below only ever reorders entries for DISPLAY/--gap purposes, it never
# recomputes or reassigns which predecessor a --drop check reads.
def _merged_entries(results: list, usage_by_stem: dict = None) -> list:
    entries = []
    for session, boundaries in results:
        tag = _session_tag(session)
        usage_map = (usage_by_stem or {}).get(session.get("stem", ""), {}) if usage_by_stem else {}
        markers = request_markers(boundaries or [])
        entries.extend(_entries_for_session(markers, usage_map, tag))
    entries.sort(key=lambda entry: entry[0])
    return entries


# `--gap MINUTES`'s candidate POSITIONS, as {position: gap_tail} — the pure selection half of
# `_bracket_gap_lines`, split out so `--rebuild`/`--drop` can filter the exact same candidate set
# ("the lines --gap would print, before-line included") before rendering, rather than duplicating
# the pairing walk. For every consecutive pair whose elapsed time is >= gap_minutes (whole minutes,
# floored — `total_seconds() // 60`, never rounded, so a boundary case is exact: a gap of precisely
# N minutes qualifies for `--gap N`, one second less does not), both positions are recorded — the
# before position only if not already recorded (so a position that is already the AFTER of an
# earlier qualifying pair keeps that tail rather than being reset to tail-less), the after position
# always with `  +{elapsed}m`. `entries` is `[(dt, marker, tag, usage, prev_usage), …]`, already
# sorted and already stripped of unparseable timestamps by the caller — this function reads ONLY
# `dt` (chronological, cross-session neighbors are exactly what `--gap` wants to measure, unlike
# `--drop`, whose predecessor never crosses a session boundary — see `_entries_for_session`).
def _bracket_gap_positions(entries: list, gap_minutes: int) -> dict:
    positions = {}
    for i in range(len(entries) - 1):
        dt_before = entries[i][0]
        dt_after = entries[i + 1][0]
        elapsed = int((dt_after - dt_before).total_seconds() // 60)
        if elapsed < gap_minutes:
            continue
        positions.setdefault(i, "")
        positions[i + 1] = f"  +{elapsed}m"
    return positions


# `--gap MINUTES`: only the REQs bracketing a qualifying CONSECUTIVE gap, in chronological order —
# shared core for both the per-session path (`_gap_lines`, tag always "") and `--merged`
# (`render_reqs_merged`, tag is each entry's own session). Positions come from
# `_bracket_gap_positions`; iterating them in ascending order reproduces the exact print order the
# original single-pass walk did — a REQ that is the AFTER of one qualifying pair and the BEFORE of
# the next appears exactly once (it is the SAME dict key either way), carrying only its AFTER tail,
# since `_bracket_gap_positions` never resets an already-recorded position back to tail-less.
#
# Fewer than two entries (a lone session with 0-1 requests, or an empty merge) yields `[]` here —
# the caller still prints its own header line(s), just no REQ lines beneath, which is what lets a
# reader see a session (or the whole merge) WAS checked rather than silently vanishing.
def _bracket_gap_lines(entries: list, gap_minutes: int) -> list:
    positions = _bracket_gap_positions(entries, gap_minutes)
    lines = []
    for position in sorted(positions):
        _dt, marker, tag, _usage, _prev_usage = entries[position]
        lines.append(_req_line(marker, tag=tag, gap_tail=positions[position]))
    return lines


# `--gap MINUTES`, per-session path: `ordered` is [(msg_index, marker), …] sorted by msg index
# (chronological within one session) — normalised into `_bracket_gap_lines`' shared entry shape
# (untagged, usage-less; unparseable timestamps dropped here, same as `_merged_entries` does,
# rather than skipping only the PAIRS touching them — the two valid neighbors either side of a bad
# one end up compared to each other directly instead of neither being compared at all; real
# dual-log timestamps are never malformed, so this only changes a never-observed theoretical case).
def _gap_lines(ordered: list, gap_minutes: int) -> list:
    entries = []
    for _msg_index, marker in ordered:
        dt = local_datetime(marker["timestamp"])
        if dt is None:
            continue
        entries.append((dt, marker, "", None, None))
    return _bracket_gap_lines(entries, gap_minutes)


# `--rebuild`/`--drop`: usage-driven REQ filtering, orthogonal to `--gap`/`--merged`/scope. Both
# read the SAME per-request CR/CC `msgs` resolves via `usage.build_usage_by_flow`
# (cache_read_input_tokens / cache_creation_input_tokens) — never re-derived here.
#
# `--rebuild` keeps only REQs where CC > CR (this request's own cache write outweighs what it read
# back — the write is the signal something upstream had to be rebuilt). `--drop` keeps only REQs n
# where CR(n) < CR(n-1) + CC(n-1) — part of the prefix the PREVIOUS request had cached (its own
# read plus what it just wrote) was NOT read again by n, meaning the cache actually cooled between
# them; exactly equal does NOT qualify (`>=` fails the condition — the STRICT inequality is what
# "not fully read back" means). "previous" is `n`'s own PRECOMPUTED `prev_usage` (the 5th tuple
# element `_entries_for_session` set while walking that request's own session in isolation) —
# ALWAYS the same session's own previous REQ, `--merged` or not: the shared prompt-cache prefix a
# cache drop is measuring is system blocks + tools, never the conversation, so comparing one
# session's CR against a DIFFERENT session's CR+CC would be meaningless (see Gotchas — this is a
# 2026-09-04 correction; an initial cut used the chronological neighbor in the merged chain
# instead, which could be a different session, and produced nonsensical shortfalls like
# `capture-crosssession`'s REQ 1 measured against `duallog-search-chars`' totals). REQ 1 of a
# session — the entry whose own `prev_usage` is `None` — never qualifies for `--drop`, regardless
# of where it lands in a `--merged` chain's chronological order.
#
# Both flags combine with AND: a REQ must satisfy every active one. A REQ whose own usage (or, for
# `--drop`, its predecessor's) does not resolve is skipped under either flag — never shown
# tail-less, never guessed. Returns `None` when the entry does not qualify, else `(cache_read,
# cache_creation, shortfall)` — `shortfall` is `None` unless `--drop` matched, in which case it is
# `CR(n-1) + CC(n-1) − CR(n)` (always positive, since the qualifying branch already proved it).
def _rebuild_drop_qualifies(usage, prev_usage, rebuild: bool, drop: bool):
    if usage is None:
        return None
    cache_read, cache_creation = usage
    if rebuild and not (cache_creation > cache_read):
        return None
    shortfall = None
    if drop:
        if prev_usage is None:
            return None
        prev_read, prev_creation = prev_usage
        prev_total = prev_read + prev_creation
        if cache_read >= prev_total:
            return None
        shortfall = prev_total - cache_read
    return cache_read, cache_creation, shortfall


# "  CR c  CC c", optionally followed by "  −N" (`--drop`'s shortfall — the real minus sign U+2212,
# digit-grouped like every other count `_delta_tail` appends, though this one counts tokens rather
# than chars).
def _usage_tail(cache_read: int, cache_creation: int, shortfall) -> str:
    tail = f"  {_fmt_usage(cache_read, cache_creation)}"
    if shortfall is not None:
        tail += f"  −{shortfall:,}"
    return tail


# `--rebuild`/`--drop` with NO `--gap`: every entry of the chronological sequence that
# `_rebuild_drop_qualifies` accepts, in order, each carrying its own `_usage_tail` — no pairing, no
# gap tail at all. `prev_usage` is read straight off the tuple (`_entries_for_session`'s own
# same-session precomputation), never re-derived from list position.
def _rebuild_drop_lines(entries: list, rebuild: bool, drop: bool) -> list:
    lines = []
    for _dt, marker, tag, usage, prev_usage in entries:
        qualifies = _rebuild_drop_qualifies(usage, prev_usage, rebuild, drop)
        if qualifies is None:
            continue
        cache_read, cache_creation, shortfall = qualifies
        lines.append(_req_line(marker, tag=tag, usage_tail=_usage_tail(cache_read, cache_creation, shortfall)))
    return lines


# `--rebuild`/`--drop` combined with `--gap M`: "the flags filter the lines --gap would print,
# before-line included" — `_bracket_gap_positions` gives that exact candidate set (with each
# position's own gap tail, if any) FIRST, then each candidate is tested against
# `_rebuild_drop_qualifies` against its OWN `prev_usage` (the tuple's precomputed same-session
# predecessor — see `_entries_for_session`), which is independent of whichever entry the GAP
# pairing happens to bracket it with (the two can differ: a `--gap`-qualifying neighbor can be a
# DIFFERENT session's request, while a `--drop` predecessor never is).
def _rebuild_drop_gap_lines(entries: list, gap_minutes: int, rebuild: bool, drop: bool) -> list:
    positions = _bracket_gap_positions(entries, gap_minutes)
    lines = []
    for position in sorted(positions):
        _dt, marker, tag, usage, prev_usage = entries[position]
        qualifies = _rebuild_drop_qualifies(usage, prev_usage, rebuild, drop)
        if qualifies is None:
            continue
        cache_read, cache_creation, shortfall = qualifies
        usage_tail = _usage_tail(cache_read, cache_creation, shortfall)
        lines.append(_req_line(marker, tag=tag, gap_tail=positions[position], usage_tail=usage_tail))
    return lines


# expand: the complete content of each selected msg in the window, plus the proxy's own
# transformations of it when an overlay is supplied. `overlay` is {(msg, blk): {stripped, injected,
# req}} from overlay.py; an empty/absent one renders exactly the pre-overlay output, which is what
# keeps an untouched msg byte-identical.
def render_expand_full(data: dict, anchor: int, start: int, end: int,
                       only: str, dumped: list, overlay: dict = None) -> str:
    msgs = data["turns"]
    times = data.get("turn_times", {})
    scope = (f"msgs {start}-{end} of 0-{len(msgs) - 1}, anchor #{anchor}, "
             f"{_window_date(data, anchor)}")
    lines = [
        f"session   {data['session']['stem']}",
        f"context   {data['session']['context']}",
        f"window    {scope}" + (f", only {only}" if only else ""),
        "",
    ]
    if not dumped:
        lines.append(f"no msg in the window matches --only {only}" if only else "window is empty")
        return "\n".join(lines) + "\n"
    for msg, blocks in dumped:
        marker = "▶" if msg["index"] == anchor else " "
        lines.append(
            f"{marker} ═══ msg #{msg['index']} {_clock(times.get(msg['index']))} "
            f"{msg['role']} {fmt_chars(msg['chars'])} chars, {len(blocks)} block(s) ═══"
        )
        for position, (label, chars, text) in enumerate(blocks):
            lines.append(f"── block {position}  {label}  {fmt_chars(chars)} chars ──")
            lines.append(text)
            lines.extend(_overlay_lines((overlay or {}).get((msg["index"], position))))
        lines.append("")
    return "\n".join(lines) + "\n"


# The proxy's transformations of one block: what it removed from the text above, and what it put
# there instead. Labels carry the meaning — this output is read by agents through pipes, so there
# is no colour anywhere in it. Empty for a block the proxy never touched.
def _overlay_lines(slot) -> list:
    if not slot:
        return []
    req = slot.get("req")
    tag = f"REQ {req}" if req else "REQ ?"
    lines = []
    for text in slot.get("stripped") or []:
        lines.append(f"── stripped by {tag} ──")
        lines.append(text)
    for text in slot.get("injected") or []:
        lines.append(f"── injected by {tag} ──")
        lines.append(text)
    return lines


# LOCAL HH:MM:SS of the request that first carried a msg; "?" when it has no reliable time
# (2026-09-04: was a raw `timestamp[11:19]` UTC substring — see `reader.local_datetime`).
def _clock(timestamp) -> str:
    dt = local_datetime(timestamp)
    return dt.strftime("%H:%M:%S") if dt else "?"


# LOCAL calendar day for the window header — the anchor's own day, else the session's start day
# (2026-09-04: was a raw `stamp[:10]` UTC substring — a request near local midnight could land on
# the wrong day otherwise; see `reader.local_datetime`).
def _window_date(data: dict, anchor: int) -> str:
    stamp = data.get("turn_times", {}).get(anchor) or data["session"].get("start", "")
    dt = local_datetime(stamp)
    return dt.strftime("%Y-%m-%d") if dt else "?"


# Fixed width of the turn number field — same narrow-default convention `reqs`' own REQ number
# field uses.
_TURN_NUMBER_WIDTH = 4
_TURN_DURATION_WIDTH = 8


# Compact human duration: "58s" under a minute, "41m24s" under an hour, "1h05m30s" at or past one
# — grep-friendly (a letter suffix per unit, no spaces) and fixed-width only where cheap (seconds
# always 2 digits once a coarser unit is present; the leading unit is not padded, since padding it
# would widen every row for a session whose turns never reach double-digit hours). "?" for an
# unresolved duration — same width class as a real value once printed via `{:>N}`.
def _fmt_duration(seconds) -> str:
    if seconds is None:
        return "?"
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{secs:02d}s"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


# "102,389" digit-grouped like every other count this package renders, "?" when unresolved.
def _fmt_tokens(tokens) -> str:
    return f"{tokens:,}" if tokens is not None else "?"


# turns <session>: one line per turn — number, the local clock of the turn's FIRST request, total
# duration, model time, tool time, request count, summed output tokens, and the prompt preview
# that opened the turn. `rows` is `timeline.build_turn_rows`'s own list — this function only lays
# it out, exactly the same division of labor `render_reqs` already has with `request_markers`. A
# row whose duration/model/tool/tokens are `None` (the turn's requests did not all resolve against
# the transcript join — see `timeline.build_turn_rows`) prints "?" in every one of those four
# columns, never a partial number; the clock and request count print regardless, since a marker's
# own send timestamp needs no transcript join at all.
def render_turns(rows: list) -> str:
    if not rows:
        return "no turns found\n"
    return "\n".join(_turn_line(row) for row in rows) + "\n"


def _turn_line(row: dict) -> str:
    duration = f"{_fmt_duration(row['duration']):>{_TURN_DURATION_WIDTH}}"
    model = f"{_fmt_duration(row['model_time']):>{_TURN_DURATION_WIDTH}}"
    tool = f"{_fmt_duration(row['tool_time']):>{_TURN_DURATION_WIDTH}}"
    tokens = f"{_fmt_tokens(row['tokens']):>9}"
    return (
        f"turn {row['number']:<{_TURN_NUMBER_WIDTH}}{_clock(row['timestamp'])}  "
        f"{duration}  model {model}  tool {tool}  "
        f"{row['requests']:>3} reqs  {tokens} tok  {row['preview']}"
    )
