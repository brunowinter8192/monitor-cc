# INFRASTRUCTURE
import hashlib
from datetime import datetime, timezone
from typing import Optional

from .diff_engine import _diff_system, _diff_tools, _diff_messages, _diff_top_level_fields, _get_inner_text, compose_block
from .strip_vocab import attribute_chunk as _attribute_chunk
from .logging import _strip_cache_control, _normalize_msg_shape_for_hash, _delta_hash

# fn attribution maps for fn_map field in _build_stripped_injected_deltas
_SYS_FN: dict[int, str] = {2: '_apply_system_passes', 3: '_strip_sys3'}
_FIELD_STRIP_FN: dict[str, str] = {
    'model': '_inject_model_override', 'max_tokens': '_inject_model_override',
    'thinking': '_inject_model_override', 'output_config': '_inject_model_override',
}
_FIELD_INJECT_FN: dict[str, str] = {
    **_FIELD_STRIP_FN, 'context_management': '_inject_context_management',
}
_MSG_CODE_TO_FN: dict[str, str] = {
    'RS':  '_apply_role_system_strip',
    'REJ': '_apply_first_pass',  'TN':  '_apply_first_pass',
    'NAG': '_apply_first_pass',  'DEF': '_apply_first_pass',
    'UI':  '_apply_first_pass',  'PM':  '_apply_first_pass',
    'SK':  '_apply_cumulative_sr_strips', 'AT':  '_apply_cumulative_sr_strips',
    'CMD': '_apply_cumulative_sr_strips',
    'PYR': '_apply_cumulative_sr_strips',
    'ALL': '_apply_final_sr_pass', 'ENV': '_apply_final_sr_pass',
    'SN':  '_apply_final_sr_pass', 'FM':  '_apply_final_sr_pass',
    'PP':  '_apply_po_preview_strip', 'BGK': '_apply_bg_exit_strip',
    'GL':  '_apply_git_lock_strip',   'BD':  '_apply_bd_noise_strip',
    'HP':  '_apply_hook_prefix_strip',
}

# FUNCTIONS

# MD5[:10] of pipe-joined span texts — stable identity for a set of stripped texts
def _hash_spans(texts: list) -> str:
    return hashlib.md5("|".join(texts).encode("utf-8")).hexdigest()[:10]


# MD5[:10] of ordered span sequence — stable identity for equal+injected span list (new _injected format)
def _hash_span_sequence(spans: list) -> str:
    return hashlib.md5("|".join(f"{tag}:{text}" for tag, text in spans).encode("utf-8")).hexdigest()[:10]


# System section: stripped/injected texts, hashes, fn attribution per system block
# Returns (s_sys, i_sys, s_hashes, i_hashes, s_fn, i_fn)
def _process_system_section(sys_diffs, is_first, prev_stripped, prev_injected):
    s_sys: dict = {}
    i_sys: dict = {}
    s_hashes: dict = {}
    i_hashes: dict = {}
    s_fn: dict = {}
    i_fn: dict = {}
    for d in sys_diffs:
        idx_str = str(d["idx"])
        s_texts = [t for tag, t in d["spans"] if tag == "stripped" and t]
        i_spans = [(tag, t) for tag, t in d["spans"] if tag in ("equal", "injected") and t]
        has_i = any(tag == "injected" for tag, _ in i_spans)
        if s_texts:
            lk = f"sys.{d['idx']}"
            h = _hash_spans(s_texts)
            s_hashes[lk] = h
            if is_first or (prev_stripped or {}).get(lk) != h:
                s_sys[idx_str] = s_texts
                s_fn[lk] = _SYS_FN.get(d["idx"], "_apply_system_passes")
        if has_i:
            lk = f"sys.{d['idx']}"
            h = _hash_span_sequence(i_spans)
            i_hashes[lk] = h
            if is_first or (prev_injected or {}).get(lk) != h:
                i_sys[idx_str] = i_spans
                i_text = " ".join(t for tag, t in i_spans if tag == "injected" and t)
                if i_text != ".":
                    i_fn[lk] = _SYS_FN.get(d["idx"], "_apply_system_passes")
    return s_sys, i_sys, s_hashes, i_hashes, s_fn, i_fn


