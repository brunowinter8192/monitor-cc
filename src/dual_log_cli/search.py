# INFRASTRUCTURE
from .classifier import matches_only
from .timeline_turns import iter_block_texts

# FUNCTIONS


def find_matches(payload: dict, term: str, case_sensitive: bool = False, only=("", "")) -> list:
    needle = term if case_sensitive else term.lower()
    if not needle:
        return []
    hits = []
    for block in iter_block_texts(payload):
        if not matches_only(block["role"], block["block_types"], only):
            continue
        text = block["text"]
        haystack = text if case_sensitive else text.lower()
        if needle not in haystack:
            continue
        hits.append({
            "turn": block["turn"],
            "role": block["role"],
            "block": block["block"],
            "label": block["label"],
            "chars": block["chars"],
        })
    return hits
