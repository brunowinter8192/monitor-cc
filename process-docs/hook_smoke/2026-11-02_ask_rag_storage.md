# ask_rag_storage: permission dialog for every operation on rag-cli storage (2026-11-02)

## Requirement

The user runs Claude Code with `permissions.allow` holding bare `Bash`, `Read`, `Write`, `Edit`, `Glob`, `Grep` and `defaultMode: acceptEdits`, so nothing prompts. For two folders he wants the native dialog every time, for every operation:

- `~/Documents/ai/Meta/ClaudeCode/cli/rag-cli/data/pdf/` (original PDFs)
- `~/Documents/ai/Meta/ClaudeCode/cli/rag-cli/data/documents/` (converted Markdown)
- every symlink into them. Observed on 2026-11-02: `Berichte/`, `Literatur/`, `Skript/` of `Documents/BOM1` and `Documents/wise2627/BOM1`, plus `Literatur/`, `Skript/`, `Übungen/` of the other wise2627 courses, all pointing into `data/pdf/{bom1,bom1-reference,wise2627}/`.

Not affected: `rag-cli search`, `expand_chunks`, `list_documents`, `list_collections`, `progress`. `rag-cli update_docs` writes nothing into `data/` (checked in `src/rag/sync.py`) and stays free. Only `rag-cli index` and `rag-cli delete` change files there.

## Decision: hook returns `ask`, never a block

`src/hooks/ask_rag_storage.py` prints `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask", "permissionDecisionReason": ...}}` and exits 0. It is registered six times (Bash, Read, Write, Edit, Glob, Grep). `log_fire` got the decision value `ask`, recorded with a `reason` field like `block`.

## Detection (what counts as a hit)

A path hits when its `realpath` equals a storage root or lies below it (compared on the path boundary: `data/pdf-old` does not hit). Three additions on top:

1. Literal text. After variable substitution, any token containing a root as text hits. Covers `bash -c "cat <root>/x.md"` and paths built from variables, e.g. `R=<rag-cli>; cp $R/data/documents/a $R/data/documents/b`.
2. Directory with a symlink inside. A token that resolves to a real directory hits when one of its direct entries (first 5000) is a symlink whose `realpath` is inside a root. Observed 2026-11-02: `ls .../wise2627/BOM1/Berichte` has no storage path and `realpath` of `Berichte` is not storage, but all 75 entries are symlinks into `data/pdf/bom1`. Subdirectories are not descended.
3. Working directory. After the simulated `cd` the same two tests (inside a root, or symlink directory) apply to the working directory, so a bare `ls` in `Berichte/` hits. Commands that never touch the filesystem (`cd`, `unset`, `export`, `echo`, loop keywords, ...) are exempt from this test.

Bash handling:

