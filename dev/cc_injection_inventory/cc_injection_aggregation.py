# INFRASTRUCTURE
from cc_injection_classification import _classify_segment


# FUNCTIONS

def _process_segment_occurrence(key, dedup_seen: dict, registry: dict, pending: dict, counters: dict,
                                 role, section, block_type, text, tool_name, sys_idx=None) -> None:
    counters["raw_segments"] += 1
    if key in dedup_seen:
        for kind, ref, chars in dedup_seen[key]:
            if kind == "CLASS":
                registry[ref]["chars"] += chars
            else:
                pending[ref]["chars"] += chars
        return
    counters["distinct_segments"] += 1
    hits = _classify_segment(role, section, block_type, text, tool_name, sys_idx)
    cache_entries = []
    for h in hits:
        if h.kind == "CLASS":
            _touch_class(registry, h.ref, h.label, h.origin, role, section, block_type, h.sample, h.chars)
        else:
            _touch_pending(pending, h.ref, role, section, block_type, h.sample, h.chars)
        cache_entries.append((h.kind, h.ref, h.chars))
    dedup_seen[key] = cache_entries


def _touch_class(registry, class_key, label, origin, role, section, block_type, sample, chars) -> None:
    rec = registry.get(class_key)
    if rec is None:
        registry[class_key] = {"label": label, "origin": origin, "role": role, "section": section,
                                "block_type": block_type, "count": 1, "chars": chars, "sample": sample}
    else:
        rec["count"] += 1
        rec["chars"] += chars


def _touch_pending(pending, sig, role, section, block_type, sample, chars) -> None:
    rec = pending.get(sig)
    if rec is None:
        pending[sig] = {"role": role, "section": section, "block_type": block_type,
                         "count": 1, "chars": chars, "sample": sample,
                         "variants": {(sample or "").strip()}}
    else:
        rec["count"] += 1
        rec["chars"] += chars
        rec["variants"].add((sample or "").strip())


def _distinct_variant_count(variants: set) -> int:
    ordered = sorted((v for v in variants if v), key=len, reverse=True)
    kept: list = []
    for v in ordered:
        if not any(v in longer for longer in kept):
            kept.append(v)
    return len(kept)


def _finalize_pending_user_text(pending: dict, registry: dict) -> None:
    singleton_count = singleton_chars = 0
    singleton_sample = None
    for sig, stat in pending.items():
        if _distinct_variant_count(stat["variants"]) >= 2 and len(stat["sample"] or "") >= 40:
            registry[f"UNCLASSIFIED:user_text:{sig}"] = {
                "label": f'Recurring unattributed user-message text ("{sig}")',
                "origin": "UNCLASSIFIED", "role": stat["role"], "section": stat["section"],
                "block_type": stat["block_type"], "count": stat["count"], "chars": stat["chars"],
                "sample": stat["sample"],
            }
        else:
            singleton_count += stat["count"]
            singleton_chars += stat["chars"]
            if singleton_sample is None:
                singleton_sample = stat["sample"]
    if singleton_count:
        registry["OURS:user_typed_message"] = {
            "label": "User typed message (unique one-off text, no recurring template detected)",
            "origin": "OURS", "role": "user", "section": "messages", "block_type": "text/plain_string",
            "count": singleton_count, "chars": singleton_chars, "sample": singleton_sample,
        }
