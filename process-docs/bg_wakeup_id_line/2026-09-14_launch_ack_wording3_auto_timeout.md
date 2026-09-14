# Recognizing the third CC background-launch-ack wording (auto-backgrounded on timeout), 2026-09-14

Worker task on branch `identity`, worktree `.claude/worktrees/identity/`. Same area as the M1/M2
wording inventory and wording-2 recognition entries (2026-07-29, this folder) — this milestone adds
a THIRD wording: CC auto-backgrounding a Bash call that exceeded its own timeout, distinct from both
a deliberate `run_in_background` launch (wording 1) and a user manually backgrounding an
already-running call (wording 2). Root cause and constraints were handed down already measured by
Main (verbatim recorded text, occurrence counts, the standing "route back to full content is
preserved" ruling from `process-docs/cc_injection_inventory/2026-07-28_strip_candidate_rulings.md`)
— not re-derived here.

## The third wording, verbatim (src/logs/dual_log/api_requests_opus_monitor_cc_1789383190_original.jsonl)

```
Command did not complete within its 120s timeout and was moved to the background (ID: b1mahby4a). Output is being written to: /private/tmp/claude-501/-Users-brunowinter2000-Documents-ai-monitor-cc/d7b0d213-0c28-4e53-baf8-c11fa7838f0b/tasks/b1mahby4a.output. You will be notified when it completes. To check interim output, use Read on that file path.
Session cwd remains /Users/brunowinter2000/Documents/ai/monitor-cc; directory changes made by the backgrounded command do not apply to subsequent commands.
```

Two shape differences from wording 1/2, both confirmed by reading the actual recorded corpus text
(not assumed from the task description alone): the id sits in `(ID: <id>)`, not `with ID: <id>.`
— `_ACK_ID_RE` (`r'with ID:\s*([^.]*)\.'`) genuinely does not match this shape (verified: `None`).
And this wording carries a trailing `Session cwd remains ...` sentence in the SAME text block that
wording 1/2 never have (confirmed absent from both real wording-1/2 corpus samples pulled the same
way) — the strip discards it along with the rest of the matched ack, same as it already discards any
trailing content for wording 2 (see `W24` in `dev/proxy/test_strip_fix.py`, same discard behavior,
not a new one).

## Design choice — additive detection, NOT a widened shared predicate

`_is_bg_launch_ack` (the two deliberate/manual-launch wordings) is untouched. A new,
separate `_is_bg_auto_timeout_ack(text)` checks the third prefix
(`'Command did not complete within its'`) on its own, and `_strip_bg_launch_ack`'s own predicate
becomes `_is_bg_launch_ack_any = _is_bg_launch_ack(text) or _is_bg_auto_timeout_ack(text)`.

This mirrors the wording-2 entry's own "two narrow markers OR'd, not one broadened marker" design
choice for the FP-nuke reason recorded there. But there is a SECOND, more important reason specific
to this milestone: `src/proxy/DOCS.md` (read for caller-safety, not in Main's file list) names
`src/proxy/bg_escape.py` as importing `_is_bg_launch_ack` AND `_ACK_ID_RE` directly, to decide
whether to fire a REAL `tmux send-keys ... Escape` into a worker's live pane. The DOCS.md Gotcha
calls that dedup "load-bearing, not an optimization" — a second Escape into an idle/menu-open CC TUI
opens the quit menu. Widening `_is_bg_launch_ack` itself to also match the third wording would have
made `bg_escape.py` ALSO fire on timeout auto-backgrounding, a real production side effect the task
never asked for and I never confirmed was even correct behavior (auto-backgrounding might not put
the TUI into the same state a deliberate launch does — untested, unknown, and not this milestone's
business to guess at). Keeping the two predicates separate and additive means `bg_escape.py`'s
production behavior is provably unaffected: I traced `_trigger_bg_escape`'s loop — it now also
*sees* wording-3 chunks in `stripped_msg_removed` (since the strip fires on them), but
`_is_bg_launch_ack(chunk)` still returns `False` for them, so it `continue`s before any tmux call or
log write. Verified, not just reasoned: `dev/bg_wakeup_id_line/p2_bg_escape_probe.py` (this area's
OWN dedicated bg_escape regression suite, 29 checks) passes identically before and after — same
29/29, byte-identical stdout except the report file's own timestamp — via `git stash`/`git stash
pop` on the same process. Whoever adds a FOURTH wording should follow the same pattern: extend
`_strip_bg_launch_ack`'s own combined predicate, never `_is_bg_launch_ack` directly, unless
bg_escape firing for that wording too has been separately decided and verified.

Same reasoning applied to `_ACK_ID_RE`: left completely untouched. A new `_ACK_ID_PAREN_RE =
re.compile(r'\(ID:\s*([^.)]*)\)')` is tried only as a fallback inside
`_build_launch_ack_replacement` (`_ACK_ID_RE.search(...) or _ACK_ID_PAREN_RE.search(...)`) — and
since `bg_escape.py`'s `_extract_task_id` is only ever reached AFTER `_is_bg_launch_ack` gates the
chunk (confirmed by reading `_trigger_bg_escape`'s loop), it can never even reach a wording-3 chunk,
making the new regex zero-risk to that caller by construction, not just by omission.

## A second silent-gap trap found, not in Main's read list either: `strip_vocab.py`

`strip_inject_delta.py`'s `_MSG_CODE_TO_FN['BL'] = '_apply_bg_launch_ack_strip'` (maps by rule CODE,
needed no change) feeds off `strip_vocab.attribute_chunk`, which matches purely by PLAIN SUBSTRING
against the ORIGINAL removed ack text, against `RULES['BL']`'s own literal marker list — and this
file has ZERO imports from `strip_bg_launch_ack.py` by design (confirmed: only `from collections
import Counter` in its INFRASTRUCTURE section), the same "separately-maintained copy" pattern the
DOCS.md Gotcha already documents for `strip_inject_delta.py`'s dead `_FIELD_STRIP_FN` maps. Reusing
the shared `mod_name` (`stripped_bg_launch_ack`) for wording 3 without adding a third literal here
would have made `attribute_chunk` silently return `None` for every real wording-3 occurrence, losing
`fn_map` attribution in `stripped_delta`/`injected_delta` entries for exactly this wording, with
nothing anywhere raising or logging the gap. Added `'moved to the background (ID'` to `RULES['BL']`.
This is the SAME rule I already extend elsewhere (mod_name stays `stripped_bg_launch_ack`) — not a
new class, confirmed with Main before implementing.

## The replacement message needed its own text, not a reused constant

Constraint from Main: the replacement must still say the command was moved to background BECAUSE it
exceeded its timeout, so it doesn't read as an indistinguishable deliberate launch. `_BG_LAUNCH_ACK_MSG`
("Command is running in the background. Do NOT check...") says nothing about why, so wording 3 gets
its own `_BG_AUTO_TIMEOUT_MSG`/`_BG_AUTO_TIMEOUT_MSG_MAIN` pair (same is_main sharpening pattern as
the other two), selected inside `_build_launch_ack_replacement` via
`_is_bg_auto_timeout_ack(ack_text)`. Exact replacement for the recorded sample (506 → 320 chars, id
and path both preserved per the standing cc_injection_inventory "route back to full content" ruling):

```
Command exceeded its timeout and was moved to the background. Do NOT check, poll, or read its output — just wait until it finishes (you will get a completion notice).
Output: /private/tmp/claude-501/-Users-brunowinter2000-Documents-ai-monitor-cc/d7b0d213-0c28-4e53-baf8-c11fa7838f0b/tasks/b1mahby4a.output
ID: b1mahby4a
```

## Tests — extended two existing files, not a new one

`dev/proxy_dual_log/proxy_176_bg_launch_ack_tests.py` is this project's dedicated, comprehensive
suite for `_apply_bg_launch_ack_strip` — wording 2 was added there in full when it landed (see this
folder's 2026-07-29 entry). Added the matching `test_wording3_*` set (432→587 LOC, 57→78 assertions):
real-fixture replacement, an FP mid-content guard (marker `'moved to the background (ID'` quoted in
a synthetic RAG-search-style paragraph, must survive untouched), `attribute_chunk` → `'BL'`, message
differs from wording 1/2 and names "timeout", `is_main` sharpening, and an explicit ops-path proof
(`ops.get(0, {}).get(0, [])` non-empty + `_process_messages_section`'s real `fn_map` output) — this
last one directly answers the task's "make sure this strip does not fall into the op-less-strip
trap" instruction with a real assertion, not just the "it's inherited from `full_replace: True`"
reasoning (which IS correct and IS why the assertion passes on the first try, but reasoning alone
wasn't what was asked for).

`dev/proxy/test_strip_fix.py` (1786→1820 LOC) has its own `W15`-`W24` launch-ack section with two
real-corpus-pinned bodies (`W18` for wording 1, `W23` for wording 2). Added `W34` (next free number
in that file — checked the max via grep before picking it) pinning the exact real sample verbatim,
matching that same precedent.

## Numbers — replay over the two named sessions, run with the real module post-implementation

Both log files are LIVE and growing (mtime ~7 minutes before I first read them, and grew further
between my planning pass and implementation — 100MB / 23MB files). Main's cited 44/63 were counts
from a few minutes before mine — confirmed by Main as growth, not a discrepancy in method. Measured
with the actual `_is_bg_auto_timeout_ack`/`_build_launch_ack_replacement` (not a reimplementation),
right after landing the code:

- `api_requests_opus_monitor_cc_1789383190_original.jsonl`: 53 occurrences caught (1 distinct
  underlying event, resent across 53 request payloads as the conversation's full history grows —
  this is why "occurrences" and "distinct events" diverge so much; CC resends full history every
  request, and the proxy genuinely re-strips it every single time, matching real production
  behavior), 9,858 chars removed.
- `api_requests_opus_trading_1789383010_original.jsonl`: 159 occurrences caught (5 distinct
  underlying events), 29,097 chars removed.
- Both files' `_stripped` logs currently show 0 occurrences of the substring (checked before
  implementing) — confirms Main's "nothing catches it today" claim directly, not just by inference
  from the code.

**Landmine for whoever re-runs this measurement:** these are live session logs (this worktree's own
session, going by the file growth timing) — re-running the replay will show DIFFERENT, larger
numbers purely from continued growth, not from any code change. Don't treat a higher count on a
later run as evidence of a bug; check the file's `mtime` against your run time first, same landmine
already documented for `dev/proxy/pipeline_byte_identity.py` and `dev/proxy/addon_hook_byte_identity.py`
in the `proxy_instrumentation` area's 2026-09-14 entry.

## Caller-safety checks run, byte-for-byte, not just reasoned

- `dev/proxy_dual_log/proxy_176_bg_launch_ack_tests.py`: 57/57 before code change was extended with
  new tests (proves non-regression on the code change alone), 78/78 after adding the wording-3 tests.
- `dev/proxy/test_strip_fix.py`: 262/262 before, 264/264 after.
- `dev/proxy/pipeline_byte_identity.py` (full `apply_modification_rules` pipeline hash, pinned via
  `PROXY_PIPELINE_BYTE_IDENTITY_LOG` against a frozen copy since its default source is this same
  live-growing worktree log): HASH identical before/after via `git stash`/`git stash pop` —
  `545d682e47281ae211747b77f8530c315e01c5dd69467a9423bc725e811fc4b9`.
- `dev/bg_wakeup_id_line/p2_bg_escape_probe.py` (this area's own bg_escape regression suite):
  29/29 identical before/after — the direct proof for the bg_escape-isolation design choice above.

## DOCS.md currency

`src/proxy/DOCS.md`'s `strip_bg_launch_ack.py` entry was ALREADY over the 25-word Purpose cap before
this task touched it (27 words, pre-existing, not introduced by me) — fixed it to 24 words in the
same edit since I was touching that exact line anyway for LOC/content accuracy (54→79 LOC, "two
known wordings"→"three"). Two new Gotchas added to `src/proxy/DOCS.md`: the bg_escape-isolation
design choice, and the `strip_vocab.py` RULES['BL'] lockstep requirement — both are exactly the kind
of thing a future fourth-wording author needs and would otherwise re-derive from scratch by reading
`bg_escape.py` and `strip_vocab.py` cold, the way I had to.

## Recap close-out

Self-audit (`git diff integration --name-only`): `dev/proxy/DOCS.md`, `dev/proxy/test_strip_fix.py`,
`dev/proxy_dual_log/DOCS.md`, `dev/proxy_dual_log/proxy_176_bg_launch_ack_tests.py`,
`src/proxy/DOCS.md`, `src/proxy/message_passes_simple.py`, `src/proxy/strip_bg_launch_ack.py`,
`src/proxy/strip_vocab.py`. All touched DOCS.md entries checked against `wc -l` this pass:
`strip_bg_launch_ack.py` 79 (matches), `proxy_176_bg_launch_ack_tests.py` 587 (matches),
`test_strip_fix.py` 1820 (matches). `message_passes_simple.py` (157) and `strip_vocab.py` (222) LOC
unchanged by this task (only existing lines got longer, no new lines) — their DOCS.md entries were
already correct and needed no edit. No further work planned by this worker on this area — a fourth
wording, if one is ever observed, should read this entry and the 2026-07-29 wording-2 entry first,
and follow the same additive (never-widen-`_is_bg_launch_ack`) pattern unless bg_escape firing for
it has been separately decided.
