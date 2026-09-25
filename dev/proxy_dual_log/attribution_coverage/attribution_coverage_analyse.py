# INFRASTRUCTURE
import json
from collections import defaultdict
from pathlib import Path

from attribution_coverage_classify import (
    _SYS_INJECT_FN, _classify_strip_msg, _classify_inject_msg, _inject_text,
)
from attribution_coverage_classify import _FIELD_STRIP_FN, _FIELD_INJECT_FN

# FUNCTIONS

def _find_pairs(log_dir: Path) -> list:
    pairs = []
    for sf in sorted(log_dir.glob("*_stripped.jsonl")):
        ijf = log_dir / sf.name.replace("_stripped.jsonl", "_injected.jsonl")
        if ijf.exists():
            pairs.append((sf, ijf))
    return pairs


def _load_jsonl(path: Path) -> list:
    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def _analyse_sys_delta(s_entry: dict, i_entry: dict, strip_stats: dict, inject_stats: dict) -> None:
    for idx_s, s_texts in s_entry.get("system_delta", {}).items():
        if not s_texts:
            continue
        fn = f"sys[{idx_s}]: _apply_system_passes/strip_sys3 (replaced_system_prompt)"
        strip_stats["sys"][fn] += 1

    i_sys = i_entry.get("system_delta", {})
    for idx_s, i_val in i_sys.items():
        if not i_val:
            continue
        fn = _SYS_INJECT_FN.get(idx_s, f"sys[{idx_s}]: UNATTRIBUTED")
        inject_stats["sys"][fn] += 1


def _analyse_tools_delta(s_entry: dict, i_entry: dict, strip_stats: dict, inject_stats: dict) -> None:
    for name, shape in s_entry.get("tools_delta", {}).items():
        if not isinstance(shape, dict):
            continue
        if shape.get("whole"):
            strip_stats["tools"]["_strip_unused_tools (blocklist)"] += 1
        elif "desc" in shape:
            strip_stats["tools"]["_strip_tool_descriptions"] += 1

    for name, shape in i_entry.get("tools_delta", {}).items():
        if not isinstance(shape, dict):
            continue
        if shape.get("whole"):
            inject_stats["tools"]["inject_mcp_tools"] += 1
        elif "desc" in shape:
            inject_stats["tools"]["inject_mcp_tools (desc)"] += 1


def _analyse_messages_delta(pair_name: str, s_entry: dict, i_entry: dict, strip_stats: dict,
                            inject_stats: dict, residuals: list, false_positives: list,
                            attribute_chunk) -> None:
    s_msg_keys: set = set()
    for midx_s, mv in s_entry.get("messages_delta", {}).items():
        for bidx_s, s_texts in mv.items():
            if not s_texts:
                continue
            s_msg_keys.add((midx_s, bidx_s))
            i_bv = i_entry.get("messages_delta", {}).get(midx_s, {}).get(bidx_s, [])
            tier, cat = _classify_strip_msg(s_texts, i_bv, attribute_chunk)
            strip_stats["msg"][cat] += 1
            if tier == "residual":
                residuals.append((pair_name, "strip_msg", f"[{midx_s}][{bidx_s}]",
                                  (" ".join(s_texts))[:120], cat))
            elif tier == "unattr":
                residuals.append((pair_name, "strip_msg_UNATTR", f"[{midx_s}][{bidx_s}]",
                                  (" ".join(s_texts))[:120], "UNATTR"))
            elif tier == "false_pos":
                i_text_sample = _inject_text(i_bv)[:80]
                false_positives.append((pair_name, "strip_msg", f"[{midx_s}][{bidx_s}]",
                                        (" ".join(s_texts))[:80], i_text_sample, cat))

    for midx_s, mv in i_entry.get("messages_delta", {}).items():
        for bidx_s, i_bv in mv.items():
            if not i_bv:
                continue
            s_bv_exists = (midx_s, bidx_s) in s_msg_keys
            tier, cat = _classify_inject_msg(i_bv, s_bv_exists)
            inject_stats["msg"][cat] += 1
            if tier == "unattr":
                residuals.append((pair_name, "inject_msg", f"[{midx_s}][{bidx_s}]",
                                  _inject_text(i_bv)[:120], "UNATTR"))
            elif tier == "false_pos":
                false_positives.append((pair_name, "inject_msg", f"[{midx_s}][{bidx_s}]",
                                        "", _inject_text(i_bv)[:80], cat))


def _analyse_fields_delta(pair_name: str, s_entry: dict, i_entry: dict, strip_stats: dict,
                          inject_stats: dict, residuals: list) -> None:
    for key, orig_val in s_entry.get("fields_delta", {}).items():
        fn = _FIELD_STRIP_FN.get(key, f"UNATTR:{key}")
        strip_stats["fields"][fn] += 1
        if fn.startswith("UNATTR"):
            residuals.append((pair_name, "strip_fields", key, str(orig_val)[:80], "UNATTR"))

    for key, fwd_val in i_entry.get("fields_delta", {}).items():
        fn = _FIELD_INJECT_FN.get(key, f"UNATTR:{key}")
        inject_stats["fields"][fn] += 1
        if fn.startswith("UNATTR"):
            residuals.append((pair_name, "inject_fields", key, str(fwd_val)[:80], "UNATTR"))


def _analyse_all_pairs(pairs: list, attribute_chunk) -> tuple:
    strip_stats: dict = defaultdict(lambda: defaultdict(int))
    inject_stats: dict = defaultdict(lambda: defaultdict(int))
    residuals: list = []
    false_positives: list = []

    for sf, ijf in pairs:
        pair_name = sf.name.replace("_stripped.jsonl", "")
        s_entries = _load_jsonl(sf)
        i_entries = _load_jsonl(ijf)
        i_by_rid = {e["request_id"]: e for e in i_entries}

        for s_entry in s_entries:
            rid = s_entry["request_id"]
            i_entry = i_by_rid.get(rid, {})

            _analyse_sys_delta(s_entry, i_entry, strip_stats, inject_stats)
            _analyse_tools_delta(s_entry, i_entry, strip_stats, inject_stats)
            _analyse_messages_delta(pair_name, s_entry, i_entry, strip_stats, inject_stats,
                                    residuals, false_positives, attribute_chunk)
            _analyse_fields_delta(pair_name, s_entry, i_entry, strip_stats, inject_stats, residuals)

    return dict(strip_stats), dict(inject_stats), residuals, false_positives
