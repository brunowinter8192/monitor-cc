# Survey of opencode, goose, plandex, codex — process notes (2026-09-17)

Opening entry of this area. Subject: a reading-only survey session that produced
`dev/harness_survey/md/harness_survey.md`, comparing four open source coding harnesses
(opencode, goose, plandex, codex) on context management, prompt caching, multi-provider
support, sub-agents, rule injection, and cost observability. No source code was touched;
the harnesses live at `/tmp/harnesses/{opencode,goose,plandex,codex}` (shallow clones,
read-only, not part of this repo).

## What a follow-up agent needs before starting

The material is enormous (opencode alone has >13k-line generated SDK files; codex's
`core/src` is 63k+ LOC across ~90 files, much of it tests). The task instructions say
"read whole files, never grep-and-move-on," which is right for understanding one function,
but at this scale it is not feasible to read every file in every harness cover to cover
within a session. What actually worked was:

1. `find <dir> -name "*.ext" | xargs wc -l | sort -rn` to find the largest files in a
   crate/package, since size correlates with "this is where the real logic lives" far
   better than directory names do (e.g. `agents/platform_extensions/summon.rs` at 4434
   lines turned out to be goose's entire sub-agent/delegate implementation — the name
   gives no hint of that).
2. One targeted `grep -rn` pass per topic (`cache_control`, `subagent`, `DEFAULT_.*THRESHOLD`,
   `model_providers`) to find the 2-4 files that actually matter for a given question,
   *then* reading those files whole with `Read`, not partially. The grep is a router, not
   a substitute for reading — every claim in the final report traces to a full-file read of
   the cited function, not to the grep hit itself.
3. Reading in the order entry-point → request-builder, as the task instructed. In practice
   the fastest path to "how does this harness build a request" was: find the compaction/
   context file (usually named `compact*`, `context_mgmt`, `tell_context`), then the
   provider/transform file, then the file that finally assembles `messages`/`system` before
   the network call (`request.ts`, `client.rs`, `client.go`). That third file is where
   ordering/placement questions (Q5's "where in the message structure do rules land") get
   answered — it is not answerable from the rules-loading file alone.

## Concrete surprises worth reusing

These are the "genuinely surprised me" findings the deliverable calls out; a follow-up
agent working on cache-hit-rate tuning for `monitor-cc`'s own proxy/pipeline should look at
these first, they are directly transferable ideas:

- **goose rounds its injected "current date/time" down to the hour** specifically to keep
  the system prompt prefix byte-identical across a session and across sessions within the
  same hour, explicitly for cache-hit purposes
  (`crates/goose/src/agents/prompt_manager.rs:180-190`, comment on line 186). It also sorts
  extension/tool metadata by name before rendering, same motivation (lines 111-112). This
  is the single most reusable idea in the whole survey — any harness/proxy injecting a
  timestamp or non-deterministically-ordered metadata into a cached prefix is paying for
  it in cache misses without realizing it.
- **codex does not use Anthropic-style `cache_control` breakpoints at all.** It relies
  entirely on a stable `prompt_cache_key` (derived from thread/session id,
  `codex-rs/core/src/client.rs:541-553`) plus deciding, per request, whether the new
  request is "shape-identical" to the previous one
  (`responses_request_properties_match`, lines 329-384) in order to send an *incremental*
  websocket delta instead of replaying full history. This is architecturally a different
  (and arguably stronger) caching strategy than the "tag the last N blocks" approach the
  other three converge on — worth remembering if `monitor-cc` ever needs to reason about
  OpenAI-Responses-API cache behavior specifically, since it does not map onto the
  Anthropic mental model of manual breakpoints at all.
- **plandex has no sub-agent mechanism and no AGENTS.md-style rule file discovery.** Both
  are genuine absences, not omissions in my reading — I grepped specifically for
  `subagent|delegate|orchestrator` and for `CustomInstructions|ProjectInstructions|plandex.md`
  across all of `app/` and got no relevant hits either time. Plandex substitutes a fixed
  per-file-goroutine parallelism at the build stage (`app/server/model/plan/build_exec.go:30-93`)
  for sub-agents, and pure user-supplied context/prompt text for rules. This is the clearest
  place in the whole survey where "absence is a finding" (per the task's explicit
  instruction) applied.
- **plandex's `ModelPack` (`app/shared/ai_models_data_models.go:716-828`,
  `app/shared/ai_models_packs.go`) assigns a distinct model+provider to each of 8 named
  roles** (Planner, Coder, Builder, WholeFileBuilder, Summarizer, Namer, CommitMsg,
  ExecStatus), each with its own fallback chain (large-context / error / strong-model). This
  is a materially more explicit multi-model design than opencode's or goose's "per-agent
  model override" — it is the harness's *primary* way of choosing models, not an escape
  hatch. Worth remembering as a reference pattern if `monitor-cc` ever wants to formalize
  "which of our own pipeline stages should use which model."
