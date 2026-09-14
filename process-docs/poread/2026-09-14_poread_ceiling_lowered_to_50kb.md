# 2026-09-14 — poread ceiling lowered from 500,000 to 50,000 bytes (monitor-cc half)

Worker task, worktree `.claude/worktrees/poreadcap/`, milestone 1 of a larger plan (the plan's
later milestones were explicitly out of scope here — no paging/partial-read mode, no touch to
`src/hooks/block_po_read.py`, no marker-format/notice/hash-length/refusal-structure change). Same
area as the two prior `poread` entries (`2026-09-14_poread_full_content_route.md`,
`2026-09-14_poread_cli_moves_to_iterative_dev.md`) — this entry only lowers a value already
established there, it does not change the mechanism.

## Trigger

A 295 KB file was pulled into a live agent context in full via poread. The 500,000-byte ceiling was
far too high to serve as a real guard against that. Ceiling lowered to 50,000 bytes. Refusal
behavior itself (CLI checks size before ever opening the file; proxy refuses to inject above the
ceiling) is unchanged — only the number moved.

## What changed, and why each one

Both hand-maintained copies of `POREAD_MAX_BYTES` (this repo's `src/proxy/inject_poread.py:9`, and
iterative-dev's `src/poread_cli/__main__.py:6` — see the two prior entries in this area and the
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

Every process-docs mention of "500,000" (`2026-09-14_poread_full_content_route.md:62`,
`2026-09-14_accept_encoding_identity_fix.md` in `process-docs/proxy_instrumentation/`) and the
three frozen `dev/proxy_instrumentation/md/post_restart_verification_2026*.md` reports are
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
