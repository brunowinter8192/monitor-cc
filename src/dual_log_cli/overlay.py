# INFRASTRUCTURE
# From src/proxy_display/parser.py: the read-side dual-log accumulator the proxy pane uses. Reused
# rather than re-implemented, so duallog inherits its two hard-won behaviours unchanged — the
# per-coordinate span accumulation AND the write-side attribution lag correction
# (_lag_msg_idx_by_flow_id), which credits a trailing-msg total_tokens strip to the request that
# performed it instead of the one whose delta line happens to carry it.
from ..proxy_display.dual_log_accumulator import accumulate_dual_log
# From timeline_markers.py: {flow_id: REQ number}, the same numbering `msgs` prints
from .timeline_markers import request_numbers_by_flow

# FUNCTIONS


# Build the strip/inject overlay for one session -> {(msg_idx, blk_idx): {stripped, injected, req}}.
#
# duallog is msg-centric where the delta streams are flow-centric, and the two meet without any
# scoping work: both `expand` and `msgs` render msgs of ONE payload (the last non-haiku `_original`
# request), so there is no request header a foreign flow's span could appear under — the pane's
# flow-scoping has no analogue here. What a msg needs is the CUMULATIVE state of its coordinate,
# which is exactly what `accumulate_dual_log` leaves in `acc['messages'][msg][blk]`.
#
# The content direction is inverted from the pane's: duallog shows the PRE-strip original, so
# `stripped` is the part of the very text on screen that the proxy removed, and `injected` is what
# it put there instead (text that appears nowhere in the displayed content).
#
# Attribution: the flow that RECORDED a coordinate is not always the one that stripped it, so the
# lag set wins where it applies. Measured on the recorded sessions: no coordinate is ever touched by
# more than one flow, so the owner is unambiguous.
def build_overlay(session: dict, family: str, boundaries: list) -> dict:
    streams = session["streams"]
    acc_stripped: dict = {}
    acc_injected: dict = {}
    if streams.get("stripped") is not None:
        accumulate_dual_log(streams["stripped"], 0, acc_stripped)
    if streams.get("injected") is not None:
        accumulate_dual_log(streams["injected"], 0, acc_injected)
    fam_s = acc_stripped.get(family, {})
    fam_i = acc_injected.get(family, {})
    numbers = request_numbers_by_flow(boundaries)
    owners = _owners_by_index(fam_s, fam_i)
    overlay: dict = {}
    for source, key in ((fam_s, "stripped"), (fam_i, "injected")):
        for msg_key, blocks in (source.get("messages") or {}).items():
            for blk_key, recorded in (blocks or {}).items():
                texts = _texts(recorded, key)
                if not texts:
                    continue
                slot = overlay.setdefault((int(msg_key), int(blk_key)), {
                    "stripped": [], "injected": [], "req": None,
                })
                slot[key] = texts
                if slot["req"] is None:
                    slot["req"] = numbers.get(owners.get(msg_key, ""))
    return overlay


# {key: flow_id} — which flow's own delta first recorded a given coordinate, generalized over any
# of the per-flow index/name dicts `accumulate_dual_log` records (messages/system/tools all share
# the same {flow_id: set(key)} shape). First-recording flow wins; in every case measured so far a
# coordinate is touched by at most one flow anyway, so this is unambiguous in practice.
def _owners_by_flow_key(fam_stripped: dict, fam_injected: dict, by_flow_key: str) -> dict:
    owners: dict = {}
    for fam in (fam_stripped, fam_injected):
        for flow_id, keys in (fam.get(by_flow_key) or {}).items():
            for key in keys:
                owners.setdefault(key, flow_id)
    return owners


# {msg_idx_str: flow_id} — which flow actually performed the transformation at each coordinate.
# The lag set takes precedence: it names the request that stripped the msg, while the raw set names
# whichever line recorded it (one request later for a trailing total_tokens nuke).
def _owners_by_index(fam_stripped: dict, fam_injected: dict) -> dict:
    owners = _owners_by_flow_key(fam_stripped, fam_injected, "_msg_idx_by_flow_id")
    for flow_id, indices in (fam_stripped.get("_lag_msg_idx_by_flow_id") or {}).items():
        for index in indices:
            owners[index] = flow_id
    return owners


