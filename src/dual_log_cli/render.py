# INFRASTRUCTURE
from .discovery import stem_identity
from .reader import local_datetime
from .timeline import (
    request_markers,
    _BILLING_HEADER_SYS_INDEX,
    _group_markers_by_turn,
    _system_block_chars,
    _tool_chars,
    _turn_preview,
)

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


# One line per session, newest first. PROJECT (2026-09-10, replaces CONTEXT) is the real project
# directory `discovery.project_for_stem` resolved — a path can run much longer than the old
# `worker/<label>/<name>` rendering ever did, so the column WIDENS to fit the longest one rather
# than truncating (right-trimming a path is not acceptable — a wide column is). SESSION prints the
# stem's DISPLAY form (`discovery.display_stem`, sid8 stripped for a worker) — the on-disk stem is
# unchanged, this is presentation only, and `resolve_stem` already accepts a substring of either
# form, so a name copied from this column resolves.
def render_sessions(sessions: list) -> str:
    if not sessions:
        return "no sessions found\n"
    project_width = max(len(s["project"]) for s in sessions)
    # SESSION is the last column — left unpadded so no line carries trailing whitespace
    lines = [f"{'START':19}  {'PROJECT':{project_width}}  SESSION"]
    for session in sessions:
        lines.append(
            f"{fmt_timestamp(session['start']):19}  "
            f"{session['project']:{project_width}}  "
            f"{session['display_stem']}"
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


# reqs (2026-09-16, M6 redesign — one fixed line form, every flag a pure filter/selector over it):
# per session, `session <stem>` then every REQ under its turn separator — turn grouping is now
# ALWAYS on (the M5 `--turns` behavior, no longer opt-in; a session with no turn opener at all
# prints its REQ lines with no separators, see `_session_entries_and_separators`) — every REQ line
# carrying `CR c  CC c` via `usage.build_usage_by_flow` (always joined now, not only under
# `--rebuild`/`--drop` — see `__main__.py`), `CR ?  CC ?` when the flow does not resolve. `--turn N`
# keeps only that turn (a session missing it prints its header only); `--gap MINUTES`/`--rebuild`/
# `--drop` are pure filters over the SAME per-session REQ sequence, applied AFTER `--turn` narrows
# it (`_apply_filters`) — and a turn's separator prints only when at least one of ITS OWN REQ lines
# survives every active filter; the separator's own content (clock/span/preview) is always the
# WHOLE turn's, never recomputed from whatever subset of its REQs happened to survive (verified:
# `reqs k-ratio --gap 60`'s surviving REQ 46/47/393/394 print under turn 4/5/15/16's own separators,
# each showing that turn's real span even though only one of its REQs is printed). `results` is
# `[(session, boundaries), …]`, already scope/date/family-filtered and skip-on-unloadable exactly
# like `search`; `turns_by_stem`/`usage_by_stem` are `{stem: data["turns"]}` / `{stem: {flow_id:
# (cr, cc)}}`, built once per loaded session in `__main__.py` regardless of which flags are set.
def render_reqs(results: list, skipped: int = 0, turn: int = None, gap_minutes: int = None,
                usage_by_stem: dict = None, rebuild: bool = False, drop: bool = False,
                turns_by_stem: dict = None) -> str:
    if not results:
        lines = ["no sessions found"]
        return "\n".join(lines + _skipped_lines(skipped)) + "\n"
    lines = []
    for session, boundaries in results:
        stem = session.get("stem", "")
        lines.append(f"session {stem}")
        usage_map = (usage_by_stem or {}).get(stem, {})
        turns = (turns_by_stem or {}).get(stem, [])
        entries, separators = _session_entries_and_separators(boundaries, turns, usage_map, stem)
        entries = _apply_filters(entries, turn, gap_minutes, rebuild, drop)
        lines.extend(_grouped_lines(entries, separators, merged=False))
        lines.append("")
    return "\n".join(lines[:-1] + _skipped_lines(skipped)) + "\n"


# reqs --merged: every session in scope folded into ONE chronological REQ chain instead of one
# listing per session — the prompt cache is shared across a project's workers, so the gap that
# matters spans every session, not one. "merged <N> sessions" header (N = sessions that actually
# loaded, `len(results)`) replaces the per-session `session <stem>` lines; every REQ line AND every
# turn separator carries the session's own tag (`_session_tag`, placed right after the span on a
# separator, right after the clock on a REQ line) — turn numbers stay PER SESSION
# (`_session_entries_and_separators` computes them before the merge), so the tag is what
# disambiguates a repeated turn number across sessions. `--gap` pairs GLOBAL chronological
# neighbors across every session (`_apply_filters`/`_bracket_gap_positions` read only `entries[i][0]`,
# the dt, over the merged, sorted sequence); `--drop`'s predecessor stays the SAME session's own
# previous REQ regardless (`_entries_for_session` precomputes it per session, before the merge).
def render_reqs_merged(results: list, skipped: int = 0, turn: int = None, gap_minutes: int = None,
                       usage_by_stem: dict = None, rebuild: bool = False, drop: bool = False,
                       turns_by_stem: dict = None) -> str:
    if not results:
        lines = ["no sessions found"]
        return "\n".join(lines + _skipped_lines(skipped)) + "\n"
    entries, separators = _merged_entries(results, turns_by_stem, usage_by_stem)
    entries = _apply_filters(entries, turn, gap_minutes, rebuild, drop)
    lines = [f"merged {len(results)} sessions"]
    lines.extend(_grouped_lines(entries, separators, merged=True))
    return "\n".join(lines + _skipped_lines(skipped)) + "\n"


# One "REQ n   HH:MM:SS[  tag]  CR c  CC c" line — tag only under --merged, CR padded to
# `cr_width` (left-justified, see `_cr_width_by_stem`) so the CC column lines up across every REQ
# of the same session; "?" for either figure when `usage` is None (the flow never resolved).
def _req_line(marker: dict, tag: str, usage, cr_width: int) -> str:
    tag_part = f"  {tag}" if tag else ""
    return f"REQ {marker['number']:<{_REQ_NUMBER_WIDTH}}{_clock(marker['timestamp'])}{tag_part}{_usage_part(usage, cr_width)}"


# "  CR <padded>  CC <val>" — cache_read_input_tokens / cache_creation_input_tokens, digit-grouped
# like every other chars/token figure in this package, "?" for either when usage is None.
def _usage_part(usage, cr_width: int) -> str:
    cr_str = f"{usage[0]:,}" if usage else "?"
    cc_str = f"{usage[1]:,}" if usage else "?"
    return f"  CR {cr_str:<{cr_width}}  CC {cc_str}"


# The session's own short --merged tag: a worker's name or a main session's project label — read
# straight off the STEM via `discovery.stem_identity` rather than through any project-path lookup,
# since identity's own third element IS the tag, worker or main alike. Falls back to the raw stem
# when `stem_identity` cannot parse it at all.
def _session_tag(session: dict) -> str:
    identity = stem_identity(session.get("stem", ""))
    return identity[-1] if identity else session.get("stem", "")


# One session's REQ entries plus its turn separators, both built off the SAME
# `_group_markers_by_turn` walk (turn assignment unchanged since 2026-09-08/10 — see
# timeline.py's own Gotchas). `separators` is `{(stem, turn_number): text}`, `text` always the
# WHOLE turn's own clock/span/preview (`_fmt_duration` for the span, `_turn_preview` for the
# preview) — filtering downstream only decides whether a turn's text prints at all, never what it
# says. `tag` (non-empty only under --merged) is baked into the separator text right after the
# span, and into every entry, for `_req_line`'s own tag column. A session with no turn opener at
# all yields an empty `separators` dict — its entries all carry `turn_number=None`, a key
# `_grouped_lines` never finds in `separators`, so no separator ever prints for it (the "no opener
# -> no separators" case falls out of that lookup, no special case needed).
def _session_entries_and_separators(boundaries: list, turns: list, usage_map: dict,
                                    stem: str, tag: str = "") -> tuple:
    markers, openers, groups = _group_markers_by_turn(turns or [], boundaries or [])
    turn_by_msg_index = {}
    separators = {}
    for position, opener in enumerate(openers):
        group = groups[position]
        if not group:
            continue
        turn_number = position + 1
        for msg_index in group:
            turn_by_msg_index[msg_index] = turn_number
        group_markers = [markers[msg_index] for msg_index in group]
        first_dt = local_datetime(group_markers[0]["timestamp"])
        last_dt = local_datetime(group_markers[-1]["timestamp"])
        span = (last_dt - first_dt).total_seconds() if first_dt and last_dt else None
        tag_part = f"  {tag}" if tag else ""
        separators[(stem, turn_number)] = (
            f"── turn {turn_number}  {_clock(group_markers[0]['timestamp'])}  "
            f"{_fmt_duration(span)}{tag_part}  {_turn_preview(turns[opener])} ──"
        )
    entries = _entries_for_session(markers, usage_map, turn_by_msg_index, stem, tag)
    return entries, separators


# One session's own markers as [(dt, stem, marker, tag, turn_number, usage, prev_usage), …], in
# msg-index order (already chronological within a session) — the shared entry shape every filter
# and `_grouped_lines` consumes, whether built here for a single session or flattened across many
# by `_merged_entries`. `usage` is `usage_map.get(marker's flow_id)`, `None` when the map is
# empty/absent or the flow never resolved. `prev_usage` is PRECOMPUTED here, while this function is
# still walking ONE session in msg-index order — this marker's own session's immediately preceding
# request's `usage` (`None` for the session's own first request) — and stays fixed on the tuple
# from this point on, regardless of whatever order the entry later ends up in once `_merged_entries`
# flattens and re-sorts across sessions by `dt`. This is what makes a `--drop` predecessor always
# the SAME session's own previous request, even under `--merged`. A marker whose timestamp fails to
# parse is dropped, same as `_merged_entries` already does for its own chronological-ordering need
# — real dual-log timestamps are never malformed, so this never fires on genuine data.
def _entries_for_session(markers: dict, usage_map: dict, turn_by_msg_index: dict,
                         stem: str, tag: str = "") -> list:
    entries = []
    prev_usage = None
    for msg_index in sorted(markers):
        marker = markers[msg_index]
        dt = local_datetime(marker["timestamp"])
        if dt is None:
            continue
        usage = (usage_map or {}).get(marker.get("flow_id"))
        turn_number = turn_by_msg_index.get(msg_index)
        entries.append((dt, stem, marker, tag, turn_number, usage, prev_usage))
        prev_usage = usage
    return entries


# --merged's flattened, chronologically SORTED entries plus every session's own separators, merged
# into one dict (keys already disambiguated by `stem`, so no collision is possible even when two
# sessions share a turn NUMBER). `usage_by_stem`/`turns_by_stem` are `{stem: ...}` maps, looked up
# once per session here rather than per marker, then threaded into `_session_entries_and_separators`,
# which computes `prev_usage`/turn assignment PER SESSION before this function's own sort ever runs
# — the sort below only ever reorders entries for DISPLAY/--gap purposes, it never recomputes or
# reassigns which predecessor a --drop check reads or which turn a REQ belongs to.
def _merged_entries(results: list, turns_by_stem: dict = None, usage_by_stem: dict = None) -> tuple:
    entries = []
    separators = {}
    for session, boundaries in results:
        stem = session.get("stem", "")
        tag = _session_tag(session)
        usage_map = (usage_by_stem or {}).get(stem, {})
        turns = (turns_by_stem or {}).get(stem, [])
        session_entries, session_separators = _session_entries_and_separators(
            boundaries, turns, usage_map, stem, tag)
        entries.extend(session_entries)
        separators.update(session_separators)
    entries.sort(key=lambda entry: entry[0])
    return entries, separators


# `--gap MINUTES`'s candidate POSITIONS, as {position: None} — the pure selection half of the old
# `--gap` renderer, kept as the shared pairing walk now that no line carries a gap-specific tail of
# its own: every position bracketing a qualifying pause of >= gap_minutes (whole minutes, floored —
# `total_seconds() // 60`, never rounded, so a boundary case is exact) is recorded, before and
# after alike — `_apply_filters` only reads the KEY set (`sorted(positions)`). `entries` is already
# sorted, already stripped of unparseable timestamps by the caller — this function reads ONLY `dt`
# (index 0), chronological, cross-session neighbors under --merged included, exactly as before.
def _bracket_gap_positions(entries: list, gap_minutes: int) -> dict:
    positions = {}
    for i in range(len(entries) - 1):
        dt_before = entries[i][0]
        dt_after = entries[i + 1][0]
        elapsed = int((dt_after - dt_before).total_seconds() // 60)
        if elapsed < gap_minutes:
            continue
        positions.setdefault(i, None)
        positions[i + 1] = None
    return positions


# `--rebuild`/`--drop`: usage-driven REQ predicate, orthogonal to `--gap`/`--merged`/scope/--turn.
# Both read the SAME per-request CR/CC `msgs` resolves via `usage.build_usage_by_flow`
# (cache_read_input_tokens / cache_creation_input_tokens) — never re-derived here.
#
# `--rebuild` keeps only REQs where CC > CR (this request's own cache write outweighs what it read
# back — the write is the signal something upstream had to be rebuilt). `--drop` keeps only REQs n
# where CR(n) < CR(n-1) + CC(n-1) — part of the prefix the PREVIOUS request had cached (its own
# read plus what it just wrote) was NOT read again by n, meaning the cache actually cooled between
# them; exactly equal does NOT qualify (`>=` fails the condition — the STRICT inequality is what
# "not fully read back" means). "previous" is `n`'s own PRECOMPUTED `prev_usage` (`_entries_for_session`'s
# same-session predecessor) — ALWAYS the same session's own previous REQ, `--merged` or not: the
# shared prompt-cache prefix a cache drop is measuring is system blocks + tools, never the
# conversation, so comparing one session's CR against a DIFFERENT session's CR+CC would be
# meaningless (see Gotchas). REQ 1 of a session — the entry whose own `prev_usage` is `None` —
# never qualifies for `--drop`, regardless of where it lands in a `--merged` chain's chronological
# order.
#
# Both flags combine with AND: a REQ must satisfy every active one. A REQ whose own usage (or, for
# `--drop`, its predecessor's) does not resolve fails — never kept tail-less, never guessed
# (2026-09-16: this predicate used to also compute a printed shortfall figure; the M6 redesign
# dropped every tail, so it now returns a plain bool).
def _rebuild_drop_qualifies(usage, prev_usage, rebuild: bool, drop: bool) -> bool:
    if usage is None:
        return False
    cache_read, cache_creation = usage
    if rebuild and not (cache_creation > cache_read):
        return False
    if drop:
        if prev_usage is None:
            return False
        prev_read, prev_creation = prev_usage
        if cache_read >= prev_read + prev_creation:
            return False
    return True


# The shared filter pipeline every `reqs` flag composes through (2026-09-16, M6): `--turn` narrows
# FIRST (keeping only entries whose OWN turn number equals it — a session missing that turn
# contributes nothing, which is what makes it print its header only), then `--gap` (via
# `_bracket_gap_positions` over whatever survived the narrowing), then `--rebuild`/`--drop` (via
# `_rebuild_drop_qualifies`, each candidate checked against its OWN precomputed `prev_usage`,
# independent of whichever entry a `--gap` pairing happened to bracket it with). Every stage is a
# no-op when its own flag is unset, so a bare call returns `entries` unchanged.
def _apply_filters(entries: list, turn: int, gap_minutes: int, rebuild: bool, drop: bool) -> list:
    if turn is not None:
        entries = [entry for entry in entries if entry[4] == turn]
    if gap_minutes is not None:
        positions = _bracket_gap_positions(entries, gap_minutes)
        entries = [entries[i] for i in sorted(positions)]
    if rebuild or drop:
        entries = [entry for entry in entries if _rebuild_drop_qualifies(entry[5], entry[6], rebuild, drop)]
    return entries


# The widest CR figure ("?" counts as 1 char) actually being printed, per session (`stem`) — what
# `_req_line` pads every CR value to, so the CC column lines up down the page. Computed from
# exactly the entries about to be rendered (post every filter), not from the session's full,
# unfiltered REQ list — a narrowed listing (`--turn`/`--gap`/`--rebuild`/`--drop`) reads as its own
# tight table rather than carrying padding sized for lines it never prints.
def _cr_width_by_stem(entries: list) -> dict:
    widths = {}
    for _dt, stem, _marker, _tag, _turn, usage, _prev_usage in entries:
        cr_str = f"{usage[0]:,}" if usage else "?"
        widths[stem] = max(widths.get(stem, 0), len(cr_str))
    return widths


# Renders the (already filtered) entry sequence: a turn separator whenever the (session, turn)
# key changes from the previous entry AND that key has separator text (a no-opener session's
# entries all carry `turn_number=None`, a key never present in `separators`, so they render as a
# flat, separator-free list — no special case needed), then that entry's own `_req_line`. `merged`
# controls only whether the tag column prints — the per-session listing's own entries already
# carry `tag=""` throughout, so this is a belt-and-braces switch rather than one this module
# currently needs to disambiguate.
def _grouped_lines(entries: list, separators: dict, merged: bool) -> list:
    cr_width_by_stem = _cr_width_by_stem(entries)
    lines = []
    current_key = None
    for _dt, stem, marker, tag, turn_number, usage, _prev_usage in entries:
        key = (stem, turn_number)
        if key != current_key:
            text = separators.get(key)
            if text is not None:
                lines.append(text)
            current_key = key
        cr_width = cr_width_by_stem.get(stem, 1)
        lines.append(_req_line(marker, tag if merged else "", usage, cr_width))
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
        f"project   {data['session']['project']}",
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


# Compact human duration: "58s" under a minute, "41m24s" under an hour, "1h05m30s" at or past one
# — grep-friendly (a letter suffix per unit, no spaces) and fixed-width only where cheap (seconds
# always 2 digits once a coarser unit is present; the leading unit is not padded, since padding it
# would widen every row for a session whose turns never reach double-digit hours). "?" for an
# unresolved duration — same width class as a real value once printed via `{:>N}`.
#
# Originally built for the `turns` command's transcript-joined durations (removed 2026-09-10, see
# process-docs/dual_log_cli/) — kept for `reqs`' own turn separator (`_session_entries_and_separators`),
# which reuses it for the send-time-only turn span, the ONE thing that survived both the 2026-09-10
# pivot and the 2026-09-16 M6 redesign (the per-request elapsed tail this once also fed did not).
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
