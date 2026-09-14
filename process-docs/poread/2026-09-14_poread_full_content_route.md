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
