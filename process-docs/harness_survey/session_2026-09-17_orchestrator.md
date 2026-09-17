# Harness survey session, orchestrator notes

Written 2026-09-17. This file records what happened in the session that produced
`dev/harness_survey/md/harness_survey.md` and `what_a_harness_does.md` in this area,
including four wrong assumptions that were corrected by the user and should not be
repeated.

## Four claims that were wrong

These were asserted in chat, sourced from Reddit posts and from a subagent-cost analysis,
and corrected by the user on the spot. Anyone reaching for the same sources will hit the
same errors.

**Wrong: enabling `context_management.clear_tool_uses` in `proxy_rules.json` is free
usage relief.**
It is not. Clearing old tool uses rewrites the message array. The message array is
inside the cached prefix, so every rewrite forces a full cache rebuild. On paper it
removes stale tool output, in practice it trades a token saving for a cache miss on every
request that triggers it. The switch is off in `proxy_rules.json` deliberately.

**Wrong: subagents in this project start with roughly 97 percent boilerplate.**
That number comes from a Reddit measurement of stock Claude Code subagents. It does not
transfer here. This project's proxy strips the boilerplate before the request leaves the
machine, so a worker starts with close to only what the main agent gave it.

**Wrong: the shared prefix cache lives for five minutes.**
It is one hour.

**Wrong: a proxy is a place to measure whether a rule works.**
A proxy sees bytes. It can show that a rule changed the payload. It cannot show that the
change improved the agent's behaviour. Any claim of the form "measure rule effectiveness
in the proxy" is unfounded.

## The spawn that silently did nothing

The first `worker-cli spawn` for the harness worker produced a tmux session, a worktree
and a registry entry, and then nothing. `worker-cli list` reported `idle`, which reads
like "finished" but here meant "never started".

The tell is `worker-cli response <name>` failing with `no session JSONL found`. A worker
that has produced no session JSONL has never run a turn. `worker-cli capture` confirmed
it: the full prompt text was sitting in the input field, unsent, with the model indicator
below it.

The fix was `worker-cli kill` followed by a fresh `worker-cli spawn` with the same prompt
file, which worked on the second attempt. No cause was identified. If this recurs, check
`response` before assuming an idle worker is a finished worker.

Note also that this first spawn was issued without a following `worker-cli wait`, which
is what let the failure go unnoticed until the user asked about it.

## What the harness worker was given

The worker has no internet access by design, so the four harnesses were shallow-cloned
to `/tmp/harnesses/` first and the prompt pointed at those paths. Sizes after
`git clone --depth 1`: goose 659M, opencode 220M, codex 116M, plandex 60M.

Two of the four clones exceeded a two minute Bash timeout when run as one chained loop.
Cloning them in two batches worked. The clones are in `/tmp` and will not survive a
reboot; re-clone rather than expecting them to be there.

The prompt asked six fixed questions per harness and explicitly forbade summarizing the
README, requiring instead that the worker walk from each entry point to the code that
builds the request payload. It also required a file path on every claim and an explicit
mark on every inference. That instruction is what makes the resulting report checkable,
and it is worth repeating for any future survey of foreign code.

## Where the useful material came from

The reddit collection (`reddit-cli-posts`) produced the concrete provider options people
actually use when a quota runs out, and the number that stuck was a user reporting the
same task at 1.70 dollars on Qwen against 8 dollars on a frontier model. The GLM coding
plan pricing the user shared separately: Lite at 12.60 dollars a month billed yearly with
10.000 credits a week, Pro at 56, Max at 117.60, with Claude Code named as a supported
tool.

The github issues collection was searched for agent search strategy and returned mostly
noise from gpt-researcher stack traces. The high-value GitHub material came from reading
repository files directly, not from indexed issues. For a question about how something is
built, go to the source tree; the issue tracker answers questions about how something
breaks.

## Open thread

The user's next intended step is offloading work to Haiku, and the open question is where
that is safe. The harness survey shows all four harnesses assign models per role by
assertion, without measurement. That question is unanswered and is the natural successor
to this area.
