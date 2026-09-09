# INFRASTRUCTURE
from ..proxy_display.dual_log_accumulator import accumulate_dual_log
from .timeline_markers import request_numbers_by_flow

# FUNCTIONS


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


def _owners_by_flow_key(fam_stripped: dict, fam_injected: dict, by_flow_key: str) -> dict:
    owners: dict = {}
    for fam in (fam_stripped, fam_injected):
        for flow_id, keys in (fam.get(by_flow_key) or {}).items():
            for key in keys:
                owners.setdefault(key, flow_id)
    return owners


def _owners_by_index(fam_stripped: dict, fam_injected: dict) -> dict:
    owners = _owners_by_flow_key(fam_stripped, fam_injected, "_msg_idx_by_flow_id")
    for flow_id, indices in (fam_stripped.get("_lag_msg_idx_by_flow_id") or {}).items():
        for index in indices:
            owners[index] = flow_id
    return owners


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
