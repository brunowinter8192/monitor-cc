# What a coding harness does, and why there are several

Written 2026-09-17, from a survey of four open source harnesses read in full source:
opencode (TypeScript), goose (Rust), plandex (Go), codex (Rust). The survey report with
file paths lives in `dev/harness_survey/md/harness_survey.md`.

## The question this answers

A model answers one request. It has no memory, no file access, no loop, no way to stop
itself. Everything between "the user has a goal" and "the model returns one completion"
is the harness. Claude Code is one such harness. This document names the jobs a harness
performs, so that the choice between harnesses becomes a comparison of how each job is
solved rather than a matter of taste.

## The six jobs

Each of the four harnesses solves all six, or visibly declines to solve one. That is what
makes the list a list rather than an opinion.

### 1. Keep the conversation inside the context window

The model has a hard input limit. A coding session exceeds it within hours. The harness
must decide what to do at the threshold.

All four converge on the same answer and none of them uses a naive sliding window. They
ask the model itself to summarize, then replace history with that summary. They differ
only in what survives verbatim next to the summary:

- opencode keeps whole recent turns up to a token budget, and summarizes everything before.
- codex keeps up to 20k tokens of recent real user messages, newest first.
- goose keeps the immediately preceding user message and hides the rest without deleting it.
- plandex keeps whichever previously stored summary checkpoint happens to fit, and errors
  out loudly when none does.

Thresholds are explicit numbers, not heuristics. goose compacts at 80 percent of the
context window. opencode reserves a 20k buffer below the model's input limit. codex uses
a per-model limit and hard-caps it at the real context window regardless of configuration.

### 2. Keep the provider's prompt cache alive

A cache only reuses an unchanged prefix. Anything that perturbs the front of the payload
invalidates everything behind it. Three of the four spend real engineering effort here.

The most instructive detail found: goose rounds the injected timestamp down to the full
hour and sorts tool metadata, for no reason other than keeping the prefix byte-identical
across sessions. A timestamp that ticks per second would destroy the cache on every request.

codex takes a different route because it targets an API whose caching is session-keyed
rather than breakpoint-based. It keeps a stable cache key per thread and, when the request
shape is unchanged, sends only the continuation over the websocket instead of replaying
the history at all. That is avoidance rather than caching, and it is structurally stronger
than any breakpoint placement.

### 3. Choose a model, possibly more than one

This is the job with the widest spread between the four, and the one most relevant to
anyone limited by a usage quota rather than by capability.

plandex is the outlier worth copying. It has no concept of "the model for this session".
It has a ModelPack: a named role per job (Planner, Coder, Builder, WholeFileBuilder,
Summarizer, Namer, CommitMsg, ExecStatus), each pinned to its own model at its own
provider, each with its own fallback chain for the large-context case, the error case and
the needs-a-stronger-model case.

The others sit between:
- opencode picks a model per agent, plus a separate cheap "small model" for auxiliary
  calls like title generation.
- goose runs one provider per session but lets a subagent take a wholly different provider.
- codex varies model and reasoning effort per agent role, but the provider is per config
  profile, so a different vendor per subagent means running separate profiles.

### 4. Delegate work to subagents

Three of the four let the model itself decide to spawn a helper. plandex does not, and
that absence is deliberate: it substitutes a fixed multi-role pipeline plus one goroutine
per file during the build stage.

The interesting axis is what the child inherits. opencode and goose both seed the child
with only the task text and nothing of the parent conversation. codex makes it a parameter:
none, the last N turns, or the full parent history forked into the child.

codex is also the only one with real messaging primitives rather than a blocking call.
It can wait on an agent, send it a follow-up, interrupt it, list the active ones, resume
and close them.

### 5. Get project rules into the prompt

The filesystem convention is AGENTS.md, with CLAUDE.md as the older sibling. Three of the
four walk the directory tree and concatenate what they find. goose exposes an explicit
three-tier hierarchy of global, project and per-subdirectory. opencode adds a dynamic tier
that injects a directory's rules the moment a file in it is read.

codex does something structurally different that nobody else does. It splits the material
across two message roles: config and plugin policy goes into a "developer" role message,
project AGENTS.md content goes into a "user" role message. Everyone else flattens it all
into one system prompt string.

plandex has no rule-file discovery at all. Rules are the user's prompt and explicitly
loaded context files, nothing more.

### 6. Show what it cost

plandex is the most product-grade here, with a persisted usage ledger behind a dedicated
`plandex usage` command, filterable by session, day, month and plan.

codex shows credits and an estimated dollar figure broken down by model, reasoning effort
and speed tier, and separately feeds a structured analytics stream that records compaction
attempts with tokens before and after.

opencode and goose both compute and persist per-message cost but expose no dedicated
reporting command.

## Why there are several harnesses

The six jobs have no single correct solution, and the right answer depends on what the
harness is optimizing for.

- A harness optimizing for provider breadth accumulates a large provider registry and
  makes model choice per agent. That is opencode.
- A harness optimizing for predictable cost per task fixes the pipeline, pins a model per
  role, and refuses to let the model spawn anything. That is plandex.
- A harness optimizing for extensibility puts everything behind an extension protocol and
  lets a recipe override provider, model and tools per subagent. That is goose.
- A harness optimizing for one vendor's API can use mechanisms nobody else can, such as
  transport-level incremental requests, and spends its complexity budget on a real
  multi-agent runtime instead. That is codex.

Claude Code sits in the last category. The cost of that position is that its choices are
not configurable from outside, which is why a proxy in front of it exists in this project
at all.

## What to take from this

The finding worth acting on is the ModelPack idea, because it decouples "which model" from
"which session". A role that only names a commit message or writes a summary does not need
the same model as a role that plans a refactor. Under a usage quota that difference is not
an optimization, it is the difference between finishing the week and not.

The open question that this survey does not answer is where exactly the cheap model can
take over without degrading the result. None of the four harnesses justifies its role
assignment with a measurement. They assert it.
