# 2026-09-15 — block_non_canonical_edit: the canonical line-edit form and its hook

## Task and prior thread

This closes the loop opened by `process-docs/cache/2026-09-13_tool_cost_measurement.md` (Edit
tool removed, cost gap between Edit and `sed -i` measured at 157 tokens/call, mostly structural —
Edit resends `old_string` verbatim) and `process-docs/cache/2026-09-14_main_session_edit_addressing.md`
(a literal-anchor Bash heredoc still resends the old text, so the saving was smaller than it
looked; the open question left for a successor was "collect data across sessions before choosing
an edit form"). The classification (`BASH_FILE_MODIFICATION_FORMS` in `src/constants.py`) and the
extraction (`dev/cache/extract_bash_file_mods.py`, 210 real matched Bash calls persisted to
`dev/cache/jsonl/bash_file_mods_*.jsonl`) built earlier this same session are the data that
decision needed. This entry is the hook that acts on it.

## The canonical form went through two redesigns in review, both load-bearing

**First form (rejected):** fingerprint was `hashlib.sha256(...).hexdigest()[:8]` of the target
line range. Rejected because the agent cannot know a sha256 hash without running a separate
command to compute it first — reintroducing exactly the extra-round-trip cost this whole change
exists to remove. The lesson: a "cheap addressing" mechanism is only actually cheap if it's
derivable from information the agent already has in hand at the moment it writes the edit, not
from a value it could look up.

**Second form (accepted):** fingerprint is a literal prefix of the target line's own text, taken
after `.lstrip()`. The agent has this the moment it has read the file — no computation, just a
copy of text already on screen. Verified: indented lines, blank lines (empty-string fingerprint),
short lines (slice naturally truncates to whatever's there), and a wrong-line/wrong-text mismatch
all behave correctly, with the file left untouched on abort.

**One more round:** the replacement text originally sat in an ordinary `"..."` string, forcing
`\n` escapes and quote-escaping for real code — exactly the escaping burden that motivated this
whole thread (the corpus's literal-anchor calls were full of triple-backslashed quotes). Switched
to a triple-quoted `"""..."""` string so real newlines and unescaped single/double quotes go in
verbatim. **The one case this does not cover, stated explicitly per the review's own question:**
replacement text containing the literal three-character sequence `"""` breaks the string (verified
empirically — `"""before """triple""" after"""` is a `SyntaxError`, and content ending in a bare
`"` immediately before the closing `"""` is invalid too, e.g. `"""hello""""` also fails to parse).
Most likely to bite when the edit itself touches another Python triple-quoted string or docstring.
Not solved here — flagged as the known boundary, per the review's explicit instruction to identify
it rather than engineer around it.

## Final canonical form

```
python3 - <<'LINEEDIT'
path = "src/example.py"
edits = [
    (12, 12, "NEW_LINE", """    NEW_LINE = True"""),
    (30, 32, "def replaced", """def replaced():
    pass"""),
]
with open(path, encoding="utf-8") as f:
    lines = f.read().split("\n")
for start, end, fp, new in sorted(edits, reverse=True):
    got = lines[start - 1].lstrip()[:len(fp)]
    if got != fp:
        raise SystemExit(f"fingerprint mismatch at line {start}: expected {fp!r}, got {got!r}")
    lines[start - 1:end] = new.split("\n")
with open(path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
LINEEDIT
```

`sorted(edits, reverse=True)` applies bottom-of-file edits first, so an edit still pending never
has its target line shifted by one already applied — every edit addresses the file's ORIGINAL line
numbering, verified with a two-edit call spanning an indented multi-line range plus an isolated
blank line, landing correctly in one pass. Both `open()` calls carry `encoding="utf-8"` explicitly
per review instruction — a form meant to be issued thousands of times should not behave
differently depending on the locale of whatever machine runs it.

## Recognition: two passes, not one

`_strip_non_shell_active` (the shared utility every other hook in `src/hooks/` already uses)
blanks heredoc bodies and quoted strings before matching, which is exactly right for avoiding
false matches on prose (confirmed concretely from the classification milestone's own calibration:
a `duallog search "sed -i"` call and this project's own prompt text quoting `sed -i` as a bullet
both produce spurious matches against the raw text). But it is exactly wrong for the dominant real
pattern here — 70 of 210 corpus matches are `open(path, 'w')` calls living inside a `python3 -c`/
heredoc body, which is executable code, not inert prose, and blanking it would make the hook blind
to most real violations. So `block_non_canonical_edit.py` extracts every `python3 -c "..."` and
`python3 - <<'DELIM' ... DELIM` span from the RAW command first, inspects each body as real code
(canonical-form structural check, or the four python-mode classification patterns), blanks those
spans, THEN runs `_strip_non_shell_active` on what's left for the shell-level forms (`sed -i`,
`cat >`, `tee`, ...). Full writeup of why in `src/hooks/DOCS.md`'s Gotchas for this hook.

Two real corpus quirks the interpreter-detection regex had to grow past during build (both found
by testing against the actual 210 records, not invented): `./venv/bin/python -c` (interpreter
invoked by a venv path, not the literal string `python3`) and `python3 << 'PYEOF'` (no `-` before
the heredoc redirect — valid shell, stdin is implicit). Both are now covered
(`python3?\s*(?:-\s*)?<<\s*'(\w+)'` for the heredoc opener, no `python3` literal-anchoring at all
for the interpreter itself).

## A real bug the corpus catch turned up: target token bled across an unrelated `2>/dev/null`

Early implementation resolved a shell-level redirect's target by re-searching the WHOLE stripped
command text with a separate, looser regex than the one that did the actual classification match.
For `find ... -print0 2>/dev/null | xargs ... > /tmp/concepts_hits.txt` (a real corpus command,
`api_requests_worker_1dda1c81_concepts-rename_1789397270`), the classification pattern correctly
matched the real target (`/tmp/concepts_hits.txt`, excluding the `2>/dev/null` via its own
negative lookahead), but the separate target-resolution regex found `/dev/null` instead — the
FIRST `>`-shaped token in the string, from a completely different, unrelated redirect earlier in
the same chained command. `/dev/null` trivially "exists" as a device file, so the verdict (block)
happened to still be directionally defensible, but the STATED reason named the wrong file
entirely. Fixed by anchoring target extraction to the classification match's own `m.end()`
position rather than an independent re-search — the target token immediately follows the specific
occurrence that was actually classified, never an unrelated one elsewhere in the command. Found
purely by hand-reading the corpus verification report's BLOCK list, not by any test I had written
in advance — this is the concrete value of testing against real commands over invented fixtures.

## Corpus verification: 210/210 got a verdict, 125 allow / 85 block, hand-checked in both directions

`dev/hook_smoke/verify_block_non_canonical_edit_corpus.py` runs `_decide()` directly (no
subprocess) against every record in `dev/cache/jsonl/bash_file_mods_20260915T142910Z.jsonl` and
writes the full BLOCK list, the full ERROR list (empty), and a 40-record ALLOW sample to
`dev/hook_smoke/md/block_non_canonical_edit_corpus_report.md`. Separately, the 18-case synthetic
smoke test (`dev/hook_smoke/test_block_non_canonical_edit.py`) passes 18/18, covering every
always-block/always-allow/needs-stat branch plus the canonical form itself applied for real
against a fixture file and both known false-positive-prose shapes.

**The corpus-replay verdict distribution is NOT a measurement of real-time hook accuracy, and
must not be read as one — this is the single most important finding of this session, found only
by hand-checking rather than trusting the count.** `os.path.exists()` reflects THIS machine's
filesystem TODAY, not the state at the moment each historical command actually ran. Three distinct
confounds were found and hand-confirmed, in both directions:

1. **Inflates BLOCK.** A command whose own job was to CREATE a file (a `worker-cli spawn` prompt
   at a fixed `/tmp/spawn-worker-<name>.md` path, a freshly-dated `process-docs/.../2026-09-14_*.md`
   entry, an intermediate `> /tmp/some_scratch.txt` pipeline step) still shows the target as
   existing NOW, simply because that exact command already ran successfully and the file is still
   sitting there (or `/tmp` wasn't cleared). Of the 85 BLOCK verdicts, roughly 44 have an obvious
   `/tmp/spawn-*`, `/tmp/run_*.log`, or similar scratch-output shape; a closer read puts the true
   count of this category noticeably higher still (many `/tmp/*.txt` intermediate files from one
   `concepts-rename` worker session's grep/sort/comm pipeline share the same shape without the
   `run_`/`spawn-` substring a first pass filters on).
2. **Inflates ALLOW.** A relative-path target with no leading `cd` in the command resolves (for
   this OFFLINE verification harness only — the real hook always gets a real `cwd` from Claude
   Code's own stdin payload) against THIS worktree's `os.getcwd()`, not the historical session's
   real working directory. Confirmed concretely: `toolu_01DmbPtmA6jHZAL6LEXH2LLe`, a genuine
   read-modify-write (`s = open(p).read()` ... `open(p, "w").write(s.replace(old, new))`) against
   `dokumente/goethe/prozess/2026-09-14.md` in the wise2627 project, reports ALLOW here purely
   because the relative path doesn't resolve to anything inside this monitor-cc worktree.
3. **Inflates ALLOW, the opposite direction of #2.** A target that lived inside a WORKER WORKTREE
   already deleted after merge (the normal worktree lifecycle) now resolves to a path that
   genuinely doesn't exist anywhere on disk, even though the file certainly did at the time the
   original command ran and really was an existing-file edit.

None of these three are a defect in `block_non_canonical_edit.py`'s own logic — the 18/18 clean
synthetic smoke test, where file state is fully controlled, is the trustworthy accuracy signal for
the hook's actual decision code. They are a property of testing a stat-based, real-time hook by
replaying old commands against today's filesystem, and are documented in both
`src/hooks/DOCS.md` and `dev/hook_smoke/DOCS.md`'s Gotchas so a future re-run of this
verification script is read correctly rather than mistaken for a precision measurement.

**What weighted trust remains after the confounds are subtracted:** every genuine `sed -i`/
`perl -pi`/`gawk -i inplace` BLOCK hand-checked resolved to a real, clearly pre-existing target
(`~/.claude/shared-rules/proxy_rules.json`, `~/.config/ghostty/config`, `concepts/yardstick/
DOCS.md`'s LOC-count line, `dev/phase_a_yardstick/yardstick_config.py`'s path string) — these are
correct blocks under the accepted design regardless of the replay-timing issue, since these are
config/source files that plainly existed before the editing session touched them. The two
prose-only false-positive traps from the classification milestone's own calibration (`duallog
search "sed -i"`, and this exact prompt's own text quoting `sed -i` as a bullet inside a `cat >`
heredoc body) both correctly ALLOW against the real corpus, not just the synthetic test — the
two-pass recognition design holds up on real data, not only invented cases.

## A design question the corpus surfaced but did not change

Several BLOCK verdicts are `cat > <existing-rule-file>.md <<'EOF'` full-content rewrites of
`~/.claude/shared-rules/` files (a German-translation project earlier this session) — genuinely
pre-existing files, genuinely fully replaced, with zero dependency on old content (no `old`/`new`
substring logic, just fresh prose). Whether a FULL rewrite of an existing file (as opposed to a
partial edit) should even be in this hook's scope was considered during design and explicitly
NOT special-cased — the accepted design blocks any non-append modification of an existing file
target, full stop, because the canonical form can already express a full rewrite as one edit
spanning the whole file (start=1, end=last line), so there is no operation this hook now blocks
that the canonical form cannot also perform. This was a deliberate design acceptance, not an
oversight rediscovered here — noted for whoever next touches this hook so the question isn't
re-litigated from scratch.

## Known landmine, explicitly NOT guarded against

**Overlapping edit ranges in one `edits` list are not detected.** If a wider range is applied
after (i.e., processed earlier in the bottom-up pass than) a narrower range nested inside it, the
wider edit silently discards whatever the narrower edit would have done, and the fingerprint check
for the narrower edit still passes — because `sorted(edits, reverse=True)` processes the numerically
LARGER `start` first, a wider range starting further UP the file (smaller `start`) that also
happens to overlap forward is processed AFTER a nested one only if the nested range's `start` is
itself larger; the general case (any two overlapping ranges in one call, regardless of who's
inside whom) is not validated at all — no error, no exception, just a result that silently drops
one of the two intended changes. This has not been observed in the wild (no such call is in the
210-record corpus) and is not guarded against per explicit instruction: nobody has hit it, and
guarding against an invented case is not paid for here. If a future session finds this landmine
the fix belongs in the canonical form's own loop (an overlap check before applying), not in the
hook, which only recognizes the form structurally and never inspects the actual edit values.

## Registration status

Added to `_HOOK_SCRIPTS` in `src/hooks/hook_setup.py` (`("block_non_canonical_edit.py", "Bash")`).
**NOT activated** — `hook_setup.py` refuses to run from a worktree by design (`_guard_not_worktree`)
and this entire milestone was built in a worktree. Activation is a separate, deliberate step run
from the main repo root after merge, same as every other hook addition in this directory's own
history (`process-docs/tool_use_safety/2026-07-22_block_po_read_hook.md` is the direct precedent
for this exact deferral).

## Recap — 2026-09-15, later same session: python path resolution had the same anchoring bug the shell side already fixed, plus two smaller review items

Main review caught a second instance of the exact bug class already fixed once on the shell side:
`_resolve_python_open_path` took the FIRST literal `open()` call anywhere in a python body, not
the one the write-mode classification pattern had actually matched. In the ordinary
read-source/write-destination shape —

```python
data = open('a.txt').read()
open('b.txt', 'w').write(data)
```

— the resolver returned `a.txt`. Two consequences: the block message named the wrong file, and
the existence check ran against `a.txt` (which exists, because it was just read), so a genuinely
new `b.txt` target got blocked as a false positive — the exact defect class this whole build
weighs heaviest.

**Confirmed the bug reproduces exactly as described**, hand-built against a real two-file fixture
before touching any code: old resolver named `a.txt`; a `b.txt` that didn't yet exist still got
BLOCKED (should have been ALLOW). **Fixed the same way the shell-side redirect bug was fixed one
turn earlier**: anchor path extraction to the specific `re.Match` the write-mode classification
pattern produced (`match.group(0)`, the literal `open(...)` call text up through its mode
argument), never an independent re-search of the whole body. Re-verified the same fixture pair
both ways: `b.txt` absent → ALLOW; `b.txt` present → BLOCK correctly naming `b.txt`.

**Re-ran the corpus verification and the smoke suite as instructed. The split moved: 125/85 →
124/86 — one record flipped from ALLOW to BLOCK.** Found and hand-traced it
(`toolu_01JG1zAXhFmAGYpVicJhFJZB`, `concepts-rename` session): `content = open('concepts/
regime_vola/beta_breaks.py', encoding='utf-8').read()` ... `open('/tmp/actual_snippet.txt',
'w').write(snippet)`. Before the fix, the resolver named `beta_breaks.py` inside the
`concepts-rename` worker worktree — which no longer exists (deleted post-merge, see the
worktree-lifecycle confound already documented above), so the old, WRONG target happened to
report ALLOW. After the fix, the resolver correctly names `/tmp/actual_snippet.txt`, which exists
on this machine as a leftover from this same session's own earlier calibration work, so the new,
CORRECT target reports BLOCK. **Both the before and after verdicts for this one record are
themselves still inside the corpus-replay confounds already documented above** — the flip
demonstrates the resolution logic is now anchored correctly, not that this specific record's
verdict is now free of replay-timing noise. Smoke suite: 19/19 (18 plus the new internal-exception
case below), all corpus records still got a verdict, 0 errors.

**Fail-open is no longer silent.** `block_non_canonical_edit_workflow`'s `except Exception` around
`_decide` now prints `[block_non_canonical_edit] internal error, failing open: <type>: <message>`
to stderr before `sys.exit(0)`, in the same one-line diagnostic style as `src/proxy/
inject_poread.py`'s `[proxy_addon] poread: ...` lines. Exit code unchanged at 0 — failing open is
still correct, only the silence was the problem. Verified with a new smoke case that monkeypatches
`_decide` to raise directly (`dev/hook_smoke/test_block_non_canonical_edit.py`'s 19th case) —
subprocess-level fault injection through the sanctioned stdin-JSON surface alone could not
reliably force an internal exception (tried a `cwd` type-confusion and an embedded-NUL-byte
path first; both are already defended against internally, which is a good sign about the rest of
the code, not a test gap), so this one case imports the module directly and monkeypatches `_decide`
itself, same technique `test_block_worker_kill_while_working.py` already uses for its stub
`status_fn`.

**Documented, not fixed, per explicit instruction:** `_PY_HD_OPEN_RE` only recognizes a
single-quoted heredoc delimiter (`<<'DELIM'`). An unquoted (`<<PYEOF`) or double-quoted
(`<<"PYEOF"`) python heredoc is never extracted as a python invocation and falls through to the
generic strip-and-blank pass instead, going unseen. Not handled, because an unquoted delimiter
also breaks the canonical form's own reason for requiring a quoted one (interpolation-safety), and
no command in the 210-record corpus uses either shape. Written up as a Gotcha in
`src/hooks/DOCS.md` so a future session that finds one recognizes the gap immediately rather than
mistaking it for a mystery.

## Recap — 2026-09-15, session close

Self-check (`git diff integration --name-only`) confirms this milestone's full touched set:
`src/hooks/block_non_canonical_edit.py`, `src/hooks/hook_setup.py`, `src/hooks/DOCS.md`,
`dev/hook_smoke/test_block_non_canonical_edit.py`,
`dev/hook_smoke/verify_block_non_canonical_edit_corpus.py`, `dev/hook_smoke/DOCS.md`,
`dev/hook_smoke/md/block_non_canonical_edit_corpus_report.md`, and this file. DOCS.md staleness
check against real `wc -l` on every touched `src/`/`dev/` module: all four headings correct
(`block_non_canonical_edit.py` 244, `hook_setup.py` 212, `test_block_non_canonical_edit.py` 161,
`verify_block_non_canonical_edit_corpus.py` 115) — no correction needed this round.

This is the closing entry for this worker's `tool_use_safety` work this session. The
`cache`-area classification/extraction work earlier this same session has its own file,
`process-docs/cache/2026-09-15_bash_file_modification_classification.md`, already closed out with
its own recap sections — not touched from here, per the one-file-per-area rule.

**State for whoever picks this up next:** the hook is written, tested (19/19 synthetic smoke,
210/210 corpus records get a verdict with 0 internal errors), registered in `_HOOK_SCRIPTS`, and
committed on the `editops` branch. It is NOT active anywhere — `hook_setup.py` has refused to run
twice now, automatically, via this repo's own `post-commit` githook, because it correctly detects
it's being invoked from a worktree. Activation is a deliberate, separate step: merge this branch,
then run `python3 src/hooks/hook_setup.py` from the main repo root (a real terminal, not a Bash
tool call, per the stale-hook-recovery Gotcha in `src/hooks/DOCS.md` — though this is a fresh
registration, not a recovery, the same "real terminal" constraint applies since the script itself
guards against worktree execution). After activation, a real live-fire check (a genuine `sed -i`
against an existing scratch file, confirming BLOCK; a genuine canonical-form edit, confirming
ALLOW) would be the natural next verification — not attempted here, same deferral pattern
`process-docs/tool_use_safety/2026-07-22_block_po_read_hook.md` used for its own hook.
