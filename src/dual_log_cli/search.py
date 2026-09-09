# INFRASTRUCTURE
from .classifier import matches_only
from .timeline_turns import iter_block_texts

# FUNCTIONS


# Find every block of the deduplicated timeline that contains term; returns the hit list.
#
# One hit per (turn, block) — the block is the unit because a hit reports a block label, and a
# block holding the term one or more times still stays ONE hit. Deduplication is structural, not a
# post-filter: the searched payload is the single last request, which already embeds the whole
# conversation, so a term is never re-reported per request that resent it.
# An empty term matches nothing rather than every block, guarded before the loop even starts.
# `only` is a parsed (role, type) pair from classifier.parse_only — it restricts which MESSAGES
# contribute hits (role plus any-block-type), exactly like expand's --only.
# `chars` on each hit is the block's original-payload chars — the same value `msgs` and `expand`
# show for that block (see `timeline.iter_block_texts`) — not a re-measurement of `text`.
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
