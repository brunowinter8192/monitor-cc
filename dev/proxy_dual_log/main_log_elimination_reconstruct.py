# INFRASTRUCTURE
import json

# Fields classification: which raw_payload top-level fields are needed by proxy pane vs metadata-only
_PROXY_PANE_FIELDS = {
    "model": "already in _forwarded entry.model",
    "max_tokens": "MUST-ADD — proxy pane header: think:Nk via _fmt_thinking_budget(max_tokens)",
    "output_config": "MUST-ADD — proxy pane header: eff:X via output_config.effort → effort_value",
}
_METADATA_PANE_FIELDS = {
    "temperature": "metadata-pane-only → irrelevant after deletion",
    "top_p": "metadata-pane-only → irrelevant after deletion",
    "top_k": "metadata-pane-only → irrelevant after deletion",
    "tool_choice": "metadata-pane-only → irrelevant after deletion",
    "thinking": "metadata-pane-only (thinking_config/budget_tokens); proxy pane uses max_tokens directly",
    "context_management": "metadata-pane-only → irrelevant after deletion",
    "metadata": "metadata-pane-only (request metadata) → irrelevant after deletion",
    "diagnostics": "metadata-pane-only → irrelevant after deletion",
    "stream": "metadata-pane-only → irrelevant after deletion",
}
# system / tools / messages are reconstructed from the delta; model is in the delta entry header
_DELTA_COVERED = {"system", "tools", "messages", "model"}

# FUNCTIONS

# Recursively strip cache_control keys — verbatim copy of src/proxy/logging.py:_strip_cache_control
def _strip_cache_control(obj):
    if isinstance(obj, dict):
        return {k: _strip_cache_control(v) for k, v in obj.items() if k != "cache_control"}
    if isinstance(obj, list):
        return [_strip_cache_control(item) for item in obj]
    return obj


# Mirror of cache._normalize_user_content_shape — verbatim copy of src/proxy/logging.py:_normalize_msg_shape_for_hash
def _normalize_msg_shape_for_hash(msg: dict) -> dict:
    if msg.get("role") != "user":
        return msg
    content = msg.get("content")
    if not isinstance(content, list) or len(content) != 1:
        return msg
    block = content[0]
    if not isinstance(block, dict):
        return msg
    if set(block.keys()) == {"type", "text"} and block["type"] == "text":
        return {**msg, "content": block["text"]}
    return msg


# Infer model family from model string — mirrors src/proxy_display/parser.py:_infer_model_family
def _infer_family(model: str) -> str:
    m = model.lower()
    if "haiku" in m:
        return "haiku"
    if "sonnet" in m:
        return "sonnet"
    return "opus"


# Count cache_control markers recursively in a payload element
def _count_cache_control(obj) -> int:
    if isinstance(obj, dict):
        count = 1 if "cache_control" in obj else 0
        return count + sum(_count_cache_control(v) for v in obj.values())
    if isinstance(obj, list):
        return sum(_count_cache_control(item) for item in obj)
    return 0


# Reconstruct full forwarded payloads from the delta stream, per-model-family.
# Returns list of dicts matching order of forwarded entries:
#   {model, system, tools, messages, is_first, counts}
def _reconstruct_forwarded(fwd_entries: list) -> list:
    chain: dict = {}  # family → {system: [], tools: [], messages: []}
    results = []
    for entry in fwd_entries:
        if entry.get("type") != "forwarded_delta":
            continue
        model = entry.get("model", "")
        family = _infer_family(model)
        is_first = entry.get("is_first", False)
        counts = entry.get("counts", {})

        if is_first:
            curr = {
                "system": _dict_to_list(entry.get("system_delta", {}), counts.get("system", 0)),
                "tools": _dict_to_list(entry.get("tools_delta", {}), counts.get("tools", 0)),
                "messages": _dict_to_list(entry.get("messages_delta", {}), counts.get("messages", 0)),
            }
        else:
            prev = chain.get(family, {"system": [], "tools": [], "messages": []})
            curr = {}
            for cat in ("system", "tools", "messages"):
                lst = list(prev[cat])
                for idx_str, elem in entry.get(f"{cat}_delta", {}).items():
                    i = int(idx_str)
                    while len(lst) <= i:
                        lst.append(None)
                    lst[i] = elem
                curr[cat] = lst[:counts.get(cat, len(lst))]

        chain[family] = curr
        results.append({
            "model": model,
            "family": family,
            "is_first": is_first,
            "counts": counts,
            "system": curr["system"],
            "tools": curr["tools"],
            "messages": curr["messages"],
        })
    return results


# Expand {idx_str: elem} dict into list of length n, filling gaps with None
def _dict_to_list(d: dict, n: int) -> list:
    lst = [None] * n
    for idx_str, elem in d.items():
        i = int(idx_str)
        if i < n:
            lst[i] = elem
    return lst


# Normalize a reconstructed element for comparison: strip cache_control + normalize msg shape
def _normalize_elem(elem, is_message: bool = False) -> str:
    stripped = _strip_cache_control(elem)
    if is_message and isinstance(stripped, dict):
        stripped = _normalize_msg_shape_for_hash(stripped)
    return json.dumps(stripped, sort_keys=True)


# Return list of (idx, note) for element-level divergences between two normalized lists
def _element_divergences(a: list, b: list) -> list:
    divs = []
    if len(a) != len(b):
        divs.append(f"count: {len(a)} vs {len(b)}")
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            divs.append(f"elem[{i}] differs")
    return divs


# Classify raw_payload keys into delta-covered, proxy-pane-needed, metadata-only, other
def _classify_fields(keys: set) -> list:
    rows = []
    for k in sorted(keys):
        if k in _DELTA_COVERED:
            rows.append((k, "delta-covered", "reconstructed from _forwarded delta"))
        elif k in _PROXY_PANE_FIELDS:
            rows.append((k, "MUST-ADD", _PROXY_PANE_FIELDS[k]))
        elif k in _METADATA_PANE_FIELDS:
            rows.append((k, "metadata-pane-only", _METADATA_PANE_FIELDS[k]))
        else:
            rows.append((k, "UNCLASSIFIED", "not in classification table — needs manual review"))
    return rows
