# INFRASTRUCTURE
import json
from difflib import SequenceMatcher

RATIO_THRESHOLD = 0.1
_COLLECTION_KEYS = frozenset({"system", "tools", "messages"})

# FUNCTIONS

# Extract text string from a system/tool/message block
def _get_text(element) -> str:
    if element is None:
        return ""
    if isinstance(element, str):
        return element
    if isinstance(element, dict):
        t = element.get("text")
        if t is not None:
            return str(t)
        return json.dumps(element, ensure_ascii=False)
    return json.dumps(element, ensure_ascii=False)


# Span diff: equal / stripped / injected. ratio < RATIO_THRESHOLD → whole-block 2 spans.
def _diff_text(orig_text: str, fwd_text: str) -> list:
    if orig_text == fwd_text:
        return [("equal", orig_text)]
    if not orig_text:
        return [("injected", fwd_text)]
    if not fwd_text:
        return [("stripped", orig_text)]
    ratio = SequenceMatcher(None, orig_text, fwd_text).ratio()
    if ratio < RATIO_THRESHOLD:
        return [("stripped", orig_text), ("injected", fwd_text)]
    spans = []
    ow, fw = orig_text.split(), fwd_text.split()
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, ow, fw).get_opcodes():
        if tag == "equal":
            spans.append(("equal", " ".join(ow[i1:i2])))
        elif tag == "delete":
            spans.append(("stripped", " ".join(ow[i1:i2])))
        elif tag == "insert":
            spans.append(("injected", " ".join(fw[j1:j2])))
        else:
            spans.append(("stripped", " ".join(ow[i1:i2])))
            spans.append(("injected", " ".join(fw[j1:j2])))
    return spans


# Count stripped and injected spans
def _span_counts(spans: list) -> tuple:
    return (sum(1 for t, _ in spans if t == "stripped"),
            sum(1 for t, _ in spans if t == "injected"))


# Diff system blocks by index
def _diff_system(orig_sys: list, fwd_sys: list) -> list:
    n = max(len(orig_sys), len(fwd_sys)) if (orig_sys or fwd_sys) else 0
    diffs = []
    for i in range(n):
        ob = orig_sys[i] if i < len(orig_sys) else None
        fb = fwd_sys[i] if i < len(fwd_sys) else None
        o_text, f_text = _get_text(ob), _get_text(fb)
        diffs.append({"idx": i, "o_text": o_text, "f_text": f_text, "spans": _diff_text(o_text, f_text)})
    return diffs


# Diff tools by name: whole-stripped, whole-injected, description-changed
def _diff_tools(orig_tools: list, fwd_tools: list) -> dict:
    orig_by_name = {t.get("name", "?"): t for t in orig_tools if isinstance(t, dict)}
    fwd_by_name  = {t.get("name", "?"): t for t in fwd_tools  if isinstance(t, dict)}
    orig_order = [t.get("name", "?") for t in orig_tools if isinstance(t, dict)]
    stripped, injected, desc_changes, identical = [], [], [], []
    for name in orig_order:
        ot = orig_by_name[name]
        if name not in fwd_by_name:
            stripped.append(name)
        else:
            ft = fwd_by_name[name]
            o_desc = ot.get("description", "") or ""
            f_desc = ft.get("description", "") or ""
            if o_desc != f_desc:
                desc_changes.append((name, o_desc, f_desc, _diff_text(o_desc, f_desc)))
            else:
                identical.append(name)
    for name in fwd_by_name:
        if name not in orig_by_name:
            injected.append(name)
    return {"stripped": stripped, "injected": injected, "desc_changes": desc_changes, "identical": identical}


# Diff messages by index, within each message by block position
def _diff_messages(orig_msgs: list, fwd_msgs: list) -> list:
    n = max(len(orig_msgs), len(fwd_msgs)) if (orig_msgs or fwd_msgs) else 0
    result = []
    for i in range(n):
        om = orig_msgs[i] if i < len(orig_msgs) else None
        fm = fwd_msgs[i] if i < len(fwd_msgs) else None
        if om is None:
            f_text = _get_text(fm)
            result.append({"idx": i, "block_diffs": [
                {"bidx": 0, "o_text": "", "f_text": f_text, "spans": [("injected", f_text)]}
            ]})
            continue
        if fm is None:
            o_text = _get_text(om)
            result.append({"idx": i, "block_diffs": [
                {"bidx": 0, "o_text": o_text, "f_text": "", "spans": [("stripped", o_text)]}
            ]})
            continue
        o_content = om.get("content", "")
        f_content = fm.get("content", "")
        if isinstance(o_content, list) and isinstance(f_content, list):
            nb = max(len(o_content), len(f_content))
            block_diffs = []
            for bi in range(nb):
                ob = o_content[bi] if bi < len(o_content) else None
                fb = f_content[bi] if bi < len(f_content) else None
                o_text, f_text = _get_text(ob), _get_text(fb)
                block_diffs.append({"bidx": bi, "o_text": o_text, "f_text": f_text, "spans": _diff_text(o_text, f_text)})
        else:
            o_text = o_content if isinstance(o_content, str) else json.dumps(o_content)
            f_text = f_content if isinstance(f_content, str) else json.dumps(f_content)
            block_diffs = [{"bidx": 0, "o_text": o_text, "f_text": f_text, "spans": _diff_text(o_text, f_text)}]
        result.append({"idx": i, "block_diffs": block_diffs})
    return result


# Diff all non-collection top-level payload keys by value equality — returns list of change records
def _diff_top_level_fields(orig_payload: dict, fwd_payload: dict) -> list:
    result = []
    all_keys = set(orig_payload.keys()) | set(fwd_payload.keys())
    for key in sorted(all_keys):
        if key in _COLLECTION_KEYS:
            continue
        in_orig = key in orig_payload
        in_fwd = key in fwd_payload
        if not in_orig:
            result.append({"key": key, "tag": "injected", "orig": None, "fwd": fwd_payload[key]})
        elif not in_fwd:
            result.append({"key": key, "tag": "stripped", "orig": orig_payload[key], "fwd": None})
        elif orig_payload[key] != fwd_payload[key]:
            result.append({"key": key, "tag": "replaced", "orig": orig_payload[key], "fwd": fwd_payload[key]})
    return result
