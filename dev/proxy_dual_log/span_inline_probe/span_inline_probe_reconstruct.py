# INFRASTRUCTURE
import json
from pathlib import Path

# FUNCTIONS

def _load_jsonl(path: Path) -> list:
    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries


def _infer_family(model: str) -> str:
    m = model.lower()
    if "haiku" in m:
        return "haiku"
    if "sonnet" in m:
        return "sonnet"
    return "opus"


def _reconstruct_chains(fwd_entries: list) -> list:
    chain_states = {}
    result = []
    for entry in fwd_entries:
        if entry.get("type") != "forwarded_delta":
            result.append(None)
            continue
        family = _infer_family(entry.get("model", ""))
        counts = entry.get("counts", {})
        if entry.get("is_first"):
            state = {}
            for cat in ("system", "tools", "messages"):
                lst = [None] * counts.get(cat, 0)
                for idx_str, elem in entry.get(f"{cat}_delta", {}).items():
                    i = int(idx_str)
                    if i < len(lst):
                        lst[i] = elem
                state[cat] = lst
        else:
            prev = chain_states.get(family, {"system": [], "tools": [], "messages": []})
            state = {}
            for cat in ("system", "tools", "messages"):
                lst = list(prev[cat])
                for idx_str, elem in entry.get(f"{cat}_delta", {}).items():
                    i = int(idx_str)
                    while len(lst) <= i:
                        lst.append(None)
                    lst[i] = elem
                state[cat] = lst[:counts.get(cat, len(lst))]
        chain_states[family] = state
        result.append(state)
    return result


def _match_requests(orig_entries: list, fwd_entries: list, fwd_states: list) -> list:
    orig_by_reqid = {}
    orig_queues = {}
    for oe in orig_entries:
        reqid = oe.get("request_id", "")
        family = _infer_family(oe.get("model", ""))
        if reqid:
            orig_by_reqid[reqid] = oe
        orig_queues.setdefault(family, []).append(oe)
    cursors = {}
    result = []
    for fe, fs in zip(fwd_entries, fwd_states):
        if fs is None:
            continue
        family = _infer_family(fe.get("model", ""))
        reqid = fe.get("request_id", "")
        if reqid and reqid in orig_by_reqid:
            oe = orig_by_reqid[reqid]
        else:
            q = orig_queues.get(family, [])
            c = cursors.get(family, 0)
            oe = q[c] if c < len(q) else None
            cursors[family] = c + 1
        if oe is not None:
            result.append((oe, fe, fs))
    return result
