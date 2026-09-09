# INFRASTRUCTURE
from typing import List

from ..utils import _ANSI_ESCAPE_RE
from .format import _is_standalone_entry
from .render_turn import _render_req_expanded, _resolve_prev_same_family

# FUNCTIONS

def _entry_matches_query(entry_idx: int, entries: list, expand_states: dict, pane_width: int, query: str) -> bool:
    entry = entries[entry_idx]
    is_standalone = _is_standalone_entry(entry)
    prev_same = _resolve_prev_same_family(entries, entry_idx)
    lines, _keys = _render_req_expanded(entry_idx, entry, entries, is_standalone, prev_same, expand_states, pane_width)
    q = query.lower()
    return any(q in _ANSI_ESCAPE_RE.sub('', line).lower() for line in lines)

def build_search_matches(query: str, entries: list, expand_states: dict, pane_width: int) -> List[int]:
    if not query:
        return []
    return [
        entry_idx for entry_idx in range(len(entries))
        if _entry_matches_query(entry_idx, entries, expand_states, pane_width, query)
    ]
