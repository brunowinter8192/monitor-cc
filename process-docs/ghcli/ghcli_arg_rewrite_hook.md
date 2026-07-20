# gh-cli Positional-Arg Rewrite Hook (2026-05-28)

**Status:** Proposal. Hook not yet built. Tracked by bead.

## Problem

`gh-cli` tools that take repo as TWO positional args — `grep_file`, `grep_repo`, `get_file_content` (and any other `owner repo ...` tool) — fail when `owner/repo` is passed as ONE slashed arg:

```
gh-cli grep_file ronaldoussoren/py2app src/py2app/build_app.py "pattern"   # WRONG
→ error: the following arguments are required: pattern
```

The slash collapses `owner`+`repo` into one token, shifting every later positional left by one → the last required positional (`pattern` / `path`) is reported missing.

Correct form (owner + repo separate):

```
gh-cli grep_file ronaldoussoren py2app src/py2app/build_app.py "pattern"    # RIGHT
```

`search_code` / `search_items` are NOT affected — there the repo is given inside the query string as `repo:owner/repo`, where the slash is correct syntax. This asymmetry (slash-OK in query-string tools, slash-WRONG in positional tools) is exactly what trips up usage: the `repo:owner/repo` habit leaks into the positional tools.

Not a gh-cli defect — pure usage error. Recurred multiple times in one session 2026-05-28.

## Solution Direction — Rewrite Hook

Same family as the existing `src/hooks/rewrite_*.py` (`rewrite_bd_invalid_repo.py`, `rewrite_chained_sleep.py`, `rewrite_rag_cli_search_noise.py`): a PreToolUse hook on Bash that detects a `gh-cli` invocation of a positional-repo subcommand where arg 1 (the would-be `owner`) contains a `/`, and rewrites `owner/repo` → `owner repo` (split on the single slash).

Design constraints (per `decisions/OldThemes/hook_design_principles/A1_use_case_specificity.md`):
- Match SHARPLY: only `gh-cli <subcmd> <token-with-slash> ...` where `<subcmd>` ∈ {`grep_file`, `grep_repo`, `get_file_content`, `get_repo`, `get_repo_tree`, ...positional-repo tools}. Pull the exact tool list from the github-search skill (SKILL.md Quick Reference), do NOT hardcode a guess.
- Do NOT touch `search_code` / `search_items` / `search_repos` / `search_discussions` (query-string tools — slash is valid there).
- Do NOT touch a slashed token that is actually a file path argument (e.g. the `path` positional legitimately has slashes). The split applies ONLY to the FIRST positional after the subcommand (the owner slot), not later ones.
- Silent rewrite (like the other rewrite hooks), optionally log to the hook fire-log.

## Open Questions

- Exact positional-repo subcommand list — enumerate from the github-search skill's CLI reference, not from memory.
- Rewrite vs block: rewrite is friendlier (matches `rewrite_*` family); a block would force manual correction. Lean rewrite.
- Edge: what if a real `owner` legitimately contains no slash but the user passes `owner repo` correctly — hook must no-op (only fires when arg-1 has a slash).

## Quellen

- `src/hooks/` — existing `rewrite_*.py` hooks as pattern template
- `src/hooks/DOCS.md` — hook registry
- github-search skill `SKILL.md` — canonical positional-arg tool list + correct invocation forms
- `decisions/OldThemes/hook_design_principles/A1_use_case_specificity.md` — sharp-match design constraint