# Build the system/tools strip-inject overlay for one session's `msgs` sys/tool delta lines ->
# (sys_overlay, tools_overlay). sys_overlay is {idx_str: {stripped, injected, req, flow_id}};
# tools_overlay is {name: {stripped, injected, req, flow_id, whole}} where `whole` marks a tool the
# proxy removed ENTIRELY (stripped side recorded only {"whole": True}, no text — the description-
# level strip instead carries {"desc": [texts]}, handled like system's plain span list via `_texts`).
#
# No lag correction is needed here (unlike messages): `_diff_system`/`_diff_tools`
# (src/proxy/diff_engine.py) compute a direct same-request diff of that request's own original vs.
# forwarded halves, never a historical ops chain the way `_process_messages_section`'s `compose_block`
# does — so there is no shape-ambiguity window for a strip to land one request late. Verified on
# `opus_monitor_cc_1788464543`'s first real request: the stripped/injected stream's own system_delta
# line carries the SAME flow_id `request_boundaries` marks as that request's owner.
def build_sys_tool_overlay(session: dict, family: str, boundaries: list) -> tuple:
    streams = session["streams"]
    acc_stripped: dict = {}
    acc_injected: dict = {}
    if streams.get("stripped") is not None:
        accumulate_dual_log(streams["stripped"], 0, acc_stripped)
    if streams.get("injected") is not None:
        accumulate_dual_log(streams["injected"], 0, acc_injected)
    fam_s = acc_stripped.get(family, {})
    fam_i = acc_injected.get(family, {})
    numbers = request_numbers_by_flow(boundaries)
    sys_owners = _owners_by_flow_key(fam_s, fam_i, "_sys_idx_by_flow_id")
    tool_owners = _owners_by_flow_key(fam_s, fam_i, "_tool_name_by_flow_id")
    sys_overlay = _system_overlay(fam_s.get("system") or {}, fam_i.get("system") or {}, sys_owners, numbers)
    tools_overlay = _tools_overlay(fam_s.get("tools") or {}, fam_i.get("tools") or {}, tool_owners, numbers)
    return sys_overlay, tools_overlay


# System section of the sys/tool overlay: each recorded index's value is a plain list (stripped:
# strings, injected: (tag, text) spans) — the exact shape `_texts` already normalises for messages.
def _system_overlay(sys_stripped: dict, sys_injected: dict, owners: dict, numbers: dict) -> dict:
    overlay: dict = {}
    for source, key in ((sys_stripped, "stripped"), (sys_injected, "injected")):
        for idx_str, recorded in source.items():
            texts = _texts(recorded, key)
            if not texts:
                continue
            slot = overlay.setdefault(idx_str, {"stripped": [], "injected": [], "req": None, "flow_id": None})
            slot[key] = texts
            if slot["flow_id"] is None:
                owner = owners.get(idx_str)
                slot["flow_id"] = owner
                slot["req"] = numbers.get(owner)
    return overlay


# Tools section of the sys/tool overlay: each recorded name's value is a DICT — {"whole": True} for
# a tool the proxy removed entirely (no text to measure, `render.py` sources its original size from
# the last request's own tools list instead), or {"desc": [...]} for a description-level strip,
# whose span list is the same shape `_texts` already normalises.
def _tools_overlay(tools_stripped: dict, tools_injected: dict, owners: dict, numbers: dict) -> dict:
    overlay: dict = {}
    for source, key in ((tools_stripped, "stripped"), (tools_injected, "injected")):
        for name, recorded in source.items():
            if not isinstance(recorded, dict):
                continue
            whole = bool(recorded.get("whole"))
            texts = [] if whole else _texts(recorded.get("desc") or [], key)
            if not whole and not texts:
                continue
            slot = overlay.setdefault(
                name, {"stripped": [], "injected": [], "req": None, "flow_id": None, "whole": False},
            )
            slot[key] = texts
            if whole:
                slot["whole"] = True
            if slot["flow_id"] is None:
                owner = owners.get(name)
                slot["flow_id"] = owner
                slot["req"] = numbers.get(owner)
    return overlay


# Normalise one recorded coordinate to a list of plain texts. The stripped side is a flat list of
# strings; the injected side is (tag, text) pairs of which only the `injected` ones are new content
# — the `equal` parts are the surviving original, already on screen as the block body.
def _texts(recorded, side: str) -> list:
    if not isinstance(recorded, list):
        return []
    if side == "stripped":
        return [t for t in recorded if isinstance(t, str) and t]
    out = []
    for span in recorded:
        if isinstance(span, (list, tuple)) and len(span) == 2 and span[0] == "injected" and span[1]:
            out.append(span[1])
        elif isinstance(span, str) and span:
            out.append(span)
    return out
