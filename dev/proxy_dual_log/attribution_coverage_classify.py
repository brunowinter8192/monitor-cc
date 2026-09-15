# INFRASTRUCTURE

# Inject function map for sys delta and fields delta
_SYS_INJECT_FN = {
    "2": "_apply_system_passes (proxy rules injected)",
    "3": "_strip_sys3: '.' stub (sys[3] blanked to '.')",
}
_FIELD_INJECT_FN = {
    "max_tokens":          "_inject_model_override",
    "model":               "_inject_model_override",
    "thinking":            "_inject_model_override",
    "output_config":       "_inject_model_override",
    "context_management":  "_inject_context_management",
}
_FIELD_STRIP_FN = {
    "max_tokens":   "_inject_model_override (orig replaced)",
    "model":        "_inject_model_override (orig replaced)",
    "thinking":     "_inject_model_override (orig replaced)",
    "output_config": "_inject_model_override (orig replaced)",
    "context_management": "_strip_clear_thinking_edit (removed: thinking disabled)",
}

# FUNCTIONS

# Detect new injected span format: first item in a list is a [tag, text] pair
def _is_new_format(v: list) -> bool:
    if not v:
        return False
    first = v[0]
    return isinstance(first, list) and len(first) == 2 and first[0] in ("equal", "injected", "stripped")


# Extract plain text from an injected list (handles both old flat-string and new span-tuple formats)
def _inject_text(v: list) -> str:
    if not v:
        return ""
    if _is_new_format(v):
        return " ".join(t for _, t in v if t)
    return " ".join(str(x) for x in v if x)


# Check if an inject block value is a json_reserialization artifact
# Old format: first item is a JSON string starting with '[{"type":'
# New format: the injected span text starts with '[{"type":'
def _is_json_reser(i_bv: list) -> bool:
    if not i_bv:
        return False
    if _is_new_format(i_bv):
        for tag, text in i_bv:
            if tag == "injected" and isinstance(text, str) and text.startswith('[{"type":'):
                return True
        return False
    first = i_bv[0]
    return isinstance(first, str) and first.startswith('[{"type":')


# Classify a stripped message block → (tier, category)
# tier: 'vocab' | 'residual' | 'false_pos' | 'unattr'
# Vocab/residual checks run FIRST: a TN block whose message was also json_reserialized
# should be classified TN (the proxy strip), not json_reser (the format-change side-effect).
def _classify_strip_msg(s_texts: list, i_bv: list, attribute_chunk) -> tuple:
    # Known strip_vocab markers: check each stripped text chunk independently
    for text in s_texts:
        code = attribute_chunk(text)
        if code and code != "ALL":
            return ("vocab", code)

    # False positive: json_reserialization (string content → block-list, cache.py side effect)
    # Only checked AFTER all proxy-strip patterns fail — json_reser is the fallback for
    # blocks whose injected counterpart is a block-list JSON string but carry no strip marker.
    if _is_json_reser(i_bv):
        return ("false_pos", "json_reser")

    return ("unattr", "UNATTR")


# Classify an inject message block → (tier, category)
def _classify_inject_msg(i_bv: list, s_bv_exists: bool) -> tuple:
    # json_reserialization artifact (appears at same midx/bidx as a stripped entry)
    if s_bv_exists and _is_json_reser(i_bv):
        return ("false_pos", "json_reser")
    # BGK replacement injection: background done text
    i_text = _inject_text(i_bv)
    if "background done" in i_text:
        return ("vocab", "BGK_replacement")
    if s_bv_exists:
        return ("false_pos", "json_reser_combined")
    return ("unattr", "UNATTR")


# Compute coverage percentage numerics
def _coverage(stats: dict, false_pos_key: str | None = None) -> tuple:
    total = sum(n for section in stats.values() for n in section.values())
    fp = sum(stats.get("msg", {}).get(k, 0)
             for k in ("json_reser", "json_reser_combined"))
    unattr = sum(stats.get(sec, {}).get("UNATTR", 0) for sec in stats)
    attributed = total - fp - unattr
    raw_pct = 100.0 * attributed / total if total else 0.0
    adj_denom = total - fp
    adj_pct = 100.0 * attributed / adj_denom if adj_denom else 0.0
    return total, attributed, 0, fp, unattr, raw_pct, adj_pct