- Tokenizer is `shlex` with `punctuation_chars`; newlines become `;`. On `ValueError` (unbalanced quote, e.g. an apostrophe in a heredoc body) a plain split is used and a trace line `shlex fallback` is logged.
- Leading `NAME=value`, `export`, `env [-u X] NAME=v`, and keywords `do/then/if/...` are peeled off the command word. Assignments feed a variable map (initialised from the hook's environment); values containing `$(` or backticks are not stored.
- Unresolved `$var` in a token: the token is cut at the first `$` and the prefix is tested (`Berichte/$f` still hits through the directory test).
- `cd` is tracked across segments, start is `cwd` of the payload. `cd` with an unresolved target makes the working directory unknown; relative tokens are then skipped.
- Globs are expanded on the filesystem, capped at 500 matches, non-recursive.
- A segment whose command word is `rag-cli` and whose subcommand is `search`, `expand_chunks`, `list_documents`, `list_collections` or `progress` is skipped entirely. `index` and `delete` ask without any path.

Tools: Read/Write/Edit test `file_path`; Glob tests `path` (default cwd) and the pattern joined onto it; Grep tests `path` (default cwd).

Roots are `~/Documents/ai/Meta/ClaudeCode/cli/rag-cli/data/{pdf,documents}`. Tests override them with `MONITOR_CC_RAG_STORAGE_ROOTS` (path-separated). Both the literal and the `realpath` form of each root are used, because macOS temp directories sit behind the `/var` -> `/private/var` symlink.

## Known gaps (accepted)

- Paths that exist only at run time (`$(readlink "$f")`, loop variables with no resolvable prefix, file contents) are not seen.
- A parent folder (`rag-cli/data`, `rag-cli`, `~/Documents/ai`) never hits, also not for recursive Grep/Glob/`find`. Otherwise most searches under home would prompt.
- A recursive Grep/Glob from a project root does not hit although it traverses `Berichte/`; Glob is non-recursive in the hook and ripgrep does not follow symlinks.
- Relative or symlink paths inside a quoted compound (`bash -c "ls Berichte"`) are only caught by the literal text test.
- `cd` inside a subshell is treated like a normal `cd`.
- Mentions of a root as plain text (echo, commit message, heredoc body) prompt too. Accepted by the user; heredoc bodies are deliberately not exempted.
- Only the one absolute root is covered. A second rag-cli checkout or a renamed copy is not.
- `rag-cli` is recognised by the basename of the command word; `python3 cli.py index` is not.
- Symlinks created inside the same Bash call are not visible to the hook.
- Hooks of the same event do not override each other's `ask`: `block_path_typo` can emit `allow` with `updatedInput`; whether the strictest decision wins is taken from the Claude Code hooks documentation and was not tested live.
- Whether `ask` overrides the bare `Bash`/`Read`/... allow rules and `acceptEdits` is the open question of the live verification: run `ls` on `rag-cli/data/pdf/bom1` in a fresh session after the hook is registered. A session started with `--dangerously-skip-permissions` may not prompt.

## Test

`dev/hook_smoke/test_ask_rag_storage.py`, 44 strands, all green on 2026-11-02. Each case builds its own temp tree (`proj/Berichte/*` symlinks into `rag-cli/data/pdf/bom1`, `proj/Notizen`, `proj/plain`, documents folders) and points the roots at it; production-path cases pin `HOME` and use no filesystem.

Observed payloads of 2026-11-02 and their verdicts:

- `pdftotext -f 22 -l 22 -layout <Berichte symlink> -` : ask (symlink).
- `P=<rag-cli>/data/pdf; cd <Berichte>; for f in *.pdf; do ... mv "$t" "$P/bom1/$f"; ln -s ...; done` : ask (literal text through `$P`). The loop body in the test is a reconstruction; the original body was not available. A variant without `P` and with `*.pdf` in the symlink directory also asks (glob and working directory).
- `R=<rag-cli>; cp $R/data/documents/wise2627-reference/BOM1_* $R/data/documents/bom1-reference/` : ask.
- `env -u PYTHONHOME ... rag-cli index --collection bom1-reference` : ask (subcommand).
- `unset PYTHONHOME ...; rag-cli search "Performance Bonus target achievement" bom1-reports --document 'ADS_RemunerationReport%'` : no decision.
- `ls .../BOM1/Berichte` and `ls .../BOM1/Berichte/ADS_*` : ask (directory with symlinks; glob). Sibling `ls <proj>` whose entries are real directories : no decision.

Manual check on the real machine (not part of the suite): the hook asked for `pdftotext` via `Documents/BOM1/Berichte/...`, for `ls` on `wise2627/BOM1/Berichte`, `wise2627/COKA/Literatur` and `rag-cli/data/pdf/bom1`; it stayed silent for `git status`, `rag-cli search` and `ls /opt/homebrew/bin`. Runtime 0.05 s, 0.17 s for `/opt/homebrew/bin` (many symlinks to resolve); the registered timeout is 5 s.

## Pitfalls for a successor

- `shlex` merges adjacent punctuation: `);` arrives as one token. Separator detection therefore tests "all characters in `;&|()`", not equality with a list.
- Tests with `{T}` placeholders replace inside the JSON string; temp paths contain no JSON special characters.
- `run_all.py` rewrites the tracked `md/run_all.md` on each run; it was reverted before the commit.
