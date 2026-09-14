# 2026-09-14 — Milestone 7: per-block copy click (fourth granularity)

New task, same line of work as `process-docs/click_ui/2026-09-14_milestone5_message_copy.md`
(REQ → message → thinking block → this milestone: every other block type). Scope:
`src/proxy_display/` and the one dev test only.

## What was missing

Every block row that isn't a thinking block — text, tool_use, tool_result, anything else reaching
`render_messages._render_block_spans`'s non-thinking branch — was built with `keys.append(None)`,
no copy symbol, no way to click it at all. `[STRIPPED]` stayed out of scope, same as the two prior
milestones.

## Key shape

`('block', entry_idx, msg_idx, bidx)` — 4-tuple, same arity as `('think', entry_idx, msg_idx,
bidx)` but distinguished by `key[0]`. New `_block_row_key` in `render_messages.py`, next to
`_msg_row_key`, used in `_render_block_spans`'s non-thinking branch with the same
`_append_msg_copy_symbol` helper the thinking branch already used (reused, not duplicated, for a
third row kind now).

## The dispatch-shape decision (the "earlier milestone got this wrong once" landmine)

A block row never had a key before, exactly like a message row before milestone 5 — NOT like a
thinking row, which already toggled expand/collapse before it ever got a copy affordance. The
correct shape is therefore the message-row shape: `elif is_msg or is_block: return had_selection`
in both `_handle_proxy_mouse` and `_handle_worker_proxy_mouse`, ahead of the generic
`else: _handle_proxy_expand_click(...)`. Milestone 5's own entry documents hitting this exact bug
once (a `('msg', ...)` row falling into the expand-click path and mutating `expand_states`/the
undo stack for a row kind that never touched that state before) — reading that entry first meant
this milestone never had to rediscover it. Verified with the same shape of test milestone 5 used:
`changed is False`, `expand_states` byte-identical before/after, clipboard untouched, for a
non-copy click on a block row, in both panes.

## The one design decision Main pushed back on: one serializer, not two

My own first-pass plan (written up before "Go") mirrored the recipe in milestone 6's closing
paragraph literally — "new `_is_X_key`/`_serialize_proxy_X` pair next to the existing ones" — and
would have produced `_serialize_proxy_block` as a near-verbatim copy of `_serialize_proxy_think`'s
body. Main caught this before implementation: re-reading `_serialize_proxy_think`, NOTHING in its
body after the guard is thinking-specific — same `blk.get('full_text', blk.get('preview', ''))`
read every other block-copy site in this file already uses, same header format, same
`blocks[bidx]` lookup. The only thinking-specific line was the guard itself
(`if not _is_think_key(key): return ''`).

Decision made: ONE shared `_serialize_proxy_block(key, entries)`, guard widened to
`_is_think_key(key) or _is_block_key(key)`, and `_serialize_proxy_think` as a named function no
longer exists — `_prepare_copy_text` now calls `_serialize_proxy_block` for both key shapes. This
is NOT "changing thinking-block copy behavior" in the sense the task's negative scope forbids —
the OUTPUT for a `('think', ...)` key is byte-identical to what the old function produced (proven
directly: `dev/click_ui/p5_proxy_message_copy_click_probe.py`'s P5.7/P5.8/P5.9 checks, which call
what is now `_serialize_proxy_block(think_key, entries)`, still pass unchanged, same exact-text
assertion). Only the internal implementation — one function serving two guards instead of two
functions with identical bodies — changed, and the only two callers of the old name
(`proxy_pane_shared.py` itself and this dev test) are both files this milestone already touches.

What did NOT get merged: `_is_think_key` and `_is_block_key` stay as two separate predicates. They
still drive a real fork at the dispatch layer — a `('think', ...)` row's non-copy click falls
through to the pre-existing expand-toggle branch, a `('block', ...)` row's non-copy click returns
a no-op — so collapsing the predicates would have re-introduced exactly the wrong dispatch shape
for one of the two row kinds. Only the axis that never varied (serialization) was collapsed; the
axis that does vary (click behavior) was left alone.

## Nesting — verified at both levels directly, not by transitivity

