# INFRASTRUCTURE
from typing import List

from ..utils import _ANSI_ESCAPE_RE
from ..format.token_format import _format_turn_header_line, _format_cache_call, _call_thinking_meta, _render_expanded_call_lines

# FUNCTIONS

def _call_matches_query(call: dict, request_num: int, wide: bool, response_rid_map: dict, q: str) -> bool:
    has_thinking, sig_chars = _call_thinking_meta(call)
    header = _format_cache_call(
        '▼', call.get('cache_read', 0), call.get('cache_creation', 0), call.get('direct', 0),
        call.get('output_tokens', 0), wide, request_num, has_thinking, sig_chars,
    )
    if q in _ANSI_ESCAPE_RE.sub('', header).lower():
        return True
    exp_lines, _keys = _render_expanded_call_lines(call, response_rid_map)
    return any(q in _ANSI_ESCAPE_RE.sub('', line).lower() for line in exp_lines)

def build_token_search_matches(query: str, turns: list, pane_width: int, response_rid_map: dict = None) -> List:
    if not query:
        return []
    q = query.lower()
    wide = pane_width >= 60
    matches = []
    request_num = 0
    for turn_idx, turn in enumerate(turns):
        turn_line = _format_turn_header_line(turn_idx, turn, pane_width)
        if q in _ANSI_ESCAPE_RE.sub('', turn_line).lower():
            matches.append(('turn', turn_idx))
        for call_idx, call in enumerate(turn.get('api_calls', [])):
            request_num += 1
            if _call_matches_query(call, request_num, wide, response_rid_map, q):
                matches.append((turn_idx, call_idx))
    return matches
