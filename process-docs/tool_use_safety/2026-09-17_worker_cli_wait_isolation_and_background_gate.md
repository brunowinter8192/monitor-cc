# worker-cli wait: isolation + background-required gates (2026-09-17)

## Incident

An orchestrator session armed `worker-cli wait` repeatedly, every call written as

    cd /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/websearch; worker-cli wait

with `run_in_background: true`. `block_unauthorized_background.py`'s `_WAIT_FORM` regex is
anchored at the start of the string (`^\s*worker-cli\s+wait\b[^;&|\n]*$`), so a `cd`-prefixed
command never matches it. The hook's fallback for a non-canonical background command is a silent
demotion to `run_in_background: false` — no message, no signal, just a flipped flag in the
`updatedInput` JSON. Every wait in the session ran in the foreground as a result. One call
blocked the orchestrator 68s; a second blocked it ~2min before CC auto-backgrounded it, then it
polled for 436s in a state it could never exit and had to be killed. The orchestrator never
learned anything was wrong across the whole session — it only found out when the user pointed at
the tmux bar.

Live measurement that pinned the cause, run against the hook as it stood before this entry:

    INPUT: worker-cli wait
      (no output — allowed through, stays in background)

    INPUT: cd /tmp; worker-cli wait
      {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
       "updatedInput": {"command": "cd /tmp; worker-cli wait", "run_in_background": false}}}

    INPUT: cd /tmp && worker-cli wait
      {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
       "updatedInput": {"command": "cd /tmp && worker-cli wait", "run_in_background": false}}}

Separately, a foreground `worker-cli wait` (no `run_in_background` at all) was never policed by
any hook — `block_unauthorized_background.py` only inspects its input when
`tool_input.run_in_background` is `True`, so it early-exits before ever looking at the command.

## Decision: two new hooks, split by signature, not by target command

Two conditions were requested: "must run alone" and "must run with `run_in_background: true`".
Both concern the same command, but they check unrelated signatures — one is pure command-shape
(chaining/`cd`-prefix in the text), the other is pure flag-state. Kept as two files rather than
one, following the precedent already in this directory: `block_worker_send_background.py`
(flag-based) and `block_worker_send_while_working.py` (live-status-based) are two separate files
governing the same `worker-cli send` subcommand, split exactly because their detection surfaces
differ. `A1_use_case_specificity.md` backs this directly — pattern-match the exact anti-pattern
signature, one condition per hook, never widen an existing general mechanism to cover a new case.

`block_unauthorized_background.py` was left untouched. Its silent-demotion path for every other
command is still correct; for `worker-cli wait` specifically it is now superseded in practice
(not removed) because PreToolUse hooks are AND-of-permission across the whole registered set —
any hook that exits 2 denies the call regardless of what any other hook returns on the same
event. The new isolation hook below now blocks the exact shape `_WAIT_FORM` used to silently
demote, before the demotion is ever reached. No hook ordering dependency, no conflict.

### `block_worker_wait_isolated.py`

`_WAIT_MENTION_RE = r'\bworker-cli\s+wait\b'` gates whether the hook cares about the command at
all. `_WAIT_CANONICAL_RE = r'^\s*worker-cli\s+wait\b[^;&|\n]*$'` — same shape as the old
`_WAIT_FORM`, reused deliberately, but the failure branch now blocks (exit 2 + message) instead
of feeding a silent rewrite. Fires unconditionally on `run_in_background` (both foreground and
background chained/`cd`-prefixed forms are wrong) whenever mention matches but canonical
(anchored, whole-string) doesn't.

Deliberately **no `cd` exemption**, unlike `block_rag_cli_index_isolated.py`. `worker-cli wait`
already accepts the target project directory as a positional argument
(`worker-cli wait /path/to/project --timeout 600`, confirmed canonical and tested), so a
`cd`-then-wait chain is always correctable to the argument form — there is no legitimate reason
to `cd` first, unlike `rag-cli index`, which has no such argument.

Deliberately **no subshell-substitution detection** (`$(...)`, backticks), unlike the same
rag-index hook. That anti-pattern has never been observed on `worker-cli wait`; the milestone
instructions were explicit not to invent unobserved cases, and `_WAIT_CANONICAL_RE`'s char-class
exclusion (`[^;&|\n]*$`) only defends against `;`/`&`/`|`/newline separators, not command
substitution embedded in an argument. If this is ever observed, it is a new, separately-evidenced
case, not a reason to add speculative regex now.

### `block_worker_wait_foreground.py`

Same mention gate, then blocks when `run_in_background` is not `True` (covers both explicit
`false` and the key missing entirely). This is the flag-mirror of
`block_worker_send_background.py` (which blocks the opposite direction — `send` backgrounded)
and closes the exact policing gap named above.

## False-positive risk: quoted mentions, verified with real shapes