# Tools section: whole-tool and description-level stripped/injected, hashes, fn attribution
# Returns (s_tools, i_tools, s_hashes, i_hashes, s_fn, i_fn)
def _process_tools_section(tools_diff, is_first, prev_stripped, prev_injected):
    s_tools: dict = {}
    i_tools: dict = {}
    s_hashes: dict = {}
    i_hashes: dict = {}
    s_fn: dict = {}
    i_fn: dict = {}
    for name in tools_diff["stripped"]:
        lk = f"tool_w.{name}"
        h = _hash_spans([name])
        s_hashes[lk] = h
        if is_first or (prev_stripped or {}).get(lk) != h:
            s_tools[name] = {"whole": True}
            s_fn[lk] = "_strip_unused_tools"
    for name in tools_diff["injected"]:
        lk = f"tool_w.{name}"
        h = _hash_spans([name])
        i_hashes[lk] = h
        if is_first or (prev_injected or {}).get(lk) != h:
            i_tools[name] = {"whole": True}
            i_fn[lk] = "inject_mcp_tools"
    for name, _o, _f, spans in tools_diff["desc_changes"]:
        s_texts = [t for tag, t in spans if tag == "stripped" and t]
        i_spans = [(tag, t) for tag, t in spans if tag in ("equal", "injected") and t]
        has_i = any(tag == "injected" for tag, _ in i_spans)
        if s_texts:
            lk = f"tool_d.{name}"
            h = _hash_spans(s_texts)
            s_hashes[lk] = h
            if is_first or (prev_stripped or {}).get(lk) != h:
                s_tools[name] = {"desc": s_texts}
                s_fn[lk] = "_strip_tool_descriptions"
        if has_i:
            lk = f"tool_d.{name}"
            h = _hash_span_sequence(i_spans)
            i_hashes[lk] = h
            if is_first or (prev_injected or {}).get(lk) != h:
                i_tools[name] = {"desc": i_spans}
                i_text = " ".join(t for tag, t in i_spans if tag == "injected" and t)
                if i_text != ".":
                    i_fn[lk] = "inject_mcp_tools"
    return s_tools, i_tools, s_hashes, i_hashes, s_fn, i_fn


# Messages section: block-level stripped/injected spans, hashes, fn attribution
# Returns (s_msgs, i_msgs, s_hashes, i_hashes, s_fn, i_fn)
def _process_messages_section(msg_diffs, orig_msgs_norm, is_first, prev_stripped, prev_injected, all_ops):
    s_msgs: dict = {}
    i_msgs: dict = {}
    s_hashes: dict = {}
    i_hashes: dict = {}
    s_fn: dict = {}
    i_fn: dict = {}
    for md in msg_diffs:
        midx = str(md["idx"])
        s_blks: dict = {}
        i_blks: dict = {}
        om_norm = orig_msgs_norm[md["idx"]] if md["idx"] < len(orig_msgs_norm) else {}
        o_content_raw = om_norm.get("content", "") if isinstance(om_norm, dict) else ""
        msg_ops = (all_ops or {}).get(md["idx"], {})
        for bd in md["block_diffs"]:
            bidx_int = bd["bidx"]
            bidx = str(bidx_int)
            if isinstance(o_content_raw, list):
                ob = o_content_raw[bidx_int] if bidx_int < len(o_content_raw) else None
                c0_text = _get_inner_text(ob) if ob is not None else ""
            elif bidx_int == 0:
                c0_text = o_content_raw if isinstance(o_content_raw, str) else ""
            else:
                c0_text = ""
            block_ops = msg_ops.get(bidx_int, [])
            spans = compose_block(c0_text, block_ops)
            s_texts = [t for tag, t in spans if tag == "stripped" and t]
            i_spans = [(tag, t) for tag, t in spans if tag in ("equal", "injected") and t]
            has_i = any(tag == "injected" for tag, _ in i_spans)
            if s_texts:
                lk = f"msg.{md['idx']}.{bd['bidx']}"
                h = _hash_spans(s_texts)
                s_hashes[lk] = h
                if is_first or (prev_stripped or {}).get(lk) != h:
                    s_blks[bidx] = s_texts
                    if om_norm.get("role") == "system":
                        code = 'RS'
                    else:
                        code = _attribute_chunk("\n".join(s_texts))
                    s_fn[lk] = _MSG_CODE_TO_FN.get(code, "unknown") if code else "unknown"
            if has_i:
                lk = f"msg.{md['idx']}.{bd['bidx']}"
                h = _hash_span_sequence(i_spans)
                i_hashes[lk] = h
                if is_first or (prev_injected or {}).get(lk) != h:
                    i_blks[bidx] = i_spans
                    i_text = " ".join(t for tag, t in i_spans if tag == "injected" and t)
                    if i_text == ".":
                        pass  # empty-block placeholder — not a real injection, skip badge
                    elif "background done" in i_text:
                        i_fn[lk] = "_apply_bg_exit_strip"
                    else:
                        code = _attribute_chunk(i_text) if i_text else None
                        i_fn[lk] = _MSG_CODE_TO_FN.get(code, "unknown") if code else "unknown"
        if s_blks:
            s_msgs[midx] = s_blks
        if i_blks:
            i_msgs[midx] = i_blks
    return s_msgs, i_msgs, s_hashes, i_hashes, s_fn, i_fn


