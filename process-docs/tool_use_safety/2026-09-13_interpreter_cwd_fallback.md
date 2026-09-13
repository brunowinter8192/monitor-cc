# block_cli_chained.py: interpreter-form cwd fallback (2026-09-13)

## Task

`match_interpreter_cli_segment` in `_known_cli.py` resolved the `python cli.py <sub>` interpreter
form to a tool only by finding one of the 5 known project-directory names (`_CLI_PY_DIR_TOOL`:
gh-cli, rag-cli, reddit-cli, websearch, jobscraper/linkedin) somewhere in the Bash command text.
When the session already sits inside the CLI's own directory, the command carries no such name
(`python3 cli.py search ...`), so resolution returned `None` and every rule in
`block_cli_chained.py` was skipped.

Measured over 352 session transcripts: 919 Bash calls mention `cli.py`, 306 in interpreter form. Of
those, 14 carry no directory name while the session's `cwd` IS a known CLI directory — 2 of the 14
were real bypasses of this hook's own rules (one protected subcommand redirected to a file, one
piped into `head`). 259 other interpreter-form calls with no directory name in the command have a
`cwd` that is NOT a CLI directory (almost all a different project's own `cli.py`, a chore tracker)
and must keep passing.

## Fix

`match_interpreter_cli_segment(segment, command_context, cwd=None)` now falls back to searching
`cwd` with the same `_CLI_PY_DIR_RE` regex already used against the command text, but ONLY when
the command text itself yields no match — command-text resolution keeps priority unconditionally,
so any case that already resolved before this change resolves identically now. The regex needed no
changes: it already boundary-anchors on `/` or whitespace, and a cwd is a plain `/`-separated path
with no spaces, so it matches a known directory name anywhere in the path, including a worktree
nested below it (`.../cli/websearch/.claude/worktrees/rawlog`). `resolve_cli_segment` and every
call site in `block_cli_chained.py` (`_parse_command`, the orchestrator, all 3 rule-check
functions) now thread `cwd` through; `cwd` comes from the PreToolUse payload's top-level `cwd`
field via `payload.get("cwd")`, defaulting to `None` on a missing/non-string value or a parse
error — same fail-open shape as the rest of the module.

Smoke suite `dev/hook_smoke/test_block_cli_chained.py`: 42 -> 45 cases. `CASES` tuples grew an
optional 4th element (`cwd`, `None` if omitted) threaded through `_run_hook`; the 2 measured
bypasses became BLOCK cases with a CLI-dir `cwd`, the other-project `cli.py`-with-unrelated-`cwd`
shape became a PASS case. All 45 pass.

## Known residual — NOT a bug, an accepted, unobserved gap

If a Bash command `cd`s into a FOREIGN directory (not one of the 5 known ones) and calls that
directory's own `cli.py`, while the session's `cwd` (as reported in the PreToolUse payload)
happens to sit inside one of the 5 known CLI directories, the cwd fallback still fires and can
block wrongly — the fallback has no way to see that the command's own `cd` already moved execution
away from the reported `cwd`. Measured directly against the shipped hook:

- `cd /tmp/some-other-project && python3 cli.py scrape_url_chromium "x" > /tmp/out.txt` with
  `cwd=/Users/.../cli/websearch/.claude/worktrees/rawlog` -> exit 2 (false block; the foreign
  project's own `cli.py` happens to define a `scrape_url_chromium` subcommand identically named to
  websearch's protected one).
- Worse shape, `linkedin`/`jobscraper` protects `None` (every subcommand): `cd
  /tmp/some-other-project && python3 cli.py whatever_subcommand > /tmp/out.txt` with
  `cwd=/Users/.../cli/jobscraper/.claude/worktrees/xyz` -> exit 2 (false block on ANY subcommand
  name, no name collision needed at all, since `is_protected_segment` returns `True`
  unconditionally when `PROTECTED_SUBCOMMANDS[tool]` is `None`).

This shape did not occur once in the 306 measured interpreter-form calls (all 14 no-directory-name
cases had a command that stayed inside the cwd's own tool — no observed `cd`-away-then-call-a-
different-`cli.py` case). Per the evidence-burden standard, nothing was built against it: it is a
real, understood mechanism, not a hypothetical hand-wave, but it stays unobserved in real data, so
a defence for it would be complexity added ahead of any measured failure. If a real transcript ever
shows this shape, the fix is straightforward: track the last `cd` target per chain segment (already
computed for other purposes in `block_cli_chained.py`'s segment splitting) and prefer it over `cwd`
whenever a `cd` is present in the same segment, using `cwd` only when the segment has none.

## Related note — cwd can be stale

The PreToolUse payload's `cwd` field is confirmed present from real captured payloads (Claude Code
issues #72262 and #82413) and from the decompiled payload builder (#76333). Issue #83636 reports
that the reported `cwd` can go stale and point at the session's LAUNCH directory rather than its
current one. This fallback treats `cwd` strictly as a hint that narrows resolution to one of the 5
known directory names — it never widens the block surface beyond those 5, and a stale `cwd` at
worst causes the same class of residual described above (fallback resolves to a tool the command
isn't actually calling) or a missed resolution (fallback fails to recognize a directory the session
actually is in) — it cannot cause the hook to block a call that has nothing to do with any of the 5
CLIs.
