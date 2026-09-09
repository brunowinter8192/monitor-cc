# INFRASTRUCTURE
from .discovery import stem_identity
from .reader import local_datetime
from .render_format import _clock, _fmt_duration, _skipped_lines
from .timeline_grouping import _group_markers_by_turn, _turn_preview

# Fixed width of the REQ number field — a 4-char left-justified number directly followed by the
# clock, no extra space needed (the padding itself is the gap): "REQ 1   20:16:02". Same narrow-
# default-with-occasional-jog convention `msgs`' own chars column uses — a 5-digit REQ number
# pushes its own clock one column right rather than widening every shorter line permanently.
_REQ_NUMBER_WIDTH = 4


# FUNCTIONS


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
