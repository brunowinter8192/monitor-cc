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

`block_unauthorized_background.py`'s initial version was left untouched, on the assumption that
PreToolUse hooks are AND-of-permission across the whole registered set — any hook that exits 2
denies the call regardless of what any other hook returns on the same event — so the new
isolation hook's block would win over the general hook's demotion with no conflict. That
assumption was corrected the same session (see "Correction" below) — the general hook was
changed after all, and the final design does not depend on precedence at all.

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

## Correction: precedence between a block and a rewrite is undocumented — design changed to not need it

The first version of this entry shipped with `block_unauthorized_background.py` untouched, on
the claim that PreToolUse hooks are AND-of-permission — any hook exiting 2 denies the call no
matter what another hook returns — so the new isolation hook's block would always win over the
general hook's silent demotion for the same input, with no real conflict.

That claim was checked, not just repeated, before this correction: `hook_taxonomy.md`,
`2026-05-22_hook_principle_block_vs_allow.md`, `2026-05-22_hook_api_auto_rewrite_works.md`, and a
full-tree grep of `process-docs/` for precedence/conflict language turned up nothing. This repo
documents that both mechanisms exist (block via exit 2 + stderr, rewrite via exit 0 +
`updatedInput`) but nowhere documents what happens when two hooks on the same `PreToolUse` event
disagree on the same call. **The precedence question is unresolved in this repo's own
documentation as of 2026-09-17.**

That matters here specifically, not generically: the two hooks are not disjoint on this command.
`block_unauthorized_background.py` rewrites (demotes to foreground) precisely when a
`run_in_background=true` command is not canonical, and for `worker-cli wait`, non-canonical means
chained or `cd`-prefixed — exactly the shapes `block_worker_wait_isolated.py` blocks. Every
chained/`cd`-prefixed wait therefore triggered both hooks at once, one wanting to block, one
wanting to silently demote. If block wins, the fix works. If the rewrite wins (or merges, or
whichever result a harness applies last wins), the call gets silently demoted exactly as it did
before this milestone, the orchestrator learns nothing, and the fix would look shipped while
changing nothing.

### Fix — make the general hook stop having an opinion on this command

Rather than resolve or rely on precedence, `block_unauthorized_background.py` was changed to
exclude `worker-cli wait` from its rewrite path entirely, so it is no longer a second, possibly-
conflicting source of truth for this command:

```python
_WAIT_MENTION_RE = re.compile(r'\bworker-cli\s+wait\b')

def _mentions_worker_wait(command: str) -> bool:
    return bool(_WAIT_MENTION_RE.search(_strip_non_shell_active(command)))
```

`if _is_canonical(command) or _mentions_worker_wait(command): sys.exit(0)` — added as an OR onto
the existing canonical check, one new import (`_shell_strip`, already used by both new hooks, for
the same quoted-mention-safety reason), one new constant, one new function, one new clause. The
shell-strip guard is required here, not decorative: without it, an unrelated dangerous command
that merely quotes the phrase "worker-cli wait" in an argument (e.g. an `echo` or a `worker-cli
send` message body chained with something else) would wrongly skip the general hook's demotion
for that unrelated command. Verified as its own case (see below).

Now the two hooks are no longer in conflict on any input: `block_unauthorized_background.py`
never rewrites a `worker-cli wait`-mentioning command (canonical or not), so there is nothing
left for a precedence question to resolve. The outcome for a chained/`cd`-prefixed wait is the
same regardless of which order a harness evaluates the three hooks in, because only one of them
(`block_worker_wait_isolated.py`) ever produces a verdict on it.

Verified live, both conflict shapes, all three hooks run independently against the identical
payload:

```
cd /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/websearch; worker-cli wait
  (run_in_background: true)

  block_unauthorized_background.py  → exit 0, no output (no opinion)
  block_worker_wait_isolated.py     → exit 2, isolation message
  block_worker_wait_foreground.py   → exit 0, no output (bg flag is true)

worker-cli wait && rag-cli index docs
  (run_in_background: true)

  block_unauthorized_background.py  → exit 0, no output (no opinion)
  block_worker_wait_isolated.py     → exit 2, isolation message
```

