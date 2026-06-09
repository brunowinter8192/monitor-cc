# INFRASTRUCTURE
from typing import Optional

from ..constants import RESET, YELLOW, DIM, WHITE, PROXY_MESSAGES_KEEP_LAST
from .format import _is_standalone_entry

# FUNCTIONS

# Build header line for worker-proxy pane listing workers with current selection marked
def _format_worker_proxy_header(workers: list, current_worker: Optional[str]) -> str:
    label = f"{YELLOW}WORKER-PROXY{RESET}  "
    if not workers:
        return label + f"{DIM}no workers{RESET}"
    parts = []
    for i, w in enumerate(workers, 1):
        name = w['name']
        star = '*' if name == current_worker else ''
        if name == current_worker:
            parts.append(f"{WHITE}[{i}{star}]{name}{RESET}")
        else:
            parts.append(f"{DIM}[{i}]{name}{RESET}")
    return label + '  '.join(parts)

# Extract entry_idx from any proxy line_map key variant (shared with pane.py pattern)
def _wp_entry_idx_from_key(key) -> Optional[int]:
    if isinstance(key, int):
        return key
    if isinstance(key, tuple):
        if isinstance(key[0], str):
            return key[1]
        if isinstance(key[0], int):
            return key[0]
    return None

# Walk backward from k-1 to find first non-standalone entry idx (prev_same reference)
def _resolve_prev_same_wp(entries: list, k: int) -> Optional[int]:
    for i in range(k - 1, -1, -1):
        if not _is_standalone_entry(entries[i]):
            return i
    return None

# Strip messages from all entries outside the keep-last window that are not expanded
def _strip_inactive_wp_messages(entries: list, expand_states: dict) -> None:
    cutoff = max(0, len(entries) - PROXY_MESSAGES_KEEP_LAST)
    for i in range(cutoff):
        e = entries[i]
        if e.get('messages') is None:
            continue
        is_active = (
            expand_states.get(i, False) or
            expand_states.get(('req', i), False) or
            expand_states.get((i, 'neg_delta'), False)
        )
        if not is_active:
            del e['messages']
