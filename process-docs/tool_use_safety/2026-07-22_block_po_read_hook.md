# block_po_read Hook Added, 2026-07-22

## Motivation

When a Bash tool's output exceeds CC's inline size limit, CC persists the FULL output to an export file (`.../tool-results/<id>.txt` under a `.claude/` project/session tree) and injects only a `<persisted-output>` preview into the transcript. A proxy-log audit (822 real cases) established the invariant discriminator: the path CONTAINS `/.claude/` AND ENDS `.txt` — no other `.txt` file under any `.claude/` directory is ever legitimately read via shell in this codebase. Nothing previously prevented a shell reader (`head`/`tail`/`grep`/`cat`/`sed`/etc.) from consuming only PART of one of these exports and acting on an incomplete view — the exact failure mode `block_log_read.py.disabled` was built to prevent for `.log` files, unaddressed for persisted-output exports.

## Design — block, not rewrite; path-schema only, no size threshold

Unlike the `.log`-reading rewrite hooks (silent pipe-strip), this is a BLOCK hook: there is no unique computable "corrected" shell command for a partial-read-of-a-large-export — the correct fix is a different TOOL entirely (Read, with `offset`/`limit` for paging), not a rewritten Bash command. Blocking forces the agent to switch tools rather than silently rewriting Bash into something that still can't page a multi-MB file cleanly.

Structural clone of `block_log_read.py.disabled`'s Branch B only (reader-tool + matching input-path segment → block): no state file, no session-count tracking, no Branch A — persisted-output partial reads are wrong on the first occurrence, not just on repetition (unlike log-polling, where the concern is repeated re-reads).

Discriminator is PATH SCHEMA ONLY (`/\.claude/` substring + `.txt` suffix on the same token) — deliberately no byte-size threshold. A size cutoff would need tuning and could miss small-but-still-partial exports or false-positive on legitimately small `.claude/*.txt` files that happen to cross an arbitrary line; the schema match is exact and needs no calibration.

Reader-tool set: the `block_log_read` reader list (`head`, `tail`, `grep`, `egrep`, `fgrep`, `sed`, `awk`, `cut`, `less`, `more`, `cat`, `tac`, `nl`, `zcat`) plus `rg` (ripgrep, common in this environment, absent from the older template) and `cut` (already in the fixed scope list).

No Read-tool matcher — Read (with any `offset`/`limit`) is the sanctioned full/paging reader and must stay fully allowed; adding a Read-side component here would work against the hook's own goal of directing agents toward Read.

## Verification — this session

`py_compile` clean on the new hook (`src/hooks/block_po_read.py`, 76 LOC) and `hook_setup.py`. Smoke test (`dev/hook_smoke/test_block_po_read.py`, 14 cases, real subprocess invocations of the hook with real stdin JSON): 14/14 PASS — 6 positive single-reader blocks (head/tail/grep/cat/sed/rg on a `~/.claude/.../tool-results/<id>.txt` path), 1 piped block (`cat <path> | head`), 4 no-ops (normal file, `.log` file, `/tmp/foo.txt` not under `.claude/`, `.claude/` path not ending `.txt`), 1 redirect-write no-op, 1 quoted-string no-op, 1 malformed-JSON-stdin fail-open. Registration confirmed via `git diff` on `hook_setup.py`: `_HOOK_SCRIPTS` 38→39 entries. Live fire against a real running CC session / deployment onto the actual `~/.claude/settings.json` was not attempted from this worktree — `hook_setup.py`'s own `_guard_not_worktree()` refuses execution from a worktree path by design; that live-fire verify is deferred to the orchestrator after merge onto the main repo.
