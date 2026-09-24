# Hook fallbacks and tripwires: trace lines (HK01-HK14) — worker mcfix-hooks

## Decisions applied (from the Main review of the Phase 5 hook findings)

- Hooks stay fail-open. No exit code, stdout or block message of any hook changed.
- One new `log_fire` decision value, `"trace"`, same record shape as `block` (`reason` field). Every LOG item is one trace line in the firing log (`MONITOR_CC_HOOK_FIRING_LOG` or `src/logs/hook_firing.jsonl`). Filter with `jq 'select(.decision != "trace")'`.
- HK01: all 31 `_parse_*` handlers log `parse error: <type>: <msg>`. Only the handler is logged, not a legitimately absent `command`.
- HK02: `log_fire` creates its directory; on write failure it prints one stderr line `log_fire failed: ...`. In a block hook that line lands after the block text in the model-visible stderr, only when logging itself fails.
- HK03: `_strip_non_shell_active` catches `_StripError` only and logs `raw-text fallback: unclosed <heredoc|single quote|double quote|ANSI-C quote>` under hook `_shell_strip`. A bug elsewhere in `_strip_impl` now crashes the hook (exit 1, non-blocking for Claude Code).
- HK04: the four `_strip_quoted` copies keep dropping the remainder of an unterminated quote and now log `unterminated quote: remainder dropped`. Detection: the scan index reaches `n` before the closing quote.
- HK05, HK14 deleted: `_resolve_root` try/except, `_is_directory` try/except (`os.path.isdir` returns False on ValueError, verified with a NUL byte path), `_unpack_entry` and the 3-tuple event route (`_DEFAULT_EVENT` became `_EVENT`).
- HK06: shlex `ValueError` in gh_cli_local_path, rag_docs_layer, rag_cli_document_repeat logs `shlex ValueError: segment exempt`. An unclosed quote therefore yields two traces: the strip fallback and the shlex exemption.
- HK07: block_po_read logs `size unknown, blocking: <path>` before the unchanged block.
- HK08: rag repeat state: read failure, write failure and count reset are logged; corrupt lines are logged once per read (`skipped N corrupt lines`) and disappear on the next write, so no repeat spam. A missing state file stays silent (first run).
- HK09: kill/send twins log workflow exception, `status_fn` exception, worker-cli not found, non-zero rc, subprocess exception incl. the 3s timeout. The string-sort version pick in `_resolve_worker_cli` was not touched.
- HK10: `rewrite_background_sleep._in_worktree` stays fail-open (True) and logs `getcwd failed, hook skipped`. block_cd_drift and block_worker_spawn_placement stay unguarded (accidental tripwire).
- HK11: `_sweep_stale_hooks` prints `Swept stale hook: <event> <command>` to stderr per removed entry.
- No action: HK12, HK13, HK15.

## Verification that held up

- Before/after harness (`/tmp/hkcompare.py`, not committed): `git archive integration src/hooks` into `/tmp/hooks_before`, then every active hook is run on the old and the new tree over 10416 (hook, payload, cwd) jobs. Payloads: 60 distinct commands sampled from the production `hook_firing.jsonl` (read-only) in foreground and background variants, synthetic unclosed-quote/heredoc/worktree/po/rag/worker commands, Read/Edit/Write payloads, and malformed stdin (empty, `not json`, `[]`, null tool_input, non-str command). Two cwds: `/tmp` and the worktree. Firing log and rag state file point to a temp dir per run.
- Compared per job: exit code, stdout, stderr (traceback paths and line numbers normalized), firing-log records without `ts` and without `trace` records, rag state file. Result after each of the five change groups: 0 diffs. Trace records were emitted by 31 hooks (only additions).
- Harness pitfalls seen: (a) restricting PATH to `/usr/bin:/bin` selects Python 3.9 which cannot import the hooks (`str | None`), producing hundreds of fake diffs; (b) comparing log records including `ts` gives fake diffs when the two runs straddle a second boundary.
- Existing crash observed before the change and unchanged: `block_path_typo.py` with stdin `[]` dies with an AttributeError traceback after its parse try (payload is a list, `.get` is outside the try).
- Provoking test `dev/hook_smoke/test_hook_trace_lines.py`: 17 cases in parallel threads, all PASS on the new tree, 16 FAIL on the old tree (the passing one is the NUL-byte case, which shows the deleted handler was unreachable).
- The existing kill/send tests pass (13/13, 12/12). Their fakes do not raise, so no trace lines reach the production log from them; a fake that raises in `decide` would now write a trace line to the firing log unless the env variable is set.
- Test caveat: `case_status_fn_raises` sets `MONITOR_CC_HOOK_FIRING_LOG` in `os.environ` of the test process for a moment; other cases pass their own log path explicitly, so it did not interfere.

## Hazards

- Committing in a worktree triggers `.githooks/post-commit`, which runs `hook_setup.py`; it exits with the worktree-guard error text. The commit still succeeds. `gcommit` skips files whose path contains `venv` (block_venv_no_redirect.py needed a plain `git commit`).
- `hook_setup.py` was never run against the real `~/.claude/settings.json`; the sweep print is proven on a dict in memory.
