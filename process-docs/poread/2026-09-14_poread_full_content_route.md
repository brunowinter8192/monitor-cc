# 2026-09-14 — poread: the one route past Bash's inline output ceiling

Worker task on branch `identity`, worktree `.claude/worktrees/identity/`. New area — no prior
process-docs entry to build on. Background: Claude Code caps an inline Bash result at roughly
30,000 characters (`BASH_MAX_OUTPUT_LENGTH` only widens the read-back window, not the ceiling
itself); past it, CC hands the agent a file path plus a preview, unconditionally. Every route an
agent tries to recover the full content re-triggers the same ceiling. Observed twice in real
sessions the same day, on a file the agent had explicitly been told to read completely.

## The mechanism, both halves

**`src/poread_cli/`** — a tiny standalone CLI (`poread <path>`) that never prints more than one
line: `<poread-export path="..." bytes="..." sha256="..."/>` (marker prefix, ceiling, hash length
all in `src/constants.py`, imported by both halves — genuinely shared, so the Code Standards rule
"constants shared by 2+ modules go in the config module" applied directly here, unlike
`strip_vocab.py`'s deliberate independent-copy pattern used elsewhere in this codebase for a
different reason). Checks `os.path.getsize` **before** ever opening the file, so an oversize file
is never read into memory just to be rejected.

**`src/proxy/inject_poread.py`** — a new pass, same shape as `strip_bg_launch_ack.py`
(`_walk_replace_marker_blocks`, `full_replace: True` via a new `_POREAD_SPEC` in
`message_passes_simple.py`, appended to `rules.py`'s `_passes` list), that recognizes the marker
inside a `tool_result` and replaces it with the file's real, current content — re-validated (size +
truncated sha256, both from disk) on every single request, never trusted from a previous one.

## Design decisions and why, in the order they mattered

**Hash-based re-validation, not just size.** The task's hard requirement was determinism: the same
marker in history must always produce the same injected bytes, or the prompt cache rebuilds every
request. Size alone catches "vanished" and most "changed"; a same-size content rewrite would slip
through. Since injecting the file means reading the whole thing anyway, hashing it costs nothing
extra. Chose SHA-256 truncated to 16 hex chars (`POREAD_HASH_LEN`), matching this codebase's
existing truncated-hash convention (`rule_ops.py`).

**The pass placement in `_passes` has zero ordering dependency, and I said so explicitly before
implementing rather than discovering it after.** Traced every earlier pass: the whole SR family
structurally never descends into `tool_result` content (where the marker lives, per the existing
DOCS.md Gotcha); every other pass anchors on a disjoint literal prefix. Placed at the end of the
list — purely additive, no risk to reorder.

**Two seam confirmations Main asked for before I wrote any code, both held:**
1. The injected content lands at the end of history on first appearance, because no pass (mine or
   any other) ever reorders or backfills messages — every one is `for idx, msg in enumerate(...):
   result.append(...)`, one-for-one, confirmed by grep across both pass files — and a `tool_result`
   structurally cannot be message index 0 (needs a prior assistant `tool_use`), which also makes it
   immune to `fixation.py`'s msg[0]-freeze-and-replay mechanism. My pass completes entirely inside
   `apply_modification_rules`, strictly before `addon.py` calls `_finalize_cache_state`, so
   cache-breakpoint placement only ever sees the fully-expanded content.
2. The marker is genuinely all Claude Code's own process ever sees or stores locally — the proxy
   only rewrites the outbound wire bytes, never CC's own state — so the full content reaches the
   model exclusively through the forwarded payload on the request immediately after the tool ran,
   and every request after that, per the determinism guarantee above.

**`strip_vocab.RULES['PR']` carries TWO markers under one code, and 'PR' is FIRST in the dict.**
Learned this exact lesson two milestones ago for `strip_bg_launch_ack.py`'s wording 3 and applied
it proactively this time instead of finding it after the fact:
`strip_inject_delta._record_injected_msg_block` calls `attribute_chunk` on the **injected** text
too, not just the stripped side, so the injected wrapper needed its own recognizable literal
(`'--- poread: '`, the header prefix my replacement text starts with) alongside the marker literal
(`'<poread-export '`) or the injected-side `fn_map` entry would silently read "unknown". Placed
first in `RULES` (not appended) because `attribute_chunk` is first-match-substring over a dict, and
my injected content can be up to 500,000 arbitrary file bytes that could coincidentally contain
another rule's marker text deep inside — first-checked minimizes that (low-probability, not
zero-probability, misattribution risk).

