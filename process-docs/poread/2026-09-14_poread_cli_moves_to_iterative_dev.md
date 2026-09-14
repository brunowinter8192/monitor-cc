# 2026-09-14 — the poread CLI moves out of monitor-cc into the iterative-dev plugin

Worker task on branch `poreadmove`, worktree `.claude/worktrees/poreadmove/`. Cross-repo milestone,
second commit lands in `Meta/iterative-dev` (branch `identity`, own worktree). This entry covers
only the monitor-cc half; the iterative-dev half has its own process-docs entry there.

## What moved and why

`bin/poread`, `src/poread_cli/` (whole package), `dev/poread_cli/` (whole test dir) — the CLI half
of poread — moved into the iterative-dev plugin, next to `worker-cli`/`gcommit`, the other
agent-facing CLIs. `src/proxy/inject_poread.py` and everything downstream of it (`strip_vocab.py`'s
`PR` rule, `message_passes_simple.py`'s `_POREAD_SPEC`) stayed — the proxy-side recognition/
replacement half has no reason to leave and every caller of it is proxy-internal. `duallog` was
never touched: it imports five monitor-cc proxy modules directly and cannot leave this repo, and
this milestone didn't need to touch it.

## The seam: four constants, one import, now two hand-maintained copies

Before this move, `src/poread_cli/__main__.py` and `src/proxy/inject_poread.py` both imported
`POREAD_MAX_BYTES`, `POREAD_HASH_LEN`, `POREAD_MARKER_PREFIX`, `POREAD_NOTICE` from
`src/constants.py` — one file, one source of truth, drift structurally impossible. Once the CLI
left this repo, that import is gone by construction (the iterative-dev plugin has no venv, no
dependency on this repo, stdlib-only). Two options existed: invent a shared package/config file
straddling both repos, or follow this codebase's own existing precedent for exactly this situation.
Chose the precedent: `src/proxy/strip_vocab.py`'s `RULES` table already hand-maintains its own copy
of every strip module's marker literals, by design, documented with a Gotcha in `src/proxy/DOCS.md`
saying so. `inject_poread.py` now does the same — it defines its own copy of the four constants
directly in its own INFRASTRUCTURE section, matched byte-for-byte against the iterative-dev CLI's
own copy of the same four values. New Gotcha added to `src/proxy/DOCS.md`, appended after the
existing `strip_vocab.py`/`RULES['BL']` Gotcha it mirrors, stating explicitly: a drift between the
two copies makes a future marker silently fail to expand (the agent sees the tiny marker-plus-
notice lines forever, no error anywhere), and that cross-repo drift is NOT machine-detectable —
there is no shared CI between monitor-cc and iterative-dev — change both by hand, together.

`src/constants.py` lost the four `POREAD_*` lines entirely (29 LOC now, was 36) — after the move
they have exactly one consumer left in this repo, so per this project's own Code Standards
("constants shared by 2+ modules go in the config module; module-specific constants live with the
module") they're no longer a shared-config concern here, they're `inject_poread.py`'s own.

## Tests — why a cross-repo check would itself be untestable, and what each side pins instead

The old `dev/proxy/poread_inject_tests.py` minted every fixture marker by invoking the real CLI as
a subprocess (`python -m src.poread_cli`) specifically so the test proved the two halves actually
agreed, not just that `inject_poread.py` could parse whatever it expected. That route no longer
exists once the CLI leaves this checkout. The tempting alternative — shell out to whatever `poread`
happens to be on `$PATH` — was rejected on this project's own testing rule: a test's result must
depend only on factors under this file's control and repeat identically forever; a `$PATH`-resolved
external binary depending on which repo/version happens to be installed on the machine running the
suite is an environment dependency, which makes it a verification, not a test, and it would need to
run every time this file runs. Not acceptable for a regression guard meant to run every time
`inject_poread.py` changes, in any environment, including CI with no iterative-dev checkout present.

Design landed on: `_mint_marker()` now builds the marker string from this test file's OWN pinned
literal copy of the marker contract (`_PINNED_MARKER_PREFIX`, `_PINNED_HASH_LEN`, `POREAD_NOTICE`
— hardcoded directly in the test file, NOT imported from `inject_poread.py`). This keeps the test's
real value: it still drives `inject_poread.py`'s actual parsing/expansion code against an
independently-authored fixture, so if `inject_poread.py`'s own hand-maintained copy of the contract
ever drifts (typo'd sentence, wrong ceiling, wrong hash length), the marker stops parsing and the
`mod recorded`/`carries the exact file content` assertions fail immediately — loud, not silent. The
iterative-dev side's own `dev/poread_cli/test_poread_cli.py` does the exact same thing mirrored:
its own pinned literal copy, independent of `src/poread_cli/__main__.py`'s constants. What this
CANNOT do, and was never going to be able to do without an environment dependency: catch a drift
where BOTH hand-maintained copies change to agree with each other but no longer match what a real
marker in the wild looks like, or catch a drift the moment it happens rather than the next time
either suite runs. That limitation is stated plainly in both Gotchas rather than glossed over.

## Numbers

`dev/proxy/poread_inject_tests.py`: 37/37 before this change (real-CLI-subprocess route) and 37/37
after (pinned-literal route) — same 12 items, same assertions, only the marker-minting mechanism
inside `_mint_marker()` changed. `dev/proxy/test_strip_fix.py` (264/264, shared strip/attribution
machinery — `strip_vocab.py` untouched, `message_passes_simple.py`'s `POREAD_MARKER_PREFIX`
re-export from `.inject_poread` unaffected since the name still resolves the same way) re-run as a
caller-side sanity check, unaffected as expected.

## Callers checked

Repo-wide grep for `poread_cli` (code + docs): only the DOCS.md files that reference it by name
(`src/DOCS.md`'s `constants.py` Called-by line, `src/hooks/DOCS.md`'s `block_po_read.py` Writes
line) and the moved files themselves — both DOCS.md lines updated to drop the now-stale path
reference. Repo-wide grep for the four `POREAD_*` constant names: `src/constants.py` (definition,
now removed), `src/proxy/inject_poread.py` (now its own copy), `src/proxy/message_passes_simple.py`
(imports `POREAD_MARKER_PREFIX` from `.inject_poread`, not from `constants` — untouched, still
resolves), and the two poread test files. `src/hooks/block_po_read.py` itself was NOT touched — its
stderr message says `poread <path>`, a plain string, no import or path reference to the CLI's
source location, so it needed no change; only its DOCS.md description of that message did.

## No further work planned by this worker here

The move is complete as scoped: CLI half relocated, proxy half unchanged apart from the forced
constant-copy adaptation, both DOCS.md files and both test suites updated and re-verified,
`duallog` untouched, `~/.local/bin` untouched (the user's own symlink to repoint).

## Recap close-out

Self-audit (`git diff integration --name-only` from the `poreadmove` worktree): `bin/poread`,
`dev/poread_cli/DOCS.md`, `dev/poread_cli/test_poread_cli.py`, `dev/proxy/DOCS.md`,
`dev/proxy/poread_inject_tests.py`, `process-docs/poread/2026-09-14_poread_cli_moves_to_iterative_dev.md`,
`src/DOCS.md`, `src/constants.py`, `src/hooks/DOCS.md`, `src/poread_cli/DOCS.md`,
`src/poread_cli/__init__.py`, `src/poread_cli/__main__.py` (last three deleted), `src/proxy/DOCS.md`,
`src/proxy/inject_poread.py` — matches the file list already named in the task's completion
checklist, nothing outside scope touched.

**One real LOC-mismatch caught by this recap's currency check, not caught at task time.**
`src/proxy/DOCS.md`'s `inject_poread.py` entry said `(79 LOC)`, carried over from an earlier
line-count before the module-level constants block was finalized; the file is actually 81 LOC
(`wc -l`). Fixed to `(81 LOC)`. Every other touched module's DOCS.md entry (`constants.py` 29,
`poread_inject_tests.py` 362, `block_po_read.py` 64 — unchanged, only its prose line was edited)
already matched `wc -l` exactly on this pass.

**Landmine for whoever next touches `inject_poread.py` or its test:** the LOC-mismatch above is a
reminder that a DOCS.md LOC figure written mid-task (before the file is fully settled) can go stale
by the time the task's own later edits land — re-run `wc -l` on the actual file at recap time
rather than trusting a number written earlier in the same session, even one written by the same
worker minutes before.

No further work planned by this worker here. Both this repo's half and the iterative-dev half
(`process-docs/poread/` there) are complete as scoped; see that repo's own recap entry for its
half's currency check.
