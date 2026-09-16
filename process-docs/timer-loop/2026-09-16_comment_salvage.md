# 2026-09-16 — Comment/docstring salvage for dev/timer-loop/ standards conformance

## Context for whoever picks this up

Milestone: bring `dev/timer-loop/` (5 `.py` files, 907 LOC) into conformance with the project's
three-marker comment standard. Every comment and docstring below was relocated here verbatim
before deletion from the code. Zero `__doc__`/`argparse` hits (`grep -rn "__doc__\|argparse"`), so
all 3 module docstrings found here deleted outright — none were load-bearing.

**Counting-method note:** Python's `tokenize` module flags `test_abort_stamp_scope.py`'s line-1
shebang (`#!/usr/bin/env python3`) as a COMMENT token. A shebang on line 1 is explicitly NOT a
comment per the standard and was left untouched. Excluding it from the tokenize count landed on
exactly 39 real comments across the 5 files, matching the milestone brief's stated measured state.

**`p3_project_scope_incident_probe.py` is DEAD — kept broken, per explicit instruction.** Its own
(now-salvaged) docstring already documented this: `src/hooks/block_timer_pending_bg.py` was
removed in Milestone 2 and `src/proxy/pending_bg_state.py` was removed in Milestone 3. Running it
today: Tests 1-4 run to completion (against a `subprocess.run` call targeting the now-nonexistent
hook file, so they FAIL rather than error — `subprocess.run` on a missing script just returns a
non-zero/wrong exit code), then Test 5 raises `ModuleNotFoundError: No module named
'proxy.pending_bg_state'` at its local `from proxy.pending_bg_state import ...` line, unguarded,
crashing the script before it ever reaches `_write_report` — so the tracked
`md/p3_project_scope_incident_probe_report.md` is never touched by running it, before or after
this edit. Verification for this file compares the PASS/FAIL pattern for tests 1-4 plus the
exception type/message/frame-sequence (file+function names, NOT line numbers — deleting comments
shifts every line below them, so line numbers necessarily differ between the before/after
tracebacks even though nothing behavioral changed) for the Test 5 crash. Both matched exactly.

---

## Salvage from dev/timer-loop/bg_completion_report.py

Was line 261 (above `_build_report`):
```
# Build the markdown report
```

## Salvage from dev/timer-loop/bg_completion_scan.py

Was lines 33-34 (above `_iter_candidate_blocks`):
```
# Extract (shape, text) candidate blocks from one message's content — mirrors the 4-shape walk
# used by every strip_* pass (str / text block / tool_result str / tool_result list[text]).
```

Was lines 56-59 (above `_looks_like_tn_candidate`):
```
# Structural candidate filter for the TN (task-notification) family: block-INITIAL SN paragraph
# (role=user path, the only one observed) OR block-initial bare tag (role=system path per
# message_passes.py comments — defensive, 0 observed in this corpus, still checked so an
# unknown-but-real occurrence would surface here rather than being silently missed).
```

Was lines 71-73 (above `_looks_like_bare_candidate`):
```
# Structural candidate filter for the bare (unwrapped) family strip_bg_completed.py targets —
# block-INITIAL "Background command "" (not contains-anywhere, to exclude prose/dev-report
# mentions the same way the TN filter above does).
```

Was lines 78-79 (above `_normalize_summary`):
```
# Mask the volatile quoted command/description inside a summary string, so distinct real
# commands sharing the same status+exit-code collapse into one wording bucket
```

Was line 84 (above `_is_canonical_timer_command`):
```
# Is the (HTML-unescaped) quoted command the canonical orchestrator timer literal?
```

Was lines 89-92 (above `_scan_file`):
```
# Scan one corpus file for TN-family and bare-family candidates. Dedup key = the exact raw
# <task-notification>...</task-notification> tag-block text (or exact raw bare-notice text) —
# robust to both simple cumulative growth AND the non-monotonic message-count resets observed
# in some worker sessions (compaction), unlike a prev-count positional delta.
```