## Two review findings, both real, both in `inject_poread.py` only

**Finding 1 — silent content loss.** First version anchored the predicate with
`text.lstrip().startswith(...)` and parsed with `re.match` (prefix only). A `tool_result` reading
`"<marker>\nsomething else"` (reachable the moment an agent chains `poread` with another command in
one Bash call, e.g. `poread /tmp/x && echo done`) would still match the predicate, and the
`full_replace` replacement would silently discard "something else" — never even recorded as
`removed`, invisible everywhere. Decision: the marker must be the ENTIRE block, not merely its
prefix. Fixed by switching `_parse_poread_marker` to `.strip()` + `re.fullmatch` — anything besides
the marker (plus its own trailing whitespace) in the same block means NO match at all, and the
whole block, trailing content included, is left completely untouched. Verified the fix doesn't
regress poread's own real output shape (marker + exactly one `print()`-added trailing `\n`) with a
dedicated regression guard, since `.strip()` removing exactly that one newline before the fullmatch
check is precisely what makes the normal case keep working.

**Finding 2 — a benign race that would have dropped an entire request's modifications, not just
one marker.** First version read and hashed the source file TWICE per marker per request — once in
the predicate (`_is_poread_marker_valid`, to decide match/no-match) and once again in the
replacement (`_build_poread_replacement`, to build the injected text) — discarding the validated
bytes after the first read. Between the two reads, the file could change (a real window, however
small — nothing prevents it). `_read_validated_poread_source` would then return `None` on the
second read, and `data.decode(...)` would raise `AttributeError` — uncaught inside the pass,
propagating out through `apply_modification_rules` into `ProxyAddon.request()`'s outer
`except Exception`, which catches and logs but by then `flow.request.content` was never
reassigned — meaning the ENTIRE request forwards with NO proxy modifications at all, not just a
skipped poread expansion. That's a much bigger blast radius than the feature earns, from a
perfectly benign, non-adversarial timing accident. Fixed by making the validated bytes flow from
predicate to replacement directly: `_inject_poread_content` builds a closure-scoped `cache: dict`
per call, `_is_poread_marker_valid` stores what it already read (`cache[text] = data`),
`_build_poread_replacement` pops it (`cache.pop(marker_text)`) instead of re-opening the file. The
file is now opened exactly once per validated marker — the race window is closed by construction,
not by handling it better. Verified the "exactly once" claim isn't just asserted but structurally
guaranteed: re-read `_walk_replace_marker_blocks`/`_walk_tool_result_inner` in `payload_helpers.py`
and confirmed every call site is `if predicate(text): ... replace_fn(text)`, always the same `text`
value, always predicate immediately before replace_fn, synchronously, with no way to skip — so
`cache.pop` can never legitimately miss.

**Landmine for whoever touches this pass next:** any FUTURE change to
`_is_poread_marker_valid`/`_build_poread_replacement` that reads the source file independently in
either function (instead of going through the cache) reopens Finding 2's exact race. The two
functions are coupled ON PURPOSE now — don't decouple them again without re-deriving why they were
coupled in the first place.

## Numbers and evidence

- CLI test (`dev/poread_cli/test_poread_cli.py`): 17/17, calling `main()` directly, no subprocess.
- Proxy-side test (`dev/proxy/poread_inject_tests.py`): 31/31 (23 from the initial milestone + 8
  added for the two review findings), mints every fixture marker through the REAL CLI as a real
  subprocess (`python -m src.poread_cli`), never reimplements it — this is what caught Finding 2's
  fix actually working: `test_source_is_read_only_once_per_marker` monkeypatches the module's own
  `open` and asserts exactly one call against the marker's resolved path.
- `dev/proxy_dual_log/proxy_176_bg_launch_ack_tests.py` (78/78) and `dev/proxy/test_strip_fix.py`
  (264/264): unchanged, confirming the shared machinery (`message_passes_simple.py`,
  `strip_vocab.py`, `strip_inject_delta.py`) wasn't disturbed.
- `dev/proxy/pipeline_byte_identity.py`, pinned via `PROXY_PIPELINE_BYTE_IDENTITY_LOG` against a
  frozen 60-payload real corpus prefix (none containing a poread marker): HASH
  `545d682e47281ae211747b77f8530c315e01c5dd69467a9423bc725e811fc4b9`, identical across all three
  states checked (before this whole milestone, after the initial implementation, after the review
  fixes) via `git stash`.
