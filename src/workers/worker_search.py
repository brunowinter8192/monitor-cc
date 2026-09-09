# INFRASTRUCTURE
from ..panes.token_search import build_token_search_matches

# FUNCTIONS

def workers_search_on_commit(state, workers: list, project_filter, pane_width: int,
                              worker_turns: dict, load_turns_fn, jump_fn) -> None:
    if not state.query:
        state.matches = []
        state.match_set = set()
        return
    q = state.query.lower()
    matches: list = []
    fresh_turns: dict = {}
    for w in workers:
        name = w.get('name', '')
        if not name:
            continue
        purpose = w.get('purpose', '') or ''
        if q in f"{name} {purpose}".lower():
            matches.append(name)
        turns = load_turns_fn(w.get('session', ''))
        if turns is None:
            continue
        fresh_turns[name] = turns
        for key in build_token_search_matches(state.query, turns, pane_width - 4):
            matches.append((name, 'turn', key[1]) if key[0] == 'turn' else (name, key[0], key[1]))
    state.matches = matches
    state.match_set = set(matches)
    state.current_idx = 0
    matched_names = {m if isinstance(m, str) else m[0] for m in matches}
    for name in matched_names:
        if name in fresh_turns:
            worker_turns[name] = fresh_turns[name]
    if matches:
        jump_fn()