Was lines 129-130 (above `_record_tn_event`):
```
# Record one deduped genuine TN completion/kill event into the findings dict, keyed by
# (status, exit_code, normalized_summary) — the actual "distinct wording" grouping.
```

Was lines 162-164 (above `_mechanism_verdict`):
```
# Evaluate the real id/output extraction mechanism (payload_helpers.py) against one example
# tag-block, plus the SN/TN fast-path marker gates the proxy uses before it ever reaches
# extraction.
```

## Salvage from dev/timer-loop/p1_scan_bg_completion_wordings.py

Module docstring (was lines 1-17):
```
Milestone 1 — inventory distinct CC background-task COMPLETION/kill notice wordings in the
real recorded corpus, for main (orchestrator) vs worker sessions.

Measurement only: scans src/logs/dual_log/*_original.jsonl for messages that look like a CC
background-task completion notice (the <task-notification> family) or a bare "Background
command "..." completed/failed" notice (the strip_bg_completed.py family), dedups cumulative
dual-log duplication, buckets by (status, exit-code, normalized summary template), and
evaluates the real id-extraction mechanism (payload_helpers._extract_task_notification_task_id)
against each wording. Writes report to dev/timer-loop/md/.

Companion to dev/bg_wakeup_id_line/p1_scan_launch_ack_wordings.py (launch side); this covers
the completion side.

Usage (from project root or worktree root):
    ./venv/bin/python dev/timer-loop/p1_scan_bg_completion_wordings.py [log_dir]
```

Was lines 31-32 (above `MAIN_REPO_ROOT`):
```
# Corpus dir: parameterized, defaults to the main checkout's dual-log dir (untracked data, not
# duplicated into worktrees) — code under test is imported from WORKTREE_ROOT above.
```

## Salvage from dev/timer-loop/p3_project_scope_incident_probe.py

Module docstring (was lines 1-27):
```
SUPERSEDED (Milestone 2, hook family rework — updated Milestone 3): src/hooks/
block_timer_pending_bg.py was removed in Milestone 2 (hook-subprocess sections stopped running);
src/proxy/pending_bg_state.py itself was then removed in Milestone 3, so the writer-side checks
this docstring used to say "still run" no longer do either — the whole script is non-runnable now
(the `from proxy.pending_bg_state import ...` below is a dead import). Left as-is, historical
record of the resolved incident.

P3 — replays the 2026-08-07 ~01:10 cross-project false-block incident: the websearch project's
MAIN session armed its canonical worker timer and was blocked by block_timer_pending_bg.py because
src/logs/pending_bg_tasks.json is one global file and a pending entry (task b4z5fzzao) belonged to
the POSTS project's main session. Drives the REAL hook (src/hooks/block_timer_pending_bg.py) via
subprocess with a seeded state file and a real cwd basename, proving:

  - a foreign-project (posts) pending entry no longer blocks a websearch-cwd timer arm (the
    incident itself, now fixed)
  - a same-project (websearch) pending entry still blocks correctly
  - a legacy entry with no "project" field still blocks every project (backward compat — such
    entries age out via the existing 60min expiry regardless)
  - an expired same-project entry still allows (expiry checked independently of project)

Also verifies the writer side directly: src/proxy/pending_bg_state.py arms a fresh entry with the
project slug derived from PROXY_PROJECT_PATH, through the real ProxyAddon.request() path.

Usage (from project root, real venv — imports mitmproxy via proxy.addon):
    ./venv/bin/python dev/timer-loop/p3_project_scope_incident_probe.py
```

Was lines 63-64 (above `_run_hook`):
```
# Run the real hook via stdin; cwd is caller-controlled (real project-name basename, never inside
# a worktree so the worktree exemption never fires and masks the case under test).
```

Was line 84 (above `test_incident_foreign_project_now_allows`):
```
# Test 1 — the incident itself: a POSTS-project pending entry no longer blocks websearch's timer.
```

Was line 98 (above `test_same_project_still_blocks`):
```
# Test 2 — same-project pending still blocks correctly (the guard still works for its real target).
```

