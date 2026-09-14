# 2026-09-14 — Milestone 5: per-message copy click in the proxy pane

## Problem

The proxy pane (main `pane.py` and worker `worker_proxy_pane.py`, sharing machinery through
`proxy_pane_shared.py`) already supported copying a whole REQ via a click on the row's `⎘`/`✓`
symbol. A single message inside an expanded REQ — the `[msg_idx] role  type  chars` rows built by
`render_messages.py`'s `_render_new_messages`/`_render_modified_messages` — carried no key at all
(`keys.append(None)`), so a click anywhere on one did nothing. The `[STRIPPED]` variant
(`_render_stripped_block`) is deliberately out of scope — its serialization (marker text? removed
original? replacement chunks?) is a separate, unspecified design decision.

## Key shape and dispatch

New key: `('msg', entry_idx, msg_idx)` — a 3-tuple, distinct from `('req', entry_idx)` (2-tuple)
and the existing `('think', entry_idx, msg_idx, bidx)` (4-tuple) drill-down key.
`_handle_proxy_mouse`/`_handle_worker_proxy_mouse` (mirrored, matching how `is_req` was already
duplicated identically between the two files rather than shared) gained `is_msg`, OR'd into the
existing copy-column branch, with an explicit `elif is_msg: return had_selection` — without that
branch a non-copy click on a msg row would fall into the generic expand-click path and start
mutating `expand_states`/the undo stack, which these rows never did before (key=None short-circuits
before reaching any handler at all).

## Where the serializer lives, and the substring-invariant design (moved here per review)

`_serialize_proxy_message` lives in `proxy_pane_shared.py`, next to the pre-existing
`_serialize_proxy_entry` — the one file both panes already share exclusively for this. `
_prepare_copy_text` dispatches on key shape so `_handle_proxy_copy_click`/
`_handle_worker_proxy_copy_click` needed no changes at all.

The substance of a comment removed from the function per review (code standard allows only the
three section-marker comment lines in a module; explanatory comments belong here instead):
`_serialize_proxy_message` builds its `parts` list using the exact same per-block separator shape
`_serialize_proxy_entry` uses — every block header carries its own leading `\n`
(`f"\n--- msg[{msg_idx}] ... ---"`), so consecutive blocks/messages get a blank-line separator
there — then the final `'\n'.join(parts)` result is `.lstrip('\n')`-ed to drop ONLY the one
resulting leading newline, since a standalone message copy has no preceding REQ-summary line to
separate from the way `_serialize_proxy_entry`'s own `entry_idx=... model=... msgs=...` line does.
This is what makes a message's copy text a byte-exact substring of what `_serialize_proxy_entry`
produces for that same message inside a full REQ copy — verified directly in
`dev/click_ui/p5_proxy_message_copy_click_probe.py` (`test_message_copy_matches_serializer_and_req_subset`:
`msg0_text in req_text`). First version omitted the leading `\n` entirely (no blank-line
separation between a multi-block message's own blocks) and failed that exact substring check —
the header shape has to match `_serialize_proxy_entry`'s literally, not just resemble it, for the
invariant to hold.

## The copy-feedback keying fix — not cosmetic, load-bearing

`_copy_feedback_until`/`_worker_copy_feedback_until` were keyed by plain `entry_idx`
(`_build_req_header_line` reads `copy_feedback.get(entry_idx, 0)`). Reusing that for message rows
would have made copying ONE message flash the REQ header AND every sibling message row sharing
that `entry_idx` — the flash would lie about what was actually copied. Fix: a new shared
`_copy_feedback_key(key, entry_idx)` returns the full `key` for a `('msg', ...)` row and plain
`entry_idx` for everything else (REQ rows unchanged, still read by `_build_req_header_line`
exactly as before). Verified in isolation
(`dev/click_ui/p5_proxy_message_copy_click_probe.py`, "flash keyed by the msg's own key" /
"sibling msg row does NOT flash").

## The zebra/hover side effect — confirmed intended, not suppressed

Once a msg row carries a real (non-`None`) key, `format.py`'s `_apply_row_backgrounds` starts
alternating its zebra background and making it hover-eligible — both gated purely on `key is not
None`, with no awareness of key TYPE. This was flagged in planning and explicitly confirmed as the
correct consequence, not a bug: every other genuinely-interactive row in this pane (REQ headers,
thinking-block headers) already participates in zebra/hover; only purely-informational rows
(block-header lines, block content) stay `key=None`/flat. A msg row becoming copyable is exactly
the "genuinely interactive" transition that earns it the same treatment. Not suppressed.

## render_byte_identity.py — hash changed, verified why

Pinned via `RENDER_BYTE_IDENTITY_LOG_DIR` against a frozen copy of this worktree's own live-growing
forwarded/stripped/injected/original quartet (210 entries). Before:
`5338aefd56b1319c20dee1caf420ff01dd22d56abca8f5295d90e4d06d92817f` (1397 expand_states keys).
After: `d35cfd9504f7d71faaebd42eb535077b8c2d0a68b064a009e3048abb653fec0f` (2024 expand_states keys).
Confirmed the diff is exactly the two effects above and nothing else: dumped `render_messages`'s
raw `m_lines` (this harness never passes `copy_feedback`, so no symbol is ever appended) at all
210 entries × 4 widths = 840 combinations, before and after via `git stash` — **0 differences** in
the visible text itself. The hash moves only because (1) `m_keys` changed `None`→tuple for these
rows (feeds `_hash_section_functions`'s `repr((m_lines, m_keys))`) and (2) the now-key`is not
None` zebra/hover eligibility changes the ANSI background wrapper `_apply_row_backgrounds` applies
(feeds `_hash_format_proxy_block`'s text hash). The expand_states growth (1397→2024) is
`_grow_expand_states`'s own loop discovering the new msg keys via `item_positions_out` — inert,
nothing reads `expand_states[('msg', ...)]` anywhere.

## Landmine hit while writing the test: body row 1 is reserved for the search bar

`format_proxy_block` called directly (the `dev/display/test_hover_map.py` style, avoiding
`os.get_terminal_size()`'s crash in this sandbox — no real TTY) produces UNSHIFTED row numbers
starting at 1. But `_handle_proxy_mouse`/`_handle_worker_proxy_mouse` special-case `row == 1` as
"focus the search bar" before ever consulting `line_map` — a synthetic click at a raw
`format_proxy_block` row can silently land on that branch instead of the real dispatch, and the
handler still returns truthy, so a naive assertion would false-pass. Fixed by shifting `line_map`/
`copy_rows` with `proxy_pane_shared._shift_line_map_and_copy_rows(..., 1)` before dispatching any
synthetic click — the same shift `_render_and_scroll_body` applies for real. Documented as a new
Gotcha in `dev/click_ui/DOCS.md` for the next probe that calls `format_proxy_block` directly and
then tries to click on what it found.

## Tests

`dev/click_ui/p5_proxy_message_copy_click_probe.py` (new, 252 LOC) — 29 assertions: key/copy-row
registration, serializer-matches-and-is-substring, full click dispatch through BOTH panes
(copy-column click, non-copy no-op, flash isolation, REQ copy unchanged), width guard. Also ran
unmodified as caller-safety: `dev/display/test_hover_map.py` (45/45, before and after),
`dev/click_ui/p2_copy_click_probe.py`/`p3_button_click_probe.py` (both crash identically
before/after on this sandbox's missing TTY — confirmed pre-existing via traceback diff, not
introduced by this milestone).
