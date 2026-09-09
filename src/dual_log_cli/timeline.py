# INFRASTRUCTURE
from .reader import infer_family, load_last_request
from .timeline_boundaries import build_turn_times, request_boundaries
from .timeline_turns import build_turns

# FUNCTIONS


# Load everything a command needs for one session: the last request's payload plus its msg rows
def load_timeline(session: dict) -> dict:
    original = session["streams"].get("original")
    if original is None:
        raise FileNotFoundError(f"no _original stream for {session['stem']}")
    entry, line_bytes, skipped = load_last_request(original)
    if entry is None:
        raise ValueError(f"no non-haiku request line in {original.name}")
    payload = entry.get("payload", {}) or {}
    family = infer_family(entry.get("model", ""))
    forwarded = session["streams"].get("forwarded")
    boundaries = request_boundaries(forwarded, family) if forwarded else []
    return {
        "session": session,
        "entry": entry,
        "payload": payload,
        "family": family,
        "line_bytes": line_bytes,
        "haiku_lines_skipped": skipped,
        "turns": build_turns(payload),
        "boundaries": boundaries,
        "turn_times": build_turn_times(boundaries),
    }