The highest risk by construction: orchestrators routinely discuss `worker-cli wait` by name
inside `worker-cli send` message bodies and inside heredoc-written prompt files, and both hooks
search the raw command text for the phrase. Both hooks run `_strip_non_shell_active` first
(same protection `block_worker_send_background.py` already uses, same FP class documented in
`2026-05-22_hook_principle_block_vs_allow.md`), which blanks quoted-string and heredoc-body
regions to same-length spaces before either regex runs.

Verified live, full un-shortened shapes, both hooks, both allowed through cleanly (exit 0, no
output):

```
worker-cli send orchestrator "Arm worker-cli wait after every dispatch. Do not run worker-cli
wait in the foreground, and never chain it with cd; worker-cli wait — always issue it alone with
run_in_background: true."
```

```
cat <<'EOF' > /tmp/mchook_verify_prompt.md
## Wake-up Loop

After every dispatch, arm the wait: `worker-cli wait`.
Never run `cd /path; worker-cli wait` — pass the project path as an argument instead.
EOF
```

The heredoc case is the harder one: the body contains the exact incident shape
(`cd /path; worker-cli wait`) as literal text, and both regexes still see it as blanked space,
not live shell text — proof the strip, not luck, is what's protecting these hooks.

The dev-suite equivalents (`test_block_worker_wait_isolated.py`,
`test_block_worker_wait_foreground.py`) carry one case each of the same class as a permanent
regression guard; this section exists because a suite case proves the regex, not the shell-strip
integration end-to-end — see the live shapes above for that.

## What this closes off: foreground observation of `worker-cli wait` itself

Blocking every foreground bare-command Bash tool call means an agent can no longer bare-invoke
`worker-cli wait` as a raw foreground Bash tool call to watch it behave directly — the exact
thing the `2026-09-02_wait_transition_gate.md` verification did
(`worker-cli wait --timeout 20` against a real project, reading the trace as it ran).

Checked rather than assumed: does this also break `dev/worker_wait/test_worker_wait.sh` in
iterative-dev, which runs `bash "$BIN" wait ...` dozens of times per run? No. That script invokes
`worker-cli wait` as a subprocess spawned from *inside* the shell-script file — the file itself
is what an agent hands to the Bash tool (`bash dev/worker_wait/test_worker_wait.sh`), and a
PreToolUse hook only ever inspects that one top-level command string. It never sees a subprocess
call a shell script makes internally; that call never crosses the Claude-Code-tool-call boundary
at all. Grepped monitor-cc itself for the same shape — no `.sh` test script here invokes
`worker-cli wait` as a nested subprocess today, so nothing in this repo's own suite is affected
either way; this reasoning is what protects the iterative-dev suite specifically, and it
generalizes to any script-wrapped invocation.

That is also the answer for an agent that genuinely needs to observe `worker-cli wait` live in
the foreground (as `2026-09-02`'s verification did): put the invocation inside a small script
file or a quoted `bash -c "..."` wrapper and hand *that* to the Bash tool, rather than bare-
invoking `worker-cli wait` as the literal top-level command. Neither hook fires on it — the
script-file form because the mention never appears in the top-level command text at all, the
`bash -c "..."` form because `_strip_non_shell_active` blanks the quoted argument before the
mention regex runs — and the command still executes for real, still foreground, still directly
observable via the Bash tool's own stdout. This is not a fallback either hook implements; it is
a pre-existing property of how PreToolUse hooks see only the outermost command text, the same
property that already lets `test_worker_wait.sh` run unaffected.

## Files changed

- `src/hooks/block_worker_wait_isolated.py` — new.
- `src/hooks/block_worker_wait_foreground.py` — new.
- `src/hooks/hook_setup.py` — both registered in `_HOOK_SCRIPTS`, next to
  `block_worker_send_background.py`.
- `src/hooks/DOCS.md` — two new module entries; `_shell_strip.py` and `_fire_log.py` "Called by"
  lists and counts updated (30 → 32 active `_fire_log` callers).
- `dev/hook_smoke/test_block_worker_wait_isolated.py` — new, 14 cases, all pass.
- `dev/hook_smoke/test_block_worker_wait_foreground.py` — new, 9 cases, all pass.
- `dev/hook_smoke/DOCS.md` — two new test entries.
- Re-ran `test_block_unauthorized_background.py` (14/14) and `test_rewrite_background_sleep.py`
  (14/14) unmodified after adding the new hooks — no regression, both existing suites still pass
  exactly as before.

## Note for a future reader of `hook_taxonomy.md`

That file states "22 PreToolUse + 1 PostToolUse" for the tool-hooks count as of its own writing.
This entry adds 2 more PreToolUse hooks, so that count is stale as of 2026-09-17. Not corrected
there — per this repo's process-docs rule, only the author of a process-docs file may edit it;
this note exists so the next reader isn't misled by the stale number without having to
rediscover it.