### Cost of the fix — one test case changed on purpose, two added

`test_block_unauthorized_background.py`'s case `"worker-cli wait && rag-cli index — chained,
tail-guard rejects it FORCE"` asserted `rewritten_bg=False` (the hook used to demote this). That
assertion is now the literal bug being removed, so its expectation was updated to `None` (no
output) rather than left to fail — 13 of the 14 original cases needed no change at all, since
`\bworker-cli\s+wait\b` only matches when the word `wait` is genuinely present with a boundary on
both sides (`worker-cli waitfoo` still doesn't match, so that FORCE case is untouched). Two cases
were added: a `cd`-prefixed wait confirming the same no-opinion outcome, and
`echo "worker-cli wait" && ./venv/bin/python script.py` confirming the shell-strip guard — a
quoted mention does not exempt the unrelated `./venv/bin/python` command riding along with it,
which still gets demoted (`FORCE`, `rewritten_bg=False`) exactly as before. 16/16 pass.

### Precedence itself: still unresolved, deliberately not needed, not established empirically

This design does not depend on the answer, so it was not chased down further. An attempt to
establish it empirically (arm both a blocking and a rewriting hook against a real Claude Code
tool call and observe which one wins) was considered but not carried out in this session:
`hook_setup.py` refuses to run from inside a worktree by design (its own guard), and hooks are
registered machine-wide in `~/.claude/settings.json` — actually registering a test hook pair
against the live global settings file from a worker session is out of scope for a worker
(touches machine state outside this worktree, and the worktree-only scope exists precisely so a
worker's own background-sleep habits don't get promoted the way an orchestrator's do — see
`rewrite_background_sleep.py`'s worktree exemption). Left for whoever next needs the real answer,
from a main session with a real terminal, not from here. If the answer ever turns out to matter
for a future hook pair with a similarly overlapping signature, this entry is the place that
established it should be checked, not assumed.

## Files changed

- `src/hooks/block_worker_wait_isolated.py` — new.
- `src/hooks/block_worker_wait_foreground.py` — new.
- `src/hooks/block_unauthorized_background.py` — `worker-cli wait` excluded from the rewrite path
  entirely (see Correction above); one new import, one new constant, one new function, one new
  clause; every other command's behavior unchanged (verified: 13 of 14 pre-existing test cases
  pass with unmodified expectations).
- `src/hooks/hook_setup.py` — the two new hooks registered in `_HOOK_SCRIPTS`, next to
  `block_worker_send_background.py`.
- `src/hooks/DOCS.md` — two new module entries; `block_unauthorized_background.py`'s purpose/
  writes lines updated for the exclusion; `_shell_strip.py`'s "Called by" list gained
  `block_unauthorized_background.py` plus the two new hooks; `_fire_log.py`'s active-caller count
  updated (30 → 32).
- `dev/hook_smoke/test_block_worker_wait_isolated.py` — new, 14 cases, all pass.
- `dev/hook_smoke/test_block_worker_wait_foreground.py` — new, 9 cases, all pass.
- `dev/hook_smoke/test_block_unauthorized_background.py` — 1 case's expectation updated on
  purpose (see Correction above), 2 cases added; 16/16 pass.
- `dev/hook_smoke/DOCS.md` — two new test entries; `test_block_unauthorized_background.py`'s
  entry updated for the new case count and behavior.
- Re-ran `test_rewrite_background_sleep.py` (14/14), `test_block_worker_send_while_working.py`
  (12/12), and `test_block_worker_kill_while_working.py` (13/13) unmodified after the change — no
  regression in any sibling worker-cli-guard hook's own suite.

## Note for a future reader of `hook_taxonomy.md`

That file states "22 PreToolUse + 1 PostToolUse" for the tool-hooks count as of its own writing.
This entry adds 2 more PreToolUse hooks, so that count is stale as of 2026-09-17. Not corrected
there — per this repo's process-docs rule, only the author of a process-docs file may edit it;
this note exists so the next reader isn't misled by the stale number without having to
rediscover it.
