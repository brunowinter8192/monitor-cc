# Proxy Pane Expand/Collapse Undo ('u' key), 2026-07-21

## Motivation

The proxy pane (`src/proxy_display/pane.py`) lets the user expand/collapse individual req entries by click. No way to revert an accidental toggle — re-clicking works but requires re-locating the same row, awkward once the viewport has scrolled or re-rendered. Added vim-style undo bound to `'u'`, walking back through toggle history one step per press (cmd+z was considered and rejected — the terminal eats Cmd, and cbreak mode keeps Ctrl+Z bound to the OS suspend signal, so neither is usable; `'u'` was unused in this pane and matches vim-undo convention).

## Scope decision

Undo covers ONLY expand/collapse toggles — not scroll, copy, or hover. Rationale: those are either already trivially reversible (scroll: just scroll back) or not meaningfully "undoable" as a discrete user action (hover is transient state, copy has no visible side effect to revert). Keeping the undo stack narrowly scoped avoids conflating unrelated interaction types into one history.

## Design

- `_proxy_undo_stack: list[(key, prev_state)]`, module-level, capped at 200 entries (oldest dropped via `pop(0)` on overflow) — bounds memory without needing a deque import for a rarely-large list.
- Push happens at exactly one site: the `else` branch in `_handle_proxy_mouse` under `button == 0` (the actual expand-toggle branch), immediately before the state flip. The sibling copy-column branch (same `button == 0` handler, different column range) and the scroll (64/65) / hover (>=32) branches do not push — confirmed by placement, not a filter check, since those branches never reach the toggle code path at all.
- `_undo_proxy_expand()` pops LIFO and restores `proxy_expand_states[key] = prev_state`. Deliberately does NOT re-trigger `_lazy_load_messages_forwarded` or set `_proxy_just_expanded`: any entry that was ever expanded already had its messages lazy-loaded on that first expand-click, and lazy-loaded messages are never evicted by collapse (only by the deque-bound eviction in `_strip_inactive_messages` after `PROXY_MESSAGES_KEEP_LAST` entries age out) — so undo-to-expanded needs no reload, and undo-to-collapsed needs none either. Setting `_proxy_just_expanded` would trigger the auto-scroll-to-item behavior, which is not desired for an undo (undo should not jerk the viewport).
- Session-change reset (`_refresh_proxy_data`, on new main session detected) clears `_proxy_undo_stack` alongside `proxy_expand_states` — a stale key referencing a prior session's entries must not be undoable into a display that no longer holds that data.
- Deliberately excluded from `_proxy_ram_state`: the stack is hard-capped at 200 tuples of small primitives, no unbounded-growth risk, so it doesn't need RAM-audit visibility (unlike the other tracked state which can grow with session length).

## Verification — this session

`py_compile` clean. Unit harness against the real `_undo_proxy_expand`/`proxy_expand_states`/`_proxy_undo_stack` (imported directly from `src.proxy_display.pane`, not reimplemented): single-toggle undo restores prior state and returns `True`; undo on an empty stack returns `False` and is a no-op; two pushes for different keys pop in LIFO order (second push undone first). All three passed. The real `'u'`-keypress-in-terminal path (cbreak mode, `read_keypress()` inside the live running pane loop) was not exercised — that is the user's live follow-up test, not reproducible from a worker session without a running terminal pane.