- `strip_vocab.attribute_chunk` confirmed resolving `'PR'` on both the stripped (marker) and
  injected (`'--- poread: '`-prefixed) sides of a real injected occurrence.

## Landmine hit while writing tests, unrelated to the two review findings

`os.path.realpath` on macOS resolves `/tmp`/`/var` through their `/private` symlink targets. A
naive test comparing a monkeypatched `open()`'s argument against the ORIGINAL (pre-realpath)
tempfile path will always show 0 calls, even though the real call happened correctly with the
resolved path — not a poread bug, a test-fixture bug I made and fixed by comparing against
`os.path.realpath(path)` instead. Worth remembering for any future test on this machine that opens
a file by a path poread (or anything else using `os.path.realpath`) resolved first.

## Recap close-out

Self-audit (`git diff integration --name-only`): `bin/poread`, `dev/poread_cli/DOCS.md`,
`dev/poread_cli/test_poread_cli.py`, `dev/proxy/DOCS.md`, `dev/proxy/poread_inject_tests.py`,
`src/DOCS.md`, `src/constants.py`, `src/hooks/DOCS.md`, `src/hooks/block_po_read.py`,
`src/poread_cli/DOCS.md`, `src/poread_cli/__init__.py`, `src/poread_cli/__main__.py`,
`src/proxy/DOCS.md`, `src/proxy/inject_poread.py`, `src/proxy/message_passes_simple.py`,
`src/proxy/rules.py`, `src/proxy/strip_inject_delta.py`, `src/proxy/strip_vocab.py`. Every touched
DOCS.md entry checked against `wc -l` this pass — all ten already matched exactly (kept current
inline during the task itself, both at initial implementation and again after the review-fix
commit), nothing to fix.

One observed, out-of-my-control side effect worth naming: committing a change to `src/hooks/`
fires this repo's post-commit hook, which tries to run `hook_setup.py` — that script refuses to run
from a worktree ("must be run from the main repo root"). The commit itself lands fine either way;
this is a pre-existing environment behavior, not something this task's scope covers or should try
to fix.

`~/.claude/settings.json` was never touched, as instructed. No further work planned by this worker
on this line — the milestone (CLI + proxy-side injection + the `block_po_read.py` pointer update)
is complete as scoped, and both review findings are fixed and tested.

## 2026-09-14 — the marker needs to explain itself, and a small message trim before it

Two small tasks, same area, same session. Recorded together since the second directly extends
the mechanism the first is about, and neither was big enough to warrant its own file.

### block_po_read.py message trim (no plan needed, direct)

Main found `_BLOCK_MSG`'s closing sentence ("poread brings the full content into context
regardless of size; if the file exceeds poread's own ceiling it says so on stderr and exits
non-zero") redundant with what the CLI already demonstrates when it actually fires — Main's own
call: "the ceiling explains itself when it fires, and the message is for the moment of the block,
not a manual." Removed the sentence, kept the BLOCKED line naming the path class and pointing at
`poread <path>`. `src/hooks/DOCS.md`'s Purpose/Writes lines never quoted the removed sentence, so
only the LOC needed touching (66→64). `dev/hook_smoke/test_block_po_read.py` only asserts exit
codes, never message text — unaffected, re-ran it anyway (16/16).

### The marker needed to explain itself — real gap, found by actually using it

Main's own framing: "the marker alone tells the agent nothing... today the only thing that
explains it is the rule file, and a rule file is not present at the moment the marker arrives."
Real, structural gap — an agent seeing `<poread-export path="..." bytes="..." sha256="..."/>` in
its own tool_result has no way to know what happens next unless it already knows the mechanism.

**The fixed sentence became part of the marker contract, not an extra line.** This was the whole
design constraint, stated directly by Main and confirmed correct: since `inject_poread.py`'s
predicate requires the block to be nothing but the marker (the whole-block rule from the review two
milestones ago), a second line would make every marker ineligible unless the proxy's own pattern
was widened to expect it. So `POREAD_NOTICE` (new shared constant in `src/constants.py`, same
"shared by 2+ modules" reasoning as `POREAD_MARKER_PREFIX`/`POREAD_MAX_BYTES`/`POREAD_HASH_LEN`) is
now baked into `_POREAD_MARKER_RE` itself — `r'\n' + re.escape(POREAD_NOTICE)` appended after the
marker's own pattern, `.fullmatch()`'d as one unit. A marker with no notice, a different notice, or
anything else in the block is exactly as ineligible as before — same single code path, no second
route.

