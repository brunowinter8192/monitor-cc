# 2026-09-14 — poread ceiling lowered from 500,000 to 50,000 bytes (monitor-cc half)

Worker task, worktree `.claude/worktrees/poreadcap/`, milestone 1 of a larger plan (the plan's
later milestones were explicitly out of scope here — no paging/partial-read mode, no touch to
`src/hooks/block_po_read.py`, no marker-format/notice/hash-length/refusal-structure change). Same
area as the prior work recorded in `process-docs/poread/` — this entry only lowers a value
already established there, it does not change the mechanism.

## Trigger

A 295 KB file was pulled into a live agent context in full via poread. The 500,000-byte ceiling was
far too high to serve as a real guard against that. Ceiling lowered to 50,000 bytes. Refusal
behavior itself (CLI checks size before ever opening the file; proxy refuses to inject above the
ceiling) is unchanged — only the number moved.

## What changed, and why each one

Both hand-maintained copies of `POREAD_MAX_BYTES` (this repo's `src/proxy/inject_poread.py:9`, and
iterative-dev's `src/poread_cli/__main__.py:6` — see the prior work in `process-docs/poread/` and the
Gotcha in `src/proxy/DOCS.md` for why there are two copies instead of one shared constant) both
became `50_000`. Confirmed byte-identical by diffing the four POREAD_* constant lines across both
files after the edit — not just eyeballed.

`dev/proxy/poread_inject_tests.py`'s module docstring said "the 500,000-byte ceiling" — prose only,
no assertion logic touched it (Item 6 crafts `bytes="999999999"`, already far past any real
ceiling regardless of its exact value) — updated to "50,000-byte ceiling" so the docstring doesn't
keep claiming a value nothing in the codebase enforces anymore.

`dev/proxy_instrumentation/post_restart_verification.py`'s `CLAIM3_ACTION` string told a human
verifier to run poread "against a file well under 500,000 bytes" — this is NOT one of the four
constants and Main did not name it upfront, but it is live, re-runnable dev code (already
committed, not a one-shot script, not a frozen report) whose instruction text would silently
mislead a future verifier into picking a file that passes the OLD ceiling but fails the new one.
Flagged this explicitly before touching it, since it was outside the initially-named file set;
confirmed in scope and fixed to "well under 50,000 bytes."

## What was checked and deliberately left alone

`src/pane_error_log.py`'s `PANE_ERROR_LOG_KEEP_BYTES = 500_000` is a coincidentally-identical value
for a completely unrelated log-rotation ceiling — not poread, not touched.

Every prior process-docs mention of "500,000" — findable under `process-docs/poread/` and
`process-docs/proxy_instrumentation/` — and the three frozen `dev/proxy_instrumentation/md/post_restart_verification_2026*.md` reports are
write-once historical snapshots correctly describing the ceiling as it was AT THE TIME. Per this
project's own process-docs rule (write-once, never touched after the author's session closes) and
dev/ rule (reports are outputs, not maintained), these stay as-is — they are accurate records of a
past state, not live claims.

## How the search was done

Full-file reads of every file Main named, then repo-wide grep for `500,000|500_000|500000` and
separately for `ceiling`, in both repos, to catch anything outside the named file list. This is
what surfaced the `post_restart_verification.py` reference — grep, not inference.

## Evidence

- monitor-cc `dev/proxy/poread_inject_tests.py`: 37/37 before, 37/37 after.
- iterative-dev `dev/poread_cli/test_poread_cli.py`: 17/17 before, 17/17 after (see that repo's own
  process-docs entry for its half).
- Four POREAD_* constant lines diffed byte-for-byte between `src/proxy/inject_poread.py` and
  iterative-dev's `src/poread_cli/__main__.py`: identical.
- LOC unchanged on every touched file (single-line literal/prose substitutions only): 81
  (`inject_poread.py`), 362 (`poread_inject_tests.py`), 350 (`post_restart_verification.py`) —
  confirmed via `wc -l` against `dev/proxy_instrumentation/DOCS.md`'s existing
  `post_restart_verification.py (350 LOC)` heading and `src/proxy/DOCS.md`/`dev/proxy/DOCS.md`'s
  existing headings for the other two; all already matched, nothing to fix.

