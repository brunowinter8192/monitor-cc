# dev/cache/

## Role
Persists a durable, deduplicated extraction of every Bash tool call in the recorded dual-log
corpus whose command text matches a known file-content-modification form. Touch when the
extracted corpus needs regenerating after `src/logs/dual_log/` rotates old sessions out, or when
`src.constants.BASH_FILE_MODIFICATION_FORMS` changes. Do not touch `dev/cache/samples/` — a
prior, unrelated measurement owns that directory.

## Public Interface
No `__init__.py`. `extract_bash_file_mods.py` is run directly:
`./venv/bin/python dev/cache/extract_bash_file_mods.py`.

## Flow
Streams every `src/logs/dual_log/*_original.jsonl` file in the main checkout line by line, finds
`Bash` `tool_use` blocks, deduplicates by `tool_use` id per session (the same block reappears in
every later cumulative request of its session), matches each surviving command's text against
`src.constants.BASH_FILE_MODIFICATION_FORMS`, and writes one JSON record per match to a new,
run-stamped file under `dev/cache/jsonl/`. No aggregation, no statistics — ad hoc analysis is
expected to run on top of these files later.

## Modules

### extract_bash_file_mods.py (102 LOC)

**Purpose:** Extracts and persists every Bash tool call whose command matches a known
file-content-modification form, verbatim, with enough identity to find it again.
**Reads:** every `*_original.jsonl` file under the main checkout's `src/logs/dual_log` (hardcoded
`MAIN_REPO_ROOT`, same pattern as `dev/proxy_instrumentation/p7_blocklist_258_probe.py` — this
worktree carries no logs).
**Writes:** `dev/cache/jsonl/bash_file_mods_<UTC-timestamp>.jsonl` (`%Y%m%dT%H%M%SZ`, the run's own
start time — one new file per run, never an existing one), one JSON object per matched,
deduplicated `tool_use` block: `session`, `tool_use_id`, `timestamp`, `matched_forms` (list of
classification labels), `command` (the full, verbatim command string).
**Called by:** none — manual, re-run after `src/logs/dual_log/` rotation or a classification
change.
**Calls out:** `src.constants` (`BASH_FILE_MODIFICATION_FORMS`).

---

## Gotchas
- The classification this script matches against lives in `src/constants.py`
  (`BASH_FILE_MODIFICATION_FORMS`), not here — it is shared with a later `src/hooks/` consumer, so
  a hook is never allowed to import from `dev/`.
- Matching is text-pattern-based, not a real shell parse. It cannot distinguish a genuine
  redirect/in-place-edit invocation from the same substring appearing inside prose, a quoted
  search term, or another script's own source text. Observed in this exact corpus: a
  `duallog search "sed -i" --only tool_use` call and this task's own prompt text (quoting `sed -i`
  as a bullet point) both produced a `sed -i` match with no `sed` actually invoked; several
  `<>`/`>|`/`gawk -i inplace`/`tee (truncating)` matches came from this worker's own exploratory
  Bash calls that construct or discuss those exact regex substrings as Python string literals,
  not from real invocations of those forms. `matched_forms` and the full verbatim `command` are
  carried specifically so a downstream reader can make this call itself; the extractor does not
  filter or guess.
- The classification deliberately excludes a family of commands that CAN also mutate a file's
  content but were judged out of frame — general-purpose file-management/patch/block-I/O tools
  whose overwrite behavior is incidental to a different primary purpose, not a canonical shell
  writing form. Excluded, by name: `cp`, `install`, `dd`, `patch`, `git apply`, `truncate`, `mv`,
  `rsync`, `curl -o`, `tar -x`, `unzip -o`, `git checkout --`. The frame kept is: redirection
  operators (`>`, `>>`, `>|`, `<>`), canonical in-place text editors (`sed -i`, `perl -pi`/`-ni`,
  `gawk -i inplace`), `tee`/`tee -a`, and interpreter one-liners keyed on an explicit `open()`
  write mode. Reasoning: every excluded command's primary job is something other than "write this
  text to this file" (copying, applying a diff, block-device I/O, archive extraction, VCS
  checkout), and the moment overwrite-capable-as-a-side-effect is the inclusion bar, the list has
  no natural stopping point — almost any command with a destination-path argument qualifies. A
  later hook built off `BASH_FILE_MODIFICATION_FORMS` needs a completeness guarantee a dev-area
  report does not; whoever extends the classification for that hook should start from this
  excluded list rather than rediscover it, and should re-litigate each entry on its own merits
  rather than accept this line-draw by default.
- `src/logs/dual_log/` is gitignored runtime data, live-growing from concurrent sessions
  (including this worker's own) — re-running this script shifts the exact record count without
  changing the underlying classification or method.
- The output is opened with `'x'` (exclusive create), not `'w'` — a second run landing on the same
  filename is a tripwire, not a fallback: it raises `FileExistsError` and aborts rather than
  silently replacing an earlier run's file. At one-second filename granularity this only fires on
  two runs starting in the same second, which is correct behavior to refuse, not a bug to work
  around.
- `dev/cache/jsonl/bash_file_mods_20260915T142910Z.jsonl` (210 records) is the file originally
  committed as the fixed-path `bash_file_mods.jsonl` before this run-stamped-naming milestone —
  renamed, not regenerated, into the new convention. Its timestamp is the file's own on-disk
  mtime at creation (verified against the commit that introduced it, `51d156b9`, to within ten
  seconds), not a fabricated value.

## State
`dev/cache/jsonl/` accumulates one snapshot file per run, named by that run's own UTC start time.
An existing run's file is never overwritten or appended to — a later run's poorer, rotated-corpus
result cannot silently replace an earlier, richer one. There is no single canonical "current"
file; a reader wanting the newest snapshot picks the lexicographically last filename in the
directory.