**Wording:** "The file's full content will arrive automatically on the next turn — do not read
this file again until then." One sentence, states both facts asked for (arrives next turn; don't
re-read meanwhile).

**The free property, confirmed by actually testing both directions, not just stating it in
prose.** Because the notice is part of the SAME matched-and-replaced block as the marker,
`_build_poread_replacement` — completely unchanged — discards it along with the marker on success.
Pinned directly: `test_marker_with_notice_expands_to_content` (Item 12) asserts
`POREAD_NOTICE not in result` after a successful expansion. The other direction — the notice
survives when expansion doesn't fire — was ALREADY true by construction (an ineligible block is
left byte-for-byte untouched, notice included), but I added an explicit assertion to Item 4 (source
file changed mid-session) rather than leaving it implicit: `POREAD_NOTICE in r2`, exactly the case
Main named as "the case where it needs the explanation."

### A real regression caught by re-running the existing suite, not by reasoning about it

`dev/proxy/poread_inject_tests.py`'s `_mint_marker` helper asserted `proc.stdout.count('\n') == 1`
("poread stdout must be exactly one line") — this is now structurally false (two lines), and the
assertion caught it immediately as a hard crash the moment I ran the suite after the CLI change,
before I'd even touched the proxy regex. Two OTHER existing tests needed more than a one-line count
bump, and both would have silently tested the wrong thing if I'd only fixed `_mint_marker`:

- **Item 6** (`test_oversize_declared_marker_refused_regardless_of_actual_file`) crafts its own
  marker string by hand (doesn't go through `_mint_marker`) with `bytes="999999999"` to prove the
  ceiling check fires independent of the real file's size. Its crafted string had no notice under
  it — meaning after this change it would still show "refused, unchanged" but for the WRONG
  reason (missing notice, not the oversize check), silently testing nothing about the ceiling
  anymore while still showing green. Fixed by adding `\n{POREAD_NOTICE}` to the crafted marker so
  the test genuinely exercises the oversize path again.
- **Item 9** (`test_marker_alone_with_own_trailing_newline_still_expands`) asserted
  `marker.count('\n') == 0` as a precondition on what `_mint_marker` returns. The marker now
  legitimately contains ONE internal newline (between the marker line and the notice line), so the
  precondition needed to become `== 1`, not `== 0` — a different number, not just "no newlines
  anymore."

**Landmine for whoever touches this contract next:** any test that crafts its own poread marker
string by hand (not through `_mint_marker`/the real CLI) needs the notice appended manually, or it
silently tests the wrong failure mode once real markers require two lines. Grep for
`f'<poread-export path=` (the hand-crafted-marker shape) before trusting a test's stated purpose
matches what it actually exercises.

### Numbers

`dev/poread_cli/test_poread_cli.py`: before 16/17 (one real failure — `test_valid_file_prints_marker`
expected the old one-line shape), after 17/17 (that assertion updated to the two-line shape, all
five boundary cases otherwise unchanged). `dev/proxy/poread_inject_tests.py`: before — crashed at
`_mint_marker` before any check even ran; after 37/37 (25 original, unchanged in intent, three of
them touched for the reasons above, plus 2 new dedicated tests — Item 11 marker-without-notice is
ineligible, Item 12 marker-with-notice expands and the notice disappears — plus one new assertion
added to Item 4 for the "notice survives when ineligible" direction).

### Recap close-out

Self-audit (`git diff integration --name-only` at recap time): the 10 files from the notice-sentence
commit (`src/constants.py`, `src/poread_cli/__main__.py`, `src/proxy/inject_poread.py`,
`dev/poread_cli/test_poread_cli.py`, `dev/proxy/poread_inject_tests.py`, and the five corresponding
DOCS.md files: `src/DOCS.md`, `src/poread_cli/DOCS.md`, `src/proxy/DOCS.md`, `dev/poread_cli/DOCS.md`,
`dev/proxy/DOCS.md`) — the `block_po_read.py` trim commit had already been merged into `integration`
before this recap ran, so it doesn't show in this diff; recorded here anyway since it's the same
area and the same session. All five DOCS.md entries touched by the notice-sentence task checked
against `wc -l` this pass — all already matched exactly (71/80/36/138/355 LOC), kept current inline
during the task itself.

The poread mechanism (CLI mint → proxy recognize/expand → whole-block contract → now a
self-explanatory notice sentence, all confirmed against real data and real caller code at each
step) is complete as scoped across every milestone in this area this session. No further work
planned by this worker here.
