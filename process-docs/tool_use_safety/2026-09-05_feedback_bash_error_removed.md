# Removal of feedback_bash_error (2026-09-05)

## Why

`feedback_bash_error.py` (PostToolUseFailure hook, see
`2026-08-29_posttooluse_failure_feedback_hook.md` for how it was built and verified) fed a
retry-discipline instruction back to the model as `hookSpecificOutput.additionalContext` after a
failed Bash call. CC 2.1.258 changed how that message arrives on the wire: it now comes in as a
`role=system` message, which the proxy's `_apply_role_system_strip`
(`src/proxy/message_passes.py`) reduces to `"."` before the payload reaches the model — the same
blanket nuke that strips CC's own noise messages. The hook's output never reached the model from
that CC version onward.

The user decided on removal rather than exempting the message from the strip, for a reason
independent of the delivery break: the hook's trigger is the Bash call's exit code, and under
the `;`-chaining rule (`shared-rules/global/tool-use.md`) that code is only the LAST segment's.
A chain whose middle segment failed comes back green and never fires the hook; a chain whose
last segment is a harmless "no" (grep with no match, a probe on a missing path) comes back red
and fires it for nothing. The session's own log showed this: three fires on 2026-09-05, all on
multi-segment probes with a guessed path, none on a genuine retry-worthy failure. With the exit
code judged uninformative for the model — each segment is judged by its output, per that rule —
a hook keyed on it had no reliable signal left to act on, regardless of whether its message
reached the model. A Reddit survey the same day (r/ClaudeCode, r/codex, r/ClaudeAI) found no
discussion of post-failure feedback hooks at all; the only exit-code threads were a `/tmp`-full
case (exit 1 with no output, the one case where the code is the sole signal) and a destructive
command hidden at the end of a long `&&` chain.

## What changed

- `src/hooks/feedback_bash_error.py` deleted.
- `src/hooks/hook_setup.py`: its `_HOOK_SCRIPTS` entry (`("feedback_bash_error.py", "Bash",
  "PostToolUseFailure")`) and the 3-line comment above the list explaining why its
  "untouched on success" guarantee is structural (tied to `PostToolUseFailure` never firing on a
  success payload) were removed. The general `(script, matcher, event)` 3-tuple registration
  mechanism this hook was the first user of stays in the code — `decide_entries()`,
  `_unpack_entry()`, and `_sweep_stale_hooks()`'s iterate-every-event-key behavior are all still
  live and untouched, ready for a future non-PreToolUse hook.
- `src/hooks/DOCS.md`: the module entry removed; `hook_setup.py`'s own entry's "Event dimension"
  paragraph kept (it documents a mechanism that still exists) but its closing clause — a
  historical justification naming "dead PostToolUseFailure paths" — was generalized since it no
  longer describes anything currently registered.
- `dev/hook_smoke/test_feedback_bash_error.py` deleted — it existed solely to smoke-test this
  hook.
- `dev/hook_smoke/DOCS.md`: its module entry removed (it was the last entry in the file).

## What was deliberately left alone

- **The "Feedback hooks" pattern-class bullet** in `src/hooks/DOCS.md`'s Role section
  (`feedback_*.py`, PostToolUseFailure) — describes a naming/behavior CONVENTION for a hook class,
  not a reference to this specific file. Left in place; it documents the pattern for a future
  feedback-style hook, the same way the `rewrite_*` class description would stay even if every
  current rewrite hook were temporarily removed.
- **Two general Gotchas** in the same file (the measured `PostToolUse`-vs-`PostToolUseFailure`
  event-firing behavior, and the three-channel feedback-surfacing measurement) — both are framed
  explicitly as reusable knowledge for "any future post-hoc hook" and name neither the hook nor
  its filename. Kept as standing architecture knowledge.
- **`_fire_log.py`** — its shared `log_fire()` function still recognizes `decision="feedback"` as
  one of its enum values (kept alongside `"block"`/`"rewrite"`/`"ui-notice"`), and its own DOCS.md
  entry still documents that value accurately. This is now a dead branch with no current caller,
  but the milestone's scope explicitly excluded touching any other file in `src/hooks/` beyond the
  hook itself and `hook_setup.py`'s specific references — removing it would have been an
  unrequested code change to a shared module every other hook also depends on.
- This area's own 2026-08-29 PostToolUse failure-feedback hook entry — write-once, not
  edited; its historical build/verification record stands regardless of the hook's later removal.

## Verification

`grep -rn "feedback_bash_error" src dev` (both directories, all file types) returned zero hits
after the change. Ran the full `dev/hook_smoke/` suite (31 scripts): 26 passed cleanly at their
documented counts (`test_hook_setup_main_branch_gate.py` 10/10, `test_block_gh_cli_chained.py`
34/34, etc.). 5 scripts exited non-zero (`test_bg_task_detection.py`, `test_block_chained_sleep.py`,
`test_block_read_worktree.py`, `test_fire_log.py`, `test_header_capture.py`) — confirmed via
`git stash`/re-run to fail identically before this change too (missing `mitmproxy` and
`src.panes.warnings_persist` packages in this worktree's venv, a menubar relative-import issue
when invoked directly, and two tests whose behavior depends on cwd/worktree context or a disabled
hook file), unrelated to this removal.

`hook_setup.py`'s own `.githooks/post-commit` fired automatically on the commit removing the hook
files and correctly refused to run from inside a worktree (`_guard_not_worktree()`, exit 2,
swallowed by the git hook) — `~/.claude/settings.json` was not touched from this worktree, per
the milestone's explicit instruction. `_sweep_stale_hooks()`'s existing `os.path.exists()` check
on every registered `python3 <path>` will remove the stale `PostToolUseFailure` entry the next
time `hook_setup.py` runs for real from the main repo root.