- **codex's sub-agent system (`spawn_agent`, `codex-rs/core/src/tools/handlers/multi_agents_v2/`)
  is the only one of the four with true cross-agent messaging primitives** (wait /
  send-message / interrupt / list / resume / close, each a separate tool) instead of a
  single blocking "call and get text back." It also lets the calling model choose how much
  parent history to fork into the child (`none`/`all`/last-N-turns via `fork_turns`,
  `spawn.rs:270-317`) — the other three hardcode "child gets only the task text, never
  parent history."

## Where the report's claims could be wrong or thin

Flagging these so a follow-up doesn't have to re-discover them the hard way:

- **opencode §1.4 (sub-agent parallelism)**: I did *not* find and read the exact code that
  proves multiple `task` tool calls in one assistant turn execute concurrently — I inferred
  it from the existence of `Effect.forEach`/concurrency patterns used elsewhere in the
  codebase and from the explicit `background` mode's existence implying the *foreground*
  case is otherwise blocking-per-call. The report already marks this "opportunistic rather
  than orchestrated" and doesn't overclaim, but `packages/opencode/src/session/tools.ts`
  (590 lines) was not read in full and would be the file to check to firm this up.
- **codex §4.3 (multi-provider)**: I inferred (explicitly marked "Inference" in the report)
  that a genuinely different *vendor* per sub-agent would require separate Codex config
  profiles, based on `model_providers` being a per-`Config` map rather than a per-role
  field. I did not find code that actively *forbids* pointing `spawn_agent`'s `model`
  argument at a model belonging to a different `ModelProviderInfo` than the parent's active
  provider — the models_manager (`codex_models_manager`) lookup in
  `multi_agents_v2/spawn.rs:176-184` was not traced deep enough to be certain either way.
  If this distinction matters later, read `codex-rs/models-manager/` (not explored at all
  in this session).
- **goose's `summon.rs` is 4434 lines and I read maybe 300 of them** (the
  `resolve_model_config`/`resolve_provider`/`build_task_config` region around lines
  1650-1880, plus the `delegate` tool's description string around lines 779-796). The rest
  of the file almost certainly contains more delegate-lifecycle logic (the file also
  defines `SummonClient` at line 577, not explored) — treat §2.4's "single `delegate` tool"
  characterization as accurate for what it says, but not necessarily complete.
- Neither TUI layer (`opencode`'s TUI packages, `codex-rs/tui`, `goose-cli`'s `session/output.rs`
  beyond the two functions cited) nor either app's HTTP/server layer were surveyed for the
  cost-observability question beyond the specific functions cited — there may be additional
  user-facing surfaces (e.g. `/usage` slash commands, dashboards) not covered here.

## Deliverable

`dev/harness_survey/md/harness_survey.md` (602 lines): four per-harness sections (each with
six subsections matching the task's six questions, every claim carrying a `path:line`
citation) plus a six-row comparison table and four cross-cutting observations. Committed on
branch `harness` as `daf9fbda docs: add survey of four coding harnesses`.
