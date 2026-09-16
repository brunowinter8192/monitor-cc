## Salvage from dev/bead_tracker/smoke.py

```
"""
Smoke test for bead_tracker_hook per-subcommand processing.

Creates two temporary test beads, pipes crafted PostToolUse payloads
to the hook, verifies labels via 'bd label list --json', then cleans up.

Usage (from project root): ./venv/bin/python3 dev/bead_tracker/smoke.py
"""
```

```
PROJECT_ROOT = Path(__file__).parent.parent.parent   # worktree / project root
```

```
BD_DB = None   # discovered in smoke_workflow
```

```
# Walk up from PROJECT_ROOT to locate .beads/dolt
```

```
# Create a bead and return its ID; returns None on failure
```

```
            # line format: "✓ Created issue: Monitor_CC-xxxx — title"
```

```
# Return True if bead carries the given label
```

```
# Remove label (no-op if absent)
```

```
# Pipe a PostToolUse payload to the hook; cwd is project root so hook finds DB
```

```
# Clean slate → fire hook → verify labels; returns True on PASS
```

```
# Remove labels + delete beads; safe on None
```

## Salvage from dev/bead_tracker/DOCS.md

Nothing cut — the existing DOCS.md content (Role, one Modules entry) already fits the required format sections. Rewritten in place with the same substance, no section relocated to salvage.

## Notes for successor

- 1 file, 10 comments + 1 docstring — matches the measured state exactly (2 trailing comments on `PROJECT_ROOT =`/`BD_DB =` infrastructure lines, 8 standalone comments each directly preceding a function or a line inside one).
- No load-bearing docstring: grepped `__doc__` — zero hits, no `argparse` in this file. Docstring deleted outright.
- **Not run**: this script mutates the real, shared `bd` issue tracker at `.beads/dolt` — it creates two real beads via `bd create`, exercises them, then deletes them via `bd delete --force`. Even though it cleans up after itself and the target hook (`bead_tracker_hook.py` under `src/menubar`) no longer exists in the tree (per the pre-existing DOCS.md, this script is already DEAD CODE), running it still touches production bead-tracker state through a live `bd` CLI subprocess — not a sandboxed dev fixture. Classified as unsafe to run for this milestone's proof.
- Verification used instead: a token-skeleton diff (`ast` to locate the one docstring's exact span, `tokenize` to strip all `COMMENT` tokens plus that docstring's `STRING` token, then drop purely structural tokens — `NL`/`NEWLINE`/`INDENT`/`DEDENT`/`ENCODING`/`ENDMARKER` — from both the pre-edit and post-edit token streams). The remaining `(token_type, token_string)` sequences are byte-identical (JSON-dumped and diffed) — proves the strip changed nothing but comments and the docstring.
- The token-skeleton helper lives at `/tmp/c4_4_verify/skeleton.py` for this session only (not committed — per dev/ staging rules, throwaway verification tooling stays out of the tree unless it earns a permanent spot as a regression guard, which a one-off comment-strip proof does not).
