# bd Mutation Revert — Resolved on bd 1.0.4 + Hook Retired

**Status:** RESOLVED. Bug disproven by source analysis + live tests. Hook retired.

## Source Analysis (gastownhall/beads `main` @ fbcee6c, mirrors installed bd 1.0.4 ce242a879)

### `maybeAutoImportJSONL` — insert-if-new, not UPSERT

`cmd/bd/auto_import_upgrade.go`:
- Emptiness guard: `GetStatistics` is called first; if the DB is non-empty, `maybeAutoImportJSONL` aborts before touching any rows. A stale `issues.jsonl` on a live, non-empty DB never triggers import.
- Fallback importer: `importFromLocalJSONLConflictSkip` — insert-if-new semantics (GH#3955). Source comment verbatim: a stale `issues.jsonl` "can no longer be re-imposed on top of live Dolt rows — the worst case degrades to a harmless no-op instead of clobbering recent writes."
- **Conclusion:** auto-import categorically cannot revert a close on bd 1.0.4, regardless of JSONL contents.

### `maybeAutoCommit` — nothing-to-commit is a no-op

`cmd/bd/dolt_autocommit.go`:
- `if isDoltNothingToCommit(err) { return nil }` — the "nothing to commit" warnings in `dolt-server.log` are benign. No revert, no rollback, no state change.
- **Conclusion:** those log warnings (previously suspected as a symptom) are not evidence of any bug.

## Live Tests (Monitor_CC, bd 1.0.4 ce242a879)

### Single-close test

Throwaway bead → `bd close` → 12 reads (`bd show` + `bd list`) + JSONL file check + `bd dolt stop && bd dolt start` (cross-session bounce) → status: **CLOSED, held throughout**. No revert at any point.

### Batch-close test (the hook's primary concern)

3 ids closed in ONE `bd close <A> <B> <C>` invocation → all 3 confirmed CLOSED → 12 reads + server bounce → all 3: **CLOSED, held**. The batch-revert (#4135) mechanism is not present on 1.0.4.

## JSONL Cleanup (Monitor_CC — done; other projects — pending, not executed here)

End-state established on Monitor_CC:
- `bd config set export.auto false` — disables auto-export entirely; with no JSONL being written, the import path has no input to act on.
- `.beads/issues.jsonl` deleted — removed the existing stale file; `os.Stat` in `maybeAutoImportJSONL` aborts at file-not-found before any DB check.
- `.beads/.auto-import-issues.jsonl` deleted — same reason; eliminates the "auto-importing into empty database" log noise that was appearing on Monitor_CC on cold starts.

**Rollout to other projects:** PENDING. Not executed as part of this task. Opus's responsibility.

## Hook Retirement

Files deleted:
- `src/hooks/block_batch_bd_close.py` (149 LOC) — the PreToolUse hook
- `dev/hook_smoke/test_block_batch_bd_close.py` (127 LOC) — 29-case smoke test

`hook_setup.py` `_HOOK_SCRIPTS` updated: tuple `("block_batch_bd_close.py", "Bash")` removed → future `hook_setup.py` runs will not re-register it. Live de-registration from `~/.claude/settings.json`: pending (Opus's job — re-run `python3 src/hooks/hook_setup.py` from main repo after merge; `_sweep_stale_hooks()` removes the dead entry automatically).

Hook inventory record updated: 19 → 18 hooks, 15 → 14 block hooks; the retired hook's
section marked RETIRED, technical content preserved as historical record; SOLL updated
to reflect retirement.

`src/hooks/DOCS.md`: `block_batch_bd_close.py` module entry removed.

The companion investigation writeup for this topic: SUPERSEDED note prepended; original content preserved as historical evidence.