# Top-level fields section: stripped/injected field values and hashes (no fn attribution for fields)
# Returns (s_fields, i_fields, s_hashes, i_hashes)
def _process_fields_section(field_diffs, is_first, prev_stripped, prev_injected):
    s_fields: dict = {}
    i_fields: dict = {}
    s_hashes: dict = {}
    i_hashes: dict = {}
    for fd in field_diffs:
        key = fd["key"]
        lk = f"field.{key}"
        if fd["tag"] in ("stripped", "replaced"):
            h = _delta_hash(fd["orig"])
            s_hashes[lk] = h
            if is_first or (prev_stripped or {}).get(lk) != h:
                s_fields[key] = fd["orig"]
        if fd["tag"] in ("injected", "replaced"):
            h = _delta_hash(fd["fwd"])
            i_hashes[lk] = h
            if is_first or (prev_injected or {}).get(lk) != h:
                i_fields[key] = fd["fwd"]
    return s_fields, i_fields, s_hashes, i_hashes


# Build stripped_delta and injected_delta entries and updated hash states
# Both payloads are normalized (cache_control stripped) at call site before passing here.
# prev_stripped / prev_injected: flat dicts of loc_key → hash from previous request (None = first).
# Returns (stripped_entry, injected_entry, new_stripped_hashes, new_injected_hashes).
# fn_map: top-level dict (loc_key → responsible fn) attached to both entries at write time.
# Old entries without fn_map (pre-materialization) are read-side safe — field simply absent.
def _build_stripped_injected_deltas(
    orig_payload: dict,
    fwd_payload: dict,
    request_id: str,
    prev_stripped: Optional[dict],
    prev_injected: Optional[dict],
    model: str,
    all_ops: Optional[dict] = None,
) -> tuple:
    orig_norm = _strip_cache_control(orig_payload)
    fwd_norm = _strip_cache_control(fwd_payload)

    orig_sys = [b for b in (orig_norm.get("system", []) or []) if isinstance(b, dict)]
    fwd_sys = [b for b in (fwd_norm.get("system", []) or []) if isinstance(b, dict)]
    orig_tools = orig_norm.get("tools", []) or []
    fwd_tools = fwd_norm.get("tools", []) or []
    orig_msgs = orig_norm.get("messages", []) or []
    fwd_msgs = fwd_norm.get("messages", []) or []

    sys_diffs = _diff_system(orig_sys, fwd_sys)
    tools_diff = _diff_tools(orig_tools, fwd_tools)
    orig_msgs_norm = [_normalize_msg_shape_for_hash(m) for m in orig_msgs]
    fwd_msgs_norm  = [_normalize_msg_shape_for_hash(m) for m in fwd_msgs]
    msg_diffs = _diff_messages(orig_msgs_norm, fwd_msgs_norm)
    field_diffs = _diff_top_level_fields(orig_norm, fwd_norm)

    is_first = prev_stripped is None

    s_sys, i_sys, s_sys_h, i_sys_h, s_sys_fn, i_sys_fn = _process_system_section(
        sys_diffs, is_first, prev_stripped, prev_injected)
    s_tools, i_tools, s_tools_h, i_tools_h, s_tools_fn, i_tools_fn = _process_tools_section(
        tools_diff, is_first, prev_stripped, prev_injected)
    s_msgs, i_msgs, s_msgs_h, i_msgs_h, s_msgs_fn, i_msgs_fn = _process_messages_section(
        msg_diffs, orig_msgs_norm, is_first, prev_stripped, prev_injected, all_ops)
    s_fields, i_fields, s_fields_h, i_fields_h = _process_fields_section(
        field_diffs, is_first, prev_stripped, prev_injected)

    new_s = {**s_sys_h, **s_tools_h, **s_msgs_h, **s_fields_h}
    new_i = {**i_sys_h, **i_tools_h, **i_msgs_h, **i_fields_h}
    s_fn_map = {**s_sys_fn, **s_tools_fn, **s_msgs_fn}
    i_fn_map = {**i_sys_fn, **i_tools_fn, **i_msgs_fn}

    now = datetime.now(timezone.utc)
    timestamp = f"{now.strftime('%Y-%m-%dT%H:%M:%S.')}{now.microsecond // 1000:03d}Z"
    counts = {"system": len(fwd_sys), "tools": len(fwd_tools), "messages": len(fwd_msgs)}

    stripped_entry = {
        "type": "stripped_delta",
        "request_id": request_id,
        "timestamp": timestamp,
        "model": model,
        "is_first": is_first,
        "counts": counts,
        "system_delta": s_sys,
        "tools_delta": s_tools,
        "messages_delta": s_msgs,
        "fields_delta": s_fields,
        "fn_map": s_fn_map,
    }
    injected_entry = {
        "type": "injected_delta",
        "request_id": request_id,
        "timestamp": timestamp,
        "model": model,
        "is_first": is_first,
        "counts": counts,
        "system_delta": i_sys,
        "tools_delta": i_tools,
        "messages_delta": i_msgs,
        "fields_delta": i_fields,
        "fn_map": i_fn_map,
    }
    return stripped_entry, injected_entry, new_s, new_i
