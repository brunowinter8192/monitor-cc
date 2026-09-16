# INFRASTRUCTURE
import sys

from main_log_elimination_reconstruct import (
    _reconstruct_forwarded, _normalize_elem, _count_cache_control,
    _element_divergences, _classify_fields, _DELTA_COVERED,
)

# FUNCTIONS

def _compare_request(idx: int, main_e: dict, fwd_r: dict) -> dict:
    raw_payload = main_e.get("raw_payload", {})

    bp_main = _count_cache_control(raw_payload)
    bp_fwd = _count_cache_control({
        "system": fwd_r["system"],
        "tools": fwd_r["tools"],
        "messages": fwd_r["messages"],
    })

    raw_sys = [_normalize_elem(b) for b in (raw_payload.get("system") or [])]
    raw_tools = [_normalize_elem(t) for t in (raw_payload.get("tools") or [])]
    raw_msgs = [_normalize_elem(m, is_message=True) for m in (raw_payload.get("messages") or [])]

    fwd_sys = [_normalize_elem(b) for b in (fwd_r["system"] or [])]
    fwd_tools = [_normalize_elem(t) for t in (fwd_r["tools"] or [])]
    fwd_msgs = [_normalize_elem(m, is_message=True) for m in (fwd_r["messages"] or [])]

    sys_match = raw_sys == fwd_sys
    tools_match = raw_tools == fwd_tools
    msgs_match = raw_msgs == fwd_msgs

    sys_div = _element_divergences(raw_sys, fwd_sys) if not sys_match else []
    tools_div = _element_divergences(raw_tools, fwd_tools) if not tools_match else []
    msgs_div = _element_divergences(raw_msgs, fwd_msgs) if not msgs_match else []

    missing_fields = [k for k in raw_payload.keys() if k not in _DELTA_COVERED]

    return {
        "idx": idx,
        "request_id": main_e.get("request_id", ""),
        "model": main_e.get("model", ""),
        "family": fwd_r["family"],
        "is_first": fwd_r["is_first"],
        "bp_main": bp_main,
        "bp_fwd": bp_fwd,
        "sys_match": sys_match,
        "tools_match": tools_match,
        "msgs_match": msgs_match,
        "sys_div": sys_div,
        "tools_div": tools_div,
        "msgs_div": msgs_div,
        "raw_msg_count": len(raw_msgs),
        "fwd_msg_count": len(fwd_msgs),
        "missing_fields": missing_fields,
        "raw_keys": set(raw_payload.keys()),
    }


def _run_question_a(main_entries: list, fwd_entries: list) -> dict:
    reconstructed = _reconstruct_forwarded(fwd_entries)

    if len(main_entries) != len(reconstructed):
        print(
            f"  [warn] main log has {len(main_entries)} request entries but forwarded has {len(reconstructed)} — "
            "positional match may be off. Results may be unreliable.",
            file=sys.stderr,
        )

    n = min(len(main_entries), len(reconstructed))
    per_request = [_compare_request(i, main_entries[i], reconstructed[i]) for i in range(n)]

    all_raw_keys: set = set()
    for r in per_request:
        all_raw_keys |= r.pop("raw_keys")

    field_classification = _classify_fields(all_raw_keys)

    return {
        "n": n,
        "per_request": per_request,
        "total_sys_match": sum(1 for r in per_request if r["sys_match"]),
        "total_tools_match": sum(1 for r in per_request if r["tools_match"]),
        "total_msgs_match": sum(1 for r in per_request if r["msgs_match"]),
        "all_raw_keys": sorted(all_raw_keys),
        "field_classification": field_classification,
        "main_count": len(main_entries),
        "fwd_count": len(reconstructed),
    }


def _extract_tool_errors(orig_entries: list) -> list:
    seen_ids: set = set()
    unique_errors = []

    for entry_idx, entry in enumerate(orig_entries):
        payload = entry.get("payload", {})
        messages = payload.get("messages", [])
        for msg_idx, msg in enumerate(messages):
            content = msg.get("content", [])
            if not isinstance(content, list):
                continue
            for blk in content:
                if blk.get("type") != "tool_result":
                    continue
                if blk.get("is_error") is not True:
                    continue
                tid = blk.get("tool_use_id", "")
                if tid in seen_ids:
                    continue
                seen_ids.add(tid)
                raw_content = blk.get("content", "")
                if isinstance(raw_content, list):
                    preview = " ".join(
                        b.get("text", "")[:80] for b in raw_content
                        if isinstance(b, dict)
                    )[:200]
                else:
                    preview = str(raw_content)[:200]
                unique_errors.append({
                    "tool_use_id": tid,
                    "first_seen_entry": entry_idx,
                    "first_seen_msg": msg_idx,
                    "content_preview": preview,
                })

    return unique_errors


def _run_question_b(orig_entries: list, tool_errors: list) -> dict:
    unique_errors = _extract_tool_errors(orig_entries)

    persisted_ids = {r.get("tool_use_id", "") for r in tool_errors}
    extracted_ids = {e["tool_use_id"] for e in unique_errors}

    only_in_extracted = extracted_ids - persisted_ids
    only_in_persisted = persisted_ids - extracted_ids
    both = extracted_ids & persisted_ids

    return {
        "unique_errors": unique_errors,
        "extracted_count": len(unique_errors),
        "persisted_count": len(tool_errors),
        "both": sorted(both),
        "only_in_extracted": sorted(only_in_extracted),
        "only_in_persisted": sorted(only_in_persisted),
        "tool_errors_records": tool_errors,
        "exact_match": not only_in_extracted and not only_in_persisted,
    }