Was line 112 (above `test_legacy_entry_blocks_everyone`):
```
# Test 3 — legacy entry with no "project" field blocks every project (backward compat).
```

Was line 131 (above `test_expired_entry_allows_regardless_of_project`):
```
# Test 4 — an expired entry allows regardless of project (expiry is independent of scoping).
```

Was line 187 (above `test_writer_stamps_project_e2e`):
```
# Test 5 — writer side: real ProxyAddon.request() stamps the project slug from PROXY_PROJECT_PATH.
```

## Salvage from dev/timer-loop/test_abort_stamp_scope.py

Shebang (line 1, stays — not a comment per the standard):
```
#!/usr/bin/env python3
```

Module docstring (was lines 2-17, immediately after the shebang):
```
Integration tests for the abort-stamp scoping fix in src/menubar/bg_timer.py.

Regression guard for the 2026-08-17 live incident (process-docs/timer-loop/): the OLD
_abort_bg_sleep_timers swept 'aborted\n' into every 0-byte *.output file under _TASKS_BASE
globally on any manual abort click — confirmed live via bwbf0nmow.output carrying both 'aborted'
and a genuine later 'workers idle' line, meaning the sweep hit a DIFFERENT, still-running
worker-cli wait's own file. The fix resolves each killed PID's own output file (via a real lsof
-p <pid> -d 1,2 call, BEFORE the kill) and stamps only that file.

Uses REAL subprocesses holding REAL open file handles (mirrors CC's own background-launch fd
shape: stdout+stderr redirected straight to the task .output file) and calls the REAL
_abort_bg_sleep_timers / _resolve_pid_output_file — not a mock. importlib.import_module used for
the src.menubar imports (block_dev_imports_src.py forbids a literal 'from src.' line in dev/).

Run: python3 dev/timer-loop/test_abort_stamp_scope.py
```

Was line 36, trailing on the `_HOLD_DURATION` assignment:
```
_HOLD_DURATION = 20  # seconds — long enough that only the test's own kill/teardown ends it
```
(the comment token itself is `# seconds — long enough that only the test's own kill/teardown ends it`)

Was line 57 (above `_check`):
```
# Print one PASS/FAIL line; append desc to failures on mismatch
```

Was lines 64-67 (above `_spawn_holding_output`):
```
# Spawn a real subprocess with stdout+stderr redirected straight to output_path — the same fd
# shape CC's own background-launch produces for a task .output file, so the real lsof -p <pid>
# -d 1,2 lookup in _resolve_pid_output_file finds it exactly like it would for a genuine
# worker-cli wait/sleep process. Caller owns the returned Popen (kill/wait in a finally block).
```

Was line 71, trailing on a statement (inside `_spawn_holding_output`):
```
    fh.close()  # child already dup'd its own fd 1/2 onto this file; parent's handle is no longer needed
```
(the comment token itself is `# child already dup'd its own fd 1/2 onto this file; parent's handle is no longer needed`)

Was line 83, trailing on a statement (inside `_spawn_test_fixtures`):
```
    time.sleep(0.3)  # let lsof see the just-opened handles
```
(the comment token itself is `# let lsof see the just-opened handles`)

## Salvage from dev/timer-loop/DOCS.md

The pre-rewrite `DOCS.md` carried a trailing `## Gotchas` section that has no place in the
mandated DOCS.md format (Role / Public Interface / Flow / Modules / State only). Cut verbatim:

```
## Gotchas
- `p1_`'s corpus (src/logs/dual_log) is a moving target — counts are a lower bound, not final; a
  rescan can only add deduplicated occurrences, never remove them.
- `p3_project_scope_incident_probe.py` is non-functional on the current tree — the hook and
  state-writer modules it targets do not exist under `src/`. Kept in place as a record of the
  incident it replays, not as a runnable check.
```

This content is preserved here in full; it is not carried into the rewritten DOCS.md (the DEAD
CODE fact for `p3_project_scope_incident_probe.py` is preserved instead in that module's own
**Called by:** bullet, per the mandated format's own "Empty list = DEAD CODE, flag explicitly"
convention).
