# hook_smoke test structure, Phase 3 fixes (2026-09-24)

## What was wrong

- Every `test_block_*`/`test_rewrite_*` script spawned its hook with the cwd-relative path `src/hooks/<name>.py` and the inherited environment. It only worked from the repo root, and every block/rewrite decision was appended to the hook fire log the environment pointed at. Observed: one baseline run of all suites with `MONITOR_CC_HOOK_FIRING_LOG` exported to a temp file produced an 80935-byte log; the same run after the change produced no file at all.
- `test_bg_task_detection.py` wrote its scratch dir into the live `/tmp/claude-<uid>` tasks base and ran `lsof +D` over the whole live tree. It also could not be imported at all before the change: `from menubar import proc_cache` fails with "attempted relative import beyond top-level package" (the package needs the repo root on `sys.path` and the `src.` prefix).
- `test_fire_log.py`: the "canonical path untouched" check used a fresh random path that was never given to the hook, so it could not fail.

## What changed

- `hook_runner.py`: `run_hook(hook, stdin_bytes, extra_env, cwd)` resolves the hook against the repo root derived from `__file__`, defaults cwd to the repo root, points `MONITOR_CC_HOOK_FIRING_LOG` at a per-call temp dir. A value of `None` in `extra_env` removes a variable. `abort_if_failed(failures)` prints the failure list and exits 1.
- All table tests call `run_hook` and `abort_if_failed` right after the first mismatch (fail fast per strand). Proof method: outputs of the hook tables before and after were byte-identical (stdout plus exit code); a mutated copy of `test_block_broad_find.py` with one wrong expectation printed 2 case lines and one failure, exit 1.
- `test_fire_log.py` env override check: copies `src/hooks/` into a temp tree, runs the hook there once with the variable set (must write to the custom file and not to the tree's `src/logs/hook_firing.jsonl`) and once without it (control: must write to the tree's canonical log). A mutant that makes `_fire_log.py` ignore the variable fails the check with two messages.
- The tool-error-writer case of `test_fire_log.py` was deleted: `src.panes.warnings_persist` no longer exists (removed in commit "Block D"), the test crashed with ModuleNotFoundError before the change.
- `test_block_read_worktree.py` was deleted: the hook `src/hooks/block_read_worktree.py` was removed from the tree (commit "remove block_read_worktree.py"), so the test ran a missing script (baseline: 1 of 5 cases passed, exit 2 from python for a missing file).
- `test_block_worker_send_while_working.py`, `test_block_worker_kill_while_working.py`, `test_hook_setup_main_branch_gate.py` ran their loops at import. They now have a workflow function and a `__main__` guard. The "real entrypoint, no resolvable worker status" case of the send test runs with a fake `worker-cli` (exit 1) first on `PATH` and `HOME` set to a temp dir, so it no longer queries the live worker registry.
- `test_bg_task_detection.py`: every case runs against a scratch `_TASKS_BASE` (patched with `unittest.mock.patch.object`), `subprocess` is faked only inside `proc_cache` (not globally), sleeps became deadline polling. Three consecutive runs passed, no leftover `/tmp/bg_probe_*` dirs.
- `run_all.py` runs every `test_*.py` (except `test_header_capture.py`) as one strand via `dev/refactoring/strand_runner.py`: 24 of 24 strands passed in about 2.9 s wall time. Its report `md/run_all.md` is byte-identical between two runs.

## Not fixed, observed

- `test_header_capture.py` needs `mitmproxy` and fails 9 of 13 checks under the project venv against the current `src/proxy/addon.py`. Excluded from `run_all.py`. Unrelated to Phase 3, code drift.
- The fire log variable `MONITOR_CC_TOOL_ERROR_LOG` named in the task no longer exists in `src/`; only `MONITOR_CC_HOOK_FIRING_LOG` is read (`src/hooks/_fire_log.py`).
- In a worktree `src/logs/` does not exist, so hook fire-log writes are silently dropped there; in the main checkout the same tests would have appended to the live log.