`_serialize_proxy_block` reuses the identical header format (`f"--- msg[{msg_idx}] {role}
{blk.get('type', '?')} ---\n{ft}"`) every block-copy site in this file already uses, so the same
join/lstrip argument that made a thinking-block copy a substring of its message copy applies
unchanged. Main's instruction was explicit — verify, don't assume the REQ-level nesting via
transitivity through the message level. `dev/click_ui/p5_proxy_message_copy_click_probe.py`'s
P5.12 asserts BOTH `block_text in msg0_text` AND `block_text in req_text` directly for two
sibling blocks (a `text` block and a `tool_use` block in the same message), not just the first.

## Flash keying

`_copy_feedback_key` widened to `_is_msg_key(key) or _is_think_key(key) or _is_block_key(key)`.
Verified a block row's own key flashes, a sibling block row does not, the owning message row does
not, and the REQ header does not — in both directions (copying the block doesn't flash the
message/REQ, copying the message doesn't flash either block) — P5.13/P5.14.

## Zebra/hover — same confirmed-intended consequence as milestone 5, not re-litigated

A block row gaining zebra/hover eligibility the moment it gets a non-`None` key is the same
`format._apply_row_backgrounds` behavior (gated purely on `key is not None`) already confirmed
correct for message rows in milestone 5. Not re-argued here; same conclusion applies for the same
reason — a block row becoming copyable is exactly the "genuinely interactive" transition that
already justifies it for every other keyed row in this pane.

## render_byte_identity.py — hash changed, verified why, same shape as milestone 5's diff

Pinned to a frozen copy of a static (no live proxy attached) forwarded/stripped/injected/original
quartet under `/tmp/render_byte_identity_frozen/` (this worktree carries no `src/logs/dual_log/`
at all — gitignored, absent from a fresh checkout; copied from the main checkout's own quartet,
confirmed not actively growing via two `ls -la` timestamps 24s apart before copying). Before:
`ca89bc02fcfd3a4ae090e6c463af3271d3256a5d981d6a045e312906d1b050b1` (4 entries, 49 expand_states
keys). After: `59bc9bb29f3f737e970541fe462ee1a5137baf95fd52daeb9cf6c678388b01cb` (4 entries, 56
expand_states keys). Confirmed the diff is exactly the two effects milestone 5 already identified
for the message-row case, nothing else: dumped `render_messages`'s raw `m_lines` (no `copy_feedback`
passed in this harness, so no symbol ever appended) for all 4 entries × 4 widths, before and after
via `git stash` — 0 differences in visible text. Dumped the full `expand_states` key set the same
way — the +7 new keys are exactly `('block', ...)` tuples (`('block', 0, 0, 0)`, `('block', 0, 0,
1)`, `('block', 0, 1, 0)`, `('block', 1, 0, 0)`, `('block', 2, 2, 1)`, `('block', 2, 3, 0)`,
`('block', 2, 4, 0)`), nothing else. The hash moves for the same two reasons as milestone 5:
`m_keys` changing `None`→tuple feeds `_hash_section_functions`'s `repr((m_lines, m_keys))`, and
the now-non-`None` key's zebra/hover eligibility changes `_apply_row_backgrounds`'s ANSI wrapper,
feeding `_hash_format_proxy_block`'s text hash.

**Landmine for whoever runs this harness next:** `./venv/bin/python script.py > file` redirects
get rejected by this environment's Bash tool with a generic "add redirect" error even when the
command has no literal `>` in it — piping through `python3 ... | cat` or writing output via the
script's own `open(path, 'w')` (no shell redirect at all) both work fine. Not a bug in the script,
a quirk of the sandbox's command-pattern check.

## Test extension, not a new file