## Landmine for whoever touches the poread ceiling next

If the ceiling changes again, re-run the SAME two-grep search (`500,000|500_000|500000` and
`ceiling`) across both repos before trusting any fixed file list — this milestone's exact structure
guarantees nothing about whether a NEW stale reference has grown somewhere else since. In
particular check `dev/proxy_instrumentation/post_restart_verification.py`'s `CLAIM3_ACTION` again;
it is prose, not a constant, so no test will ever catch it drifting on its own.

## No further work planned by this worker here

Milestone 1 only, as scoped. Later milestones in the larger plan (paging/partial-read mode,
`block_po_read.py` changes) were explicitly out of scope and not started.

## 2026-09-14 — Milestone 2: block_po_read.py becomes size-gated at the same ceiling

Same worker, same worktree, same area, continuing after the M1 ceiling change and its correction
pass (area cross-reference fix). M1 created a real gap: a persisted-output export above 50,000
bytes had no full route left — `block_po_read.py` still blocked every partial shell read on it
unconditionally, and poread itself refused it. This milestone closes that gap by making the block
size-dependent, using the exact same boundary: at-or-below stays blocked (poread is still a real
route, partial reads stay wrong), above it becomes allowed (poread would refuse too, so blocking
serves no purpose — there's nothing left to protect the agent from being unable to do).

### Why the hook's original "no size threshold" design doesn't block this change

The hook's founding entry, recorded in `process-docs/tool_use_safety/` and read as one of
the named background files for this milestone, argued against a size cutoff: an invented,
independently-tuned number needs recalibration and risks missing small-but-still-partial exports or
false-positive on legitimately small files crossing an arbitrary line. That argument holds for an
invented cutoff. It does not hold here, because the number isn't invented — it's
`POREAD_MAX_BYTES`, the exact point where poread's own capability ends. Below it nothing about the
hook's schema-only logic changed at all (still no calibration needed); above it, the file is a
provably different situation (no full route exists), not a probabilistically-guessed one. This
reasoning was written into the completion report before implementation, per the milestone's own
request to state it explicitly.

### The `if=` token-prefix bug — a real, unanticipated find, not invented for test coverage

Extracting the actual filesystem path from `_PO_PATH_RE`'s match required verifying what the regex
match text actually contains for `dd if=<path> of=<dest>` — checked directly with a throwaway
Python snippet before writing any hook code, not assumed: `_PO_PATH_RE.search("dd if=/x/.claude/
y.txt of=/tmp/o")` returns `'if=/x/.claude/y.txt'`, the `if=` prefix riding along because `\S*` is
greedy and the token has no internal whitespace to stop at. Without stripping it, `os.path.getsize`
would be called on the literal string `"if=/x/.claude/y.txt"`, which is never a real path, so the
undeterminable-default would silently misfire on every `dd`-based read of an over-ceiling file —
wrongly still blocking it, exactly the case this milestone exists to unblock, and the bug would
have been invisible without a test built around a REAL over-ceiling file exercised through `dd`
specifically (not `head`/`cat`, which don't have this prefix). Fixed with a narrow
`_TOKEN_PREFIX_RE = re.compile(r'^\w+=(.*)$')` strip applied AFTER the unchanged `_PO_PATH_RE`
match — `_PO_PATH_RE` itself was correctly left untouched per the milestone's negative scope. Pinned
directly: `dd if=<real 50,001-byte file> of=/tmp/x` → exit 0, the only one of the three new test
cases that would fail if this specific fix were reverted while the other two still passed (the
boundary cases don't exercise `dd` at all).

### The undeterminable-case decision — fail closed, and why that's not a new choice

Missing file, unstat-able file, and an unresolvable/garbled path token were named as three separate
scenarios to decide on. They collapse into one code path: `os.path.getsize` inside a bare
`try/except OSError: return None`, and `None` is treated identically to "at or below the ceiling" —
i.e., still blocked. Justified primarily by continuity, not by re-deriving safety from scratch: the
existing 16-case suite already tests this exact scenario (its fixture path,
`~/.claude/projects/-Users-x-proj/abc123-session/tool-results/def456.txt`, does not exist on disk,
and every "must block" case in that suite depends on that fixture staying unresolvable AND still
blocking) — so fail-closed-on-undeterminable was already the tested, shipped behavior before this
milestone touched anything. Changing the default would have been an undocumented, untested behavior
change smuggled into a milestone that wasn't asking for one. All 16 pre-existing cases passed
unmodified after the full rewrite, which is the actual proof this reasoning held, not just the
stated intent.

### The block-message wording — a correction after Main's own review

First draft said "...that poread can still export in full — read it via `poread <path>` instead of
partially." True for the at-or-below case, but the SAME message fires for the undeterminable case
too (missing/unstat-able file), where poread will also fail — so the message would have been making
a promise it sometimes couldn't keep. Caught by Main during review, not by me during
implementation — worth being explicit about that in case the lesson generalizes: when a block
message fires from more than one branch of a decision (here: "confirmed at-or-below" AND
"undeterminable, defaulted"), check the message's claims against EVERY firing branch, not just the
one being actively worked on. Fixed by dropping the capability claim entirely: final wording is
"BLOCKED: this path is a Claude Code persisted-output export (contains /.claude/, ends .txt) — read
it via `poread <path>` instead of partially." It names the route without promising the route's
outcome — true in both firing branches, since it asserts nothing beyond "try this instead of a
partial read."

### An unrelated stale DOCS.md line, found and fixed during Main's review, not by me

`src/hooks/DOCS.md`'s `block_po_read.py` `Called by` line asserted "currently unregistered in
`~/.claude/settings.json` as of this milestone" — Main checked the real machine-local settings file
during review and found it registers the hook, so the claim was false, and had been false
independent of anything this milestone touched (pre-existing staleness that happened to sit in the
exact entry being edited). Rewritten to state the structural fact (`hook_setup.py` handles
registration) without asserting a machine-local, this-repo-doesn't-track state that can go stale
again the next time someone runs `hook_setup.py` or edits `~/.claude/settings.json` by hand.
**Landmine for whoever next edits a hook's DOCS.md `Called by` line:** don't assert the CURRENT
registration state of any hook in prose — it lives outside this repo's tracked files and this repo
has no way to keep the claim current; state only what `hook_setup.py` does, not what today's
settings file happens to contain.

### Numbers

`dev/hook_smoke/test_block_po_read.py`: 16/16 before this milestone, 19/19 after — 3 new cases
(boundary-exact real file at 50,000B → block, one-byte-over real file at 50,001B → allow, `dd
if=<over-ceiling file>` → allow). All 16 pre-existing cases pass byte-for-byte unmodified, proving
no regression in the schema-match/reader-tool logic (neither touched, per negative scope).

### Recap close-out

Self-audit (`git diff integration --name-only`): `dev/hook_smoke/DOCS.md`,
`dev/hook_smoke/test_block_po_read.py`, `src/hooks/DOCS.md`, `src/hooks/block_po_read.py` — matches
the two commits made this milestone (the implementation commit and the one-line `Called by`
correction commit). Both touched DOCS.md headings re-checked against `wc -l` at recap time:
`src/hooks/DOCS.md`'s `block_po_read.py (89 LOC)` — actual 89, matches. `dev/hook_smoke/DOCS.md`'s
`test_block_po_read.py (123 LOC)` — actual 123, matches. Nothing stale found beyond the `Called by`
line already fixed above.

**Known, pre-existing, out-of-scope environment behavior hit again this milestone:** committing a
change to `src/hooks/` fires this repo's post-commit hook, which tries to run `hook_setup.py`; that
script refuses to run from a worktree by design. Both commits this milestone landed cleanly despite
the printed error — this is the exact same behavior already recorded in an earlier `poread`-area
entry, not something either milestone in this file caused or should fix.

No further work planned by this worker in this area. Both milestones in this line
(`process-docs/poread/`) are complete as scoped: the ceiling lowered and made consistent across both
repos (M1), and the one hook that needed to become size-aware now is, using the same number, with
the gap it closed and the drift risk it introduces both documented in `src/hooks/DOCS.md`.