Extended `dev/click_ui/p5_proxy_message_copy_click_probe.py` (298→539 LOC) rather than creating a
new file — third milestone in this same file, matching its own established pattern. Reused the
existing `_make_entry()` fixture as-is (already carries a `text` and a `tool_use` block in
`msg[0]`, blockless `msg[1]`) rather than adding a new one — it already had everything this
milestone's tests needed. Ran P5.1–P5.10 unmodified first (54/54) before writing any new test
code, confirming the merge of `_serialize_proxy_think` into `_serialize_proxy_block` didn't shift
any pre-existing assertion (P5.7–P5.9 were updated to call the new name, same expected output,
still pass), then added P5.11–P5.15 (37 new checks: key + registration, serializer-match +
double-nesting proof + defensive-dispatch, full click dispatch for both panes including sibling-
and owning-message non-flash proofs and a REQ-copy-still-works-after check, width guard) for
91/91 total. Also ran `dev/display/test_hover_map.py` unmodified as caller-safety (45/45, this
milestone never touches `_render_stripped_block`'s line/key pairing).

## Recap close-out

Self-audit (`git diff integration --name-only`): `dev/click_ui/DOCS.md`,
`dev/click_ui/md/p5_proxy_message_copy_click_probe_20260914_172433.md`,
`dev/click_ui/p5_proxy_message_copy_click_probe.py`,
`process-docs/click_ui/2026-09-14_milestone7_block_copy.md`, `src/proxy_display/DOCS.md`,
`src/proxy_display/format.py`, `src/proxy_display/pane.py`,
`src/proxy_display/proxy_pane_shared.py`, `src/proxy_display/render_messages.py`,
`src/proxy_display/worker_proxy_pane.py`.

DOCS.md currency checked against `wc -l` on every touched `src/proxy_display/` file plus
`dev/click_ui/p5_proxy_message_copy_click_probe.py` this pass: `pane.py` 334, `worker_proxy_pane.py`
338, `proxy_pane_shared.py` 287, `format.py` 183, `render_messages.py` 304,
`p5_proxy_message_copy_click_probe.py` 539 — all six DOCS.md headings now match exactly. Only
`proxy_pane_shared.py`'s and `render_messages.py`'s `Writes:` prose needed factual updates (the
`_serialize_proxy_think`→`_serialize_proxy_block` rename and the new `('block', ...)` key
respectively); `pane.py`/`worker_proxy_pane.py`/`format.py` needed only the LOC bump, no prose
referenced key shapes by name. Left the pre-existing `Purpose:` word-count overage on all touched
`src/proxy_display/` entries alone, same reasoning milestone 5's recap already gave — none of this
milestone's edits went into `Purpose:` text, so there was nothing of mine to trim, and rewriting
unrelated pre-existing prose is exactly the out-of-scope cleanup the task rules warn against.

This closes the four-granularity line of work Main asked about at the end of milestone 6 (REQ →
message → thinking block → any block). If a fifth granularity is ever asked for inside this same
line (per-span within a block's dual-log overlay, say), the pattern is now: check FIRST whether
the new serializer would be a near-copy of an existing one before writing a new
`_is_X_key`/`_serialize_proxy_X` pair — the recipe in milestone 6's closing paragraph describes the
mechanical shape (new predicate, new dispatch branch, new `is_X_line`, a dispatch-order decision
per pane) but does NOT by itself justify a new serializer function when an existing one's body
already covers the case; that check is a decision each new granularity has to make for itself, not
something the recipe should be trusted to answer.

## 2026-09-14 — Recap pass

Main sent `recap`. Self-audit (`git diff integration --name-only`) matched exactly what the task
commit (`67192ca6`) already staged: `dev/click_ui/DOCS.md`,
`dev/click_ui/md/p5_proxy_message_copy_click_probe_20260914_172433.md`,
`dev/click_ui/p5_proxy_message_copy_click_probe.py`,
`process-docs/click_ui/2026-09-14_milestone7_block_copy.md`, `src/proxy_display/DOCS.md`,
`src/proxy_display/format.py`, `src/proxy_display/pane.py`,
`src/proxy_display/proxy_pane_shared.py`, `src/proxy_display/render_messages.py`,
`src/proxy_display/worker_proxy_pane.py`. Nothing new to fold in — the process-docs entry above
was already written during the task itself (not deferred to this recap), and the currency check
below found no drift since that commit.

DOCS.md currency re-checked against `wc -l` on every touched file (unchanged since the task
commit — no edits happened between commit and this recap): `pane.py` 334, `worker_proxy_pane.py`
338, `proxy_pane_shared.py` 287, `format.py` 183, `render_messages.py` 304 (all
`src/proxy_display/DOCS.md`), `p5_proxy_message_copy_click_probe.py` 539
(`dev/click_ui/DOCS.md`) — all six headings still match exactly. Also confirmed no stale
`_serialize_proxy_think` reference survived the rename anywhere in either DOCS.md (grepped both
files directly — only `_serialize_proxy_block` appears). No corrections needed; this recap commit
carries no code or DOCS.md changes, only this section.

Nothing else to hand off — the four-granularity line of work (REQ → message → thinking block →
any block) is complete as scoped, and the one open note for a future fifth granularity is already
in the section above ("check FIRST whether the new serializer would be a near-copy of an existing
one before writing a new pair").
