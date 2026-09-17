# Survey of Four Open Source Coding Harnesses

Sources read: `/tmp/harnesses/opencode` (shallow-cloned, TypeScript), `/tmp/harnesses/goose`
(Rust), `/tmp/harnesses/plandex` (Go), `/tmp/harnesses/codex` (Rust). All claims below carry a file
path and, where useful, a line number. Statements marked "Inference" are conclusions drawn from
reading the code rather than something the code states outright.

---

## 1. opencode

opencode is a TypeScript agent built on the Effect framework, with a service/layer architecture
(`Context.Service`, `Layer.effect`) around a central `Session` concept. Prompt assembly lives in
`packages/opencode/src/session/` and `packages/opencode/src/provider/`.

### 1.1 Context management

Two independent, cooperating mechanisms:

**Compaction (summarization with a token-budgeted tail).**
`packages/opencode/src/session/compaction.ts` is triggered from `packages/opencode/src/session/prompt.ts:1319-1327`
when a turn's processor returns `"compact"`. Overflow detection lives in
`packages/opencode/src/session/overflow.ts`: `isOverflow()` (lines 22-34) compares
`tokens.total || input+output+cache.read+cache.write` against `usable()`, which is
`model.limit.input - reserved` (or `context - maxOutputTokens` if no `limit.input`), where `reserved`
defaults to `min(20_000, maxOutputTokens)` (`COMPACTION_BUFFER = 20_000`, line 8).

When compaction runs (`compaction.ts:319-557`), it does **not** summarize everything blindly. `select()`
(lines 223-269) partitions the message history into "turns" (one user message + everything after it up
to the next user message) and keeps whole recent turns verbatim up to a token budget
(`preserveRecentBudget`, lines 115-120: `config.compaction.preserve_recent_tokens` or
`clamp(usable*0.25, 2_000, 15_000)`). If a single turn does not fit, `splitTurn()` (lines 140-163) finds
a sub-index inside that turn that does fit. Everything before the retained tail (`selected.head`) is
serialized (`serialize()`, lines 54-85) into a plain-text transcript and sent to a dedicated
`compaction` agent (`packages/opencode/src/agent/agent.ts:219-233`, prompt in
`packages/opencode/src/agent/prompt/compaction.txt`) which writes a summary. The summary becomes a new
assistant message with `summary: true`; the original messages are *not* deleted from storage, they are
just excluded from the next prompt build via `head`/`tail_start_id` bookkeeping
(`completedCompactions()`, lines 97-113). Compaction is itself chained: `previousSummary` is passed
into `buildPrompt()` so a second compaction extends the first rather than re-summarizing already
compacted history.

**Pruning (deleting old tool output, independent of compaction).**
`prune()` (`compaction.ts:273-317`) walks messages backwards, skips the first full turn, and once
running tool-output size exceeds `PRUNE_PROTECT = 40_000` tokens (line 29), it marks every older
`tool` part's `state.time.compacted = Date.now()` — this is a destructive, in-place edit of stored
message parts, not a summarization. `PRUNE_PROTECTED_TOOLS = ["skill"]` (line 31) is exempt. Pruning
only actually commits if the amount that *would* be pruned exceeds `PRUNE_MINIMUM = 20_000` tokens
(line 308), to avoid thrashing on small savings. On replay, `serialize()` renders a pruned tool result
as the literal string `"[Old tool result content cleared]"` (line 77) instead of the real output, and
individual long tool outputs are hard-truncated at `TOOL_OUTPUT_MAX_CHARS = 2_000` chars with a
`[truncated]` marker (lines 30, 51-52) even when not pruned.

**Surprise:** on overflow, if the *current* turn alone doesn't fit even after compacting everything
before it (e.g. huge image attachments), opencode falls back to a "replay" strategy
(`compaction.ts:340-356, 469-494`): it strips media out of the offending user message, replays only the
text, and tells the model explicitly *"the conversation was compacted and media files were removed from
context ... explain that the attachments were too large"* (line 529) — the harness manufactures an
apology message on the model's behalf rather than silently dropping data.

### 1.2 Prompt caching

Deliberate, multi-provider cache-breakpoint placement in
`packages/opencode/src/provider/transform.ts:358-407` (`applyCaching`). It marks at most the last 2
system messages and the last 2 non-system messages as cacheable, using provider-specific
`providerOptions` keys: `anthropic.cacheControl`, `openrouter.cacheControl`,
`bedrock.cachePoint`, `openaiCompatible.cache_control`, `copilot.copilot_cache_control`,
`alibaba.cacheControl` (lines 362-381). For Anthropic/Bedrock it sets cache control at the
*message* level; for everything else at the last *content block* of the message (lines 384-401). This
is gated to only run for Anthropic-family models unless the provider already does automatic caching
(`message()`, lines 465-484, `usesAnthropicAutomaticCaching` check for `@ai-sdk/anthropic` /
`@ai-sdk/google-vertex/anthropic`).

Separately, `transform.ts:1310-1327` sets provider-native cache-affinity keys for non-Anthropic
providers: `prompt_cache_key` for DeepInfra/Cerebras, `promptCacheKey` for OpenAI/Azure/xAI/Mistral/
Venice — always keyed on the opencode `sessionID`, so repeated requests within one session route to
the same upstream cache/session shard.

The request-assembly layer (`packages/opencode/src/session/llm/request.ts:56-78`) also actively
protects a stable system-prompt prefix: it builds `system[0]` as the concatenation of
`agent.prompt ?? SystemPrompt.provider(model)` + dynamic `system[]` extras + `user.system`, then lets a
plugin hook rewrite `system`, but if the plugin only *appended* material (`system.length > 2 &&
system[0] === header`) it re-collapses everything after the header into a single second block (lines
74-78) — i.e. it deliberately keeps the header stable across turns for cache purposes rather than
letting arbitrary plugin edits perturb the cached prefix.

### 1.3 Multiple providers and models

`packages/opencode/src/provider/provider.ts` is a large provider registry (2072 lines). Providers are
loaded from `models.dev` catalog data, then merged with config (`cfg.provider`), env vars, stored
auth, and plugin-supplied credentials (lines 1440-1719). `BUNDLED_PROVIDERS` (lines 113-140) map ~19
`@ai-sdk/*` / custom npm packages (Anthropic, OpenAI, Azure, Bedrock, Google Vertex + Vertex-Anthropic,
OpenRouter, xAI, Mistral, Groq, DeepInfra, Cerebras, Cohere, Gateway, TogetherAI, Perplexity, Vercel,
Alibaba, GitLab, GitHub Copilot, Venice, Cloudflare Workers AI / AI Gateway, SAP AI Core, Snowflake
Cortex, ...) — this is the broadest provider list of the four harnesses. A single opencode installation
can have many providers simultaneously "connected" (`Provider.list()`), each independently authenticated.

Model selection is per-**agent**, not global: `packages/opencode/src/agent/agent.ts:45-50` gives each
`Agent.Info` an optional `model: { modelID, providerID }`; if unset it inherits whatever model the
parent/user message used (`tool/task.ts:181-184`). Built-in agents (`build`, `plan`, `general`,
`explore`, `compaction`, `title`, `summary`, lines 140-265) can each be pointed at a different
provider/model via `opencode.json`'s `agent.<name>.model`. There is also a distinct "small model"
concept (`Provider.getSmallModel`, lines 1939-2006) used for cheap/fast auxiliary calls (title
generation etc.), picked by family priority (`gemini-flash`, `gpt-nano`, `claude-haiku`) unless
`cfg.small_model` is set explicitly. `defaultModel()` (lines 2008-2041) also remembers recently-used
models per project in `~/.local/state/opencode/model.json`.

### 1.4 Sub agents and parallel work

`packages/opencode/src/tool/task.ts` implements the `task` tool. A subagent is a full nested
`Session` (`sessions.create({ parentID: ctx.sessionID, agent: next.name, ... })`, lines 156-172) with
its own permission ruleset derived from the parent (`deriveSubagentSessionPermission`) and its own
message history; it does **not** see the parent conversation directly — it is spawned with only the
`prompt` text the parent passed in (`ops.prompt({ ..., parts })`, lines 201-212). Its final answer is
the last text part of its own conversation (line 224) and is returned to the parent wrapped in an
`<task id=... state=...><task_result>...</task_result></task>` envelope
(`renderOutput()`, lines 64-79) inserted as the tool's output. Nesting is bounded by
`cfg.subagent_depth` (default 1, lines 104-117) by walking `parentID` up the session chain.

Parallelism is opportunistic rather than orchestrated: because `task` is an ordinary tool, the model
can emit several `task` calls in the same assistant turn and the harness's tool-execution loop runs
them concurrently (session/tools.ts, not fully read but implied by `Effect.forEach`/concurrency
patterns used elsewhere and by the explicit `background` mode described next).
There is also an experimental **background mode** (`params.background`, gated behind
`OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS`, lines 96-102, 316-319): the subagent runs detached via
`BackgroundJob.Service`, the tool call returns immediately with a "started" placeholder
(`BACKGROUND_STARTED`, lines 31-35), and when the subagent finishes, its result is injected back into
the *parent* session asynchronously as a synthetic user message (`inject()`, lines 227-254) — the
parent model is explicitly told *"DO NOT sleep, poll for progress ... Work on non-overlapping tasks"*.

### 1.5 Rules and instructions

`packages/opencode/src/session/instruction.ts` discovers project rules. Global: first existing of
`$XDG_CONFIG/opencode/AGENTS.md` or `~/.claude/CLAUDE.md` (unless
`OPENCODE_DISABLE_CLAUDE_CODE_PROMPT`; `globalFiles`, lines 60-63). Project: `AGENTS.md`, `CLAUDE.md`,
deprecated `CONTEXT.md`, found by walking from cwd up to the worktree root
(`fs.findUp`, lines 124-133) — only the **first** match wins per filename set, "so we don't stack
AGENTS.md/CLAUDE.md from every ancestor" (comment, line 122). Additional arbitrary instruction files or
URLs can be listed in `config.instructions` (glob patterns, `~/`-relative, or `https://` URLs fetched
with a 5s timeout, lines 135-169). There is also a **directory-scoped** mechanism: `Instruction.resolve()`
(lines 179-221) is called whenever a `read` tool loads a file, and walks upward from that file's
directory attaching any nearer `AGENTS.md`/`CLAUDE.md` it finds that hasn't already been surfaced —
each such file is attached at most once per assistant message (`InstanceState` `claims` map).

Placement in the prompt: `packages/opencode/src/session/prompt.ts:1257-1269` assembles `system = [
...env, ...instructions, ...mcpInstructions, ...skills]`; this whole array is then handed to
`llm/request.ts:58-66`, which puts it *after* the agent's own base prompt (`agent.prompt` or a
model-family prompt from `system.ts`) and *before* the per-message `user.system` field, joined into a
single `system[0]` block. So the hierarchy in the final request is: model/agent base prompt → runtime
environment info → user/project instructions (AGENTS.md/CLAUDE.md, global before project) → MCP server
instructions → skills catalogue.

### 1.6 Cost and token observability

Token/cost accounting is computed per assistant message in `packages/opencode/src/session/session.ts`
around lines 341-399: input/output/reasoning/cache-read/cache-write token counts are derived from the
SDK's `usage` object (adjusting for double-counted cached tokens, lines 361-364), and cost is computed
from `model.cost` (per-million-token rates, including tiered pricing above 200K context,
lines 379-399) using `Decimal` arithmetic. This is attached to `assistantMessage.cost` /
`.tokens` and persisted as part of the message row (`session.ts:97-144`, columns
`cost`, `tokens_input`, `tokens_output`, `tokens_reasoning`, `tokens_cache_read`,
`tokens_cache_write`) — i.e. per-request usage/cost is durably stored in the session database, not just
printed. `packages/opencode/src/session/processor.ts:452-493` updates these fields live as streaming
chunks arrive and re-checks `isOverflow` after every update. There is no separate CLI "usage" command
observed in the files read; observability is per-message, surfaced through the session/message API
(and presumably rendered by the TUI, which was out of the read scope for this survey).

---

## 2. goose (Block)

Rust, Cargo workspace of many crates. The core agent loop lives in `crates/goose/src/agents/agent.rs`;
provider request formatting lives in `crates/goose-provider-types/src/formats/*.rs`; context
compaction logic lives in `crates/goose/src/context_mgmt/` (thin wrapper) plus the separate
`crates/goose-context-management` crate.

### 2.1 Context management

Threshold-triggered **full summarization**, not a sliding window. `check_if_compaction_needed()`
(`crates/goose/src/context_mgmt/mod.rs:225-275`) compares current agent-visible token count against
`context_limit * threshold`, where `threshold` defaults to
`DEFAULT_COMPACTION_THRESHOLD = 0.8` (`crates/goose-context-management/src/lib.rs:32`), overridable via
the `GOOSE_AUTO_COMPACT_THRESHOLD` config key. `provider.manages_own_context()` short-circuits this
entirely for providers that do their own context handling (line 231-233).

When triggered, `compact_messages()` (`context_mgmt/mod.rs:70-207`) summarizes the whole
agent-visible conversation via a dedicated summarization prompt
(`compaction.md`/`compaction_summary.md` templates, `compaction_templates()`, lines 327-332) and marks
the original messages **not agent-visible but still user-visible** (`with_agent_invisible()`,
line 143) — the raw transcript is never deleted, only hidden from the model going forward, while the
UI/export can still show it. It then appends the summary plus a continuation instruction chosen from
three canned strings depending on context (`CONVERSATION_CONTINUATION_TEXT`,
`TOOL_LOOP_CONTINUATION_TEXT`, `MANUAL_COMPACT_CONTINUATION_TEXT`, lines 33-46). Non-manual compaction
additionally preserves the most recent user message verbatim as a fresh agent-visible message so the
model doesn't lose the live request it's supposed to be answering (lines 96-129), and it carries
forward any "turn-context" event (cwd, etc.) that trails the preserved prompt (lines 174-191) so a
mid-turn retry after compaction doesn't lose per-turn state.

There is a **second, independent, finer-grained mechanism**: per-tool-call summarization
(`maybe_summarize_tool_pairs()`, lines 493-590), gated behind `GOOSE_TOOL_PAIR_SUMMARIZATION` (off by
default). `compute_tool_call_cutoff()` (lines 367-375) scales a cutoff with context size
(`3 * effective_limit / 20_000`, clamped to `[10, 500]`); once the number of eligible (non-protected)
tool calls exceeds `cutoff + TOOLCALL_SUMMARIZATION_BATCH_SIZE (10)`, the oldest 10 tool call/response
pairs are summarized individually and in parallel (`tokio::spawn`, one LLM call per pair, grouped so
parallel tool calls sharing one assistant turn are summarized together, lines 510-564) — i.e. this is
pruning-by-summarization of old tool results, distinct from the whole-conversation compaction above.

### 2.2 Prompt caching

Anthropic-format caching is explicit and precisely placed
(`crates/goose-provider-types/src/formats/anthropic.rs`): `format_system()` puts `cache_control` on the
system block (lines 566-579), `format_tools()` puts it only on the **last** tool spec so "all tool
definitions will be cached as a single prefix" (comment, lines 554-556, code 556-561), and message
building extends the cached prefix each turn by tagging the last content block of the **last two user
messages** (lines 503-521, mirroring opencode's "last 2" heuristic). `AnthropicFormatOptions` supports
a configurable cache TTL (`5m` default vs `1h`, at 2x the write-cost, comment lines 122-124) and a
global `prompt_cache_disabled` kill switch that removes every breakpoint (test at line 3147, code
gates at 499, 550, 568).

**Surprise:** `crates/goose/src/agents/prompt_manager.rs:180-190` deliberately rounds the "current date
time" injected into the system prompt down to the hour (`"%Y-%m-%d %H:00 %:z"`), with the comment "so
that prompt cache can be used. Filtering to an hour to balance user time accuracy and multi session
prompt cache hits" — a concrete example of trading a small amount of freshness for cache-hit rate. The
same file also sorts extension/tool metadata by name before rendering the system prompt (lines
111-112, "Stable tool ordering is important for multi session prompt caching") — both are examples of
designing the *content*, not just the request, to keep a stable prefix.

### 2.3 Multiple providers and models

Providers are pluggable crates (`crates/goose-providers/*`, `crates/goose/src/providers/*`): OpenAI,
Anthropic (via format crate), Bedrock, Azure Foundry, OpenRouter, Databricks (+v2), GitHub Copilot,
Google Gemini OAuth, GCP auth, ChatGPT/Codex passthrough providers, declarative/custom providers
(`config/declarative_providers.rs`), and local inference (`goose-local-inference`, MLX/HF models). A
single session has one active provider/model (`session.provider_name`, `session.model_config`), but
**subagents can be given a different provider and model than the parent** — this is first-class, not
incidental. `crates/goose/src/agents/platform_extensions/summon.rs:1718-1878`
(`resolve_model_config`/`resolve_provider`) resolves, in priority order: recipe-declared
`goose_model`/`goose_provider` → `GOOSE_SUBAGENT_MODEL`/`GOOSE_SUBAGENT_PROVIDER` env vars → per-call
tool arguments → global config → falling back to the parent session's model. This means a user (or a
recipe author) can pin, e.g., all delegated "worker" subagents to a cheaper/faster model while the
parent planner uses a stronger one. `crates/goose/src/agents/subagent_task_config.rs:34-54`
(`TaskConfig::new`) carries the resolved `provider`/`model_config` through to the child agent.

### 2.4 Sub agents and parallel work

Subagents ("tasks"/"delegates") run as fully independent `Agent` instances
(`crates/goose/src/agents/subagent_handler.rs:120-247`, `get_agent_messages`): a new `Agent` is
constructed, its provider is set via `update_provider` (possibly a different provider, see 2.3), any
extensions from `task_config.extensions` are attached, a system prompt is built from a
`subagent_system.md` template listing the tools it has access to and the max turns it's allowed
(`build_subagent_prompt`, lines 249-273), and it is given a single seeded user message: `"Subagent ID:
{id}\n\n{task}"` (lines 172-173) — the subagent does **not** inherit the parent's conversation history,
only the task text and the recipe's `instructions` (used as its system prompt). It runs its own
`agent.reply()` loop to completion (or `max_turns`, default 25,
`subagent_task_config.rs:9,48-52`, configurable via `GOOSE_SUBAGENT_MAX_TURNS`), streaming its own
messages via callbacks (`on_message`), and its result is extracted as concatenated text output
(`extract_response_text`, lines 63-116) or via a structured "final output" tool if a response schema
was set (`get_final_output`, lines 275-286). This text becomes the parent's tool result.
`crates/goose/src/agents/platform_extensions/summon.rs` (4434 lines, only partially read) implements
the tool that drives this: a single `delegate` tool (registered at lines 779-796) whose built-in
description explicitly teaches the model how to parallelize: *"Parallel: async: true, then
load(taskId) to wait and get results... Research (read-only): parallelize freely - delegates explore
and report back. Work (writes): partition files strictly - no two delegates touch the same file"*
(lines 787-792). So parallel sub-agent use in Goose is opt-in per call (`async: true`) with an explicit
follow-up `load(taskId)` tool call to collect the result later, and the tool description itself warns
that *"Delegates cannot coordinate. Same-file work = conflicts"* (line 788) — coordination is left
entirely to the parent model's task partitioning, not enforced by the harness.

### 2.5 Rules and instructions

Explicit two-level hierarchy: **global** (`~/.config/goose/.goosehints` or `AGENTS.md`, plus a
dedicated `~/.agents/AGENTS.md` "agents home" directory) and **project** (walked from the git root down
to cwd, concatenating every `.goosehints`/`AGENTS.md` found along the way — root file first, then each
subdirectory, `load_hints.rs:232-311`, `get_local_directories`). Configurable filenames via
`CONTEXT_FILE_NAMES` config key (default `[".goosehints", "AGENTS.md"]`,
`load_hints.rs:13-24`). Hint files support `@relative/path` **imports** that get expanded recursively,
bounded to not escape the git root ("import boundary", tested extensively in
`load_hints.rs:610-695`), and are filtered through the project's `.gitignore` chain
(`build_gitignore()`, lines 214-230, merges `.gitignore` from git-root down to cwd).

There is also a **third, dynamic level**: as the agent uses tools referencing paths outside the
original hint scan, `SubdirectoryHintTracker` (`load_hints.rs:26-103`) watches tool arguments
(`path`/`command` fields) and lazily loads `.goosehints`/`AGENTS.md` for any newly-touched subdirectory,
injecting it mid-session as an "### Subdirectory Hints (path)" system-prompt extra
(`prompt_manager.rs:212-228`). All of this — hints, extension docs, per-turn extras — is assembled by
`SystemPromptBuilder::build()` (`prompt_manager.rs:108-177`) into one `system.md`-templated prompt with
a trailing `"# Additional Instructions:"` section for everything that isn't the base template.

### 2.6 Cost and token observability

`crates/goose-cli/src/session/output.rs:1564-1643`: `display_context_usage()` prints a colored
progress bar (`green`<50%, `yellow`<85%, `red`≥85%) of `total_tokens/context_limit`, and
`display_cost_usage()` prints per-request cost (`estimate_model_cost`, pulling from a canonical
pricing table, `providers::canonical_cost`) as `"Cost: $X.XXXX USD (N tokens: in A (R cache read, W
cache write), out B)"` on stderr. Usage is also structurally tracked in
`goose-provider-types::conversation::token_usage::{Usage, ProviderUsage}` (input/output/total/
cache-read/cache-write tokens plus an optional `cost`/`cost_source`), and
`crates/goose/src/session/session_manager.rs` persists `session.usage.total_tokens` as part of the
session record (used later by `check_if_compaction_needed` as an authoritative token count instead of
re-estimating, `context_mgmt/mod.rs:250-251`). No dedicated CLI "usage ledger" subcommand was found in
the files read (unlike Plandex, see §3.6).

---

## 3. plandex

Go, monorepo `app/{server,cli,shared}`. Plandex is architecturally different from the other three: it
is a client/server system with a persistent **plan** (a stateful unit of work with its own DB rows for
conversation, context, and file diffs) rather than a single in-process conversation loop, and it is
built around distinct **model roles** rather than one model for everything.

### 3.1 Context management

Two mechanisms, applied to two different things:

**Conversation summarization (rolling checkpoints, not sliding window).**
`app/server/model/plan/tell_summary.go:22-231` (`addConversationMessages`) computes total conversation
tokens and, if `(tokensBeforeConvo+conversationTokens) > GetPlannerEffectiveMaxTokens()` **or**
`conversationTokens > GetPlannerMaxConvoTokens()`, walks a list of previously-generated summaries
(`summaries []*db.ConvoSummary`, persisted rows, each with a `LatestConvoMessageId`/timestamp cutoff and
token count) looking for the *first* one that, if substituted for everything up to its cutoff, brings
the total back under budget (lines 60-123). If found, that one stored summary text replaces all
messages up to its cutoff; if none of the existing summaries is enough, the conversation is simply too
large and the request fails with an explicit user-facing error (lines 125-136) rather than silently
truncating. `summarizeConvo()` (lines 233-434) is what generates a new summary checkpoint: it always
summarizes from the *previous* summary (if any) forward, not from scratch, so summaries are
incremental/chained. `DefaultMaxConvoTokens` and `MaxTokens` are per-model constants in
`app/shared/ai_models_available.go` (e.g. Claude Sonnet: `DefaultMaxConvoTokens: 15000, MaxTokens:
200000`; Gemini 2.5 Pro: `75000`/`1047576`).

**Context-window trimming (per-request, budget-capped, not persisted).**
`app/server/model/plan/tell_context.go:29-366` (`formatModelContext`) builds the `### LATEST PLAN
CONTEXT ###` block from loaded files/URLs/directory-trees/images. It applies a hard `maxTokens` cutoff
(line 221-226: stop adding parts once the running total exceeds it), and — during the "implementation"
stage with "smart context" enabled — filters context down to only the files the *current subtask*
declares it `UsesFiles` (lines 66-74, 112-117), i.e. per-subtask context scoping rather than always
sending the whole loaded context set. Pending (not-yet-applied) file content is shown only as a
one-line "has pending changes (N tokens)" placeholder during the context-selection phase instead of the
full diff, specifically to avoid "the context phase [getting] overloaded with pending file content"
(comment, lines 236-241).

### 3.2 Prompt caching

Deliberate Anthropic-style `cache_control: {type: "ephemeral"}` breakpoints
(`app/server/types` `CacheControlSpec`), placed at multiple *stable prefix boundaries* rather than only
at the very end: on the last content part of the formatted context block
(`tell_context.go:347-351`), on the auto-context prompt during the context phase
(`tell_sys_prompt.go:66-72`), on the planning-phase system prompt or the formatted subtask list
(`tell_sys_prompt.go:82-102`), and on the implementation-phase prompt/subtask list
(`tell_sys_prompt.go:132-151`). Capability is gated per model: `client.go:429-436` and `tell_exec.go`
strip every `CacheControl` from the request if `!baseModelConfig.SupportsCacheControl`, and
`client.go:189-197` retroactively strips all cache markers and retries if the provider returns a
`shared.ErrCacheSupport` model error mid-stream. Context ordering is also cache-aware: when
files are activated in the order the model referenced them, unmatched files are still sorted by a
stable key "so we are using a stable order for caching" (`tell_context.go:198-201`).

### 3.3 Multiple providers and models

This is Plandex's most distinctive feature relative to the other three: instead of one model for the
whole session, a **`ModelPack`** assigns a separate model+provider to each of several named **roles**
(`app/shared/ai_models_data_models.go:716-828`): `Planner`, `Coder` (optional), `PlanSummary`
(conversation summarizer), `Builder` (structured-edit application), `WholeFileBuilder` (optional,
defaults to Builder), `Namer` (plan/branch naming), `CommitMsg`, `ExecStatus` (auto-continue
decisions). Built-in packs (`app/shared/ai_models_packs.go:1-40`) include `DailyDriverModelPack`,
`ReasoningModelPack`, `StrongModelPack`, `CheapModelPack`, `OSSModelPack`,
`OllamaExperimentalModelPack`/`OllamaAdaptiveOssModelPack`/`OllamaAdaptiveDailyModelPack`,
provider-pinned packs (`AnthropicModelPack`, `OpenAIModelPack`, `GoogleModelPack`), and single-model
"planner override" packs (`OpusPlannerModelPack`, `GeminiPlannerModelPack`, `O3PlannerModelPack`,
`R1PlannerModelPack`, `PerplexityPlannerModelPack`). Each role can additionally declare
`LargeContextFallback`, `ErrorFallback`, and `StrongModel` fallback configs
(`getLargeContextFallback`/`getErrorFallback`/`getStrongModelFallback`,
`ai_models_packs.go:57-79`) — i.e. automatic model/provider fallback chains per role, not just a
static assignment. `app/server/model/client.go:107-213` (`CreateChatCompletionStream`) resolves the
concrete provider client per request via `modelConfig.GetProviderComposite(...)`, retries through the
fallback chain on error (`GetFallbackForModelError`, line 165), and applies provider-specific request
shaping for OpenAI, Google Vertex, Azure OpenAI (including a deployment-name remap and
`reasoning_config`→`AzureReasoningEffort` translation), Amazon Bedrock, Ollama, and OpenRouter
(auto-appending `:nitro` for fastest routing unless already pinned, lines 132-136) all from one code
path (`createChatCompletionStreamExtended`, lines 216-397).

### 3.4 Sub agents and parallel work

No general-purpose "spawn a sub-conversation" or "delegate" tool was found anywhere in
`app/server`. Instead, parallelism is **structural and fixed by the pipeline**, not something the model
invokes: the build/apply stage spawns one goroutine per pending file
(`app/server/model/plan/build_exec.go:30-93`, `Build()` → `go state.queueBuilds(...)` per path, then
`go state.execPlanBuild(...)` per file) and each file's structured-edit generation
(`fileState.buildStructuredEdits()`, called from `buildFile()`, line 397) is an independent LLM call
using the `Builder` role model. There is no shared reasoning context between these parallel builds
beyond the file's own pre-build state and the plan's context; they cannot talk to each other or spawn
further children. **This is a clear absence relative to the other three harnesses** — Plandex has
concurrency (file-level build parallelism) but no agent-invoked sub-agent/delegation mechanism.

### 3.5 Rules and instructions

No AGENTS.md/CLAUDE.md-style automatic rule-file discovery was found (grepped for
`CustomInstructions`, `ProjectInstructions`, `plandex.md`, `.plandexrules` — no hits). Plandex's
"instructions" are exclusively: (a) the user's own prompt text passed to `plandex tell`/`plandex chat`
(`app/cli/cmd/tell.go:173-201`, including an editor-based multi-line entry flow), and (b) explicitly
loaded **context** — files/directories/URLs/images/trees the user adds with `plandex load`, which then
flow through `formatModelContext` (§3.1) into the prompt. There is no directory-level or
global-vs-project rule hierarchy; all "rules" are just more loaded context or more prompt text, and the
system prompts themselves (in `app/server/model/prompts/`) are static per pipeline stage
(planning/context/implementation/chat), not user-customizable at the project level in the files read.

### 3.6 Cost and token observability

The richest, most productized observability of the four, because Plandex bills usage as SaaS
credits. Every model call reports through a hook (`app/server/model/plan/tell_stream_usage.go`):
`handleUsageChunk()` (lines 14-74) fires `hooks.DidSendModelRequest` with input/output/cached tokens,
model id/tag/name/provider, the active `ModelPackName`, the specific `ModelRole` that made the call,
generation id, and plan/session ids, on every usage chunk received mid-stream; `execHookOnStop()`
(lines 76-141) fires the same hook on early termination (cancel/error) with `StoppedEarly`/
`UserCancelled`/`HadError` flags and `NoReportedUsage: true` so the billing layer knows the usage figure
is an estimate. This is per-request server-side logging by construction. On the client side,
`app/cli/cmd/usage.go` implements a dedicated `plandex usage` command with `--log` (paginated
transaction log, `--debits`/`--purchases` filters), and `--session`/`--today`/`--month`/`--plan`
scoping — i.e. a persisted, queryable usage/cost ledger, not just an ephemeral terminal print.

---

## 4. codex (OpenAI)

Rust, Cargo workspace `codex-rs`, structured around `codex-rs/core` (the agent/session engine) with
protocol/app-server/TUI layers on top. This is the largest and most "product-hardened" codebase of the
four (analytics events, hooks, guardian/safety layers, plugin system, realtime/websocket transport),
reflecting its origin as OpenAI's first-party CLI.

### 4.1 Context management

Threshold-triggered **history replacement with a summary** ("Memento" strategy,
`codex-rs/core/src/compact.rs`), similar in spirit to Goose's but with more nuanced boundary handling.
The trigger lives in `codex-rs/core/src/session/context_window.rs:52-121`
(`context_window_token_status_with_config`): it tracks `auto_compact_scope_tokens` against
`model_info.auto_compact_token_limit()` (a **per-model** constant, not a fixed percentage), with a
configurable scope (`AutoCompactTokenLimitScope::Total` — full active context — or `BodyAfterPrefix` —
only tokens added after the initial system/context prefix, so a large fixed prefix doesn't itself force
compaction). `token_limit_reached` becomes true once usage reaches the auto-compact limit plus a
configurable fallback buffer, **or** once the model's hard `full_context_window_limit` (context window
× `effective_context_window_percent`) is hit regardless of the auto-compact scope (lines 104-109) — the
hard cap always wins.

Compaction (`compact.rs:114-405`, `run_compact_task_inner_impl`) asks the model itself to summarize the
current history (`SUMMARIZATION_PROMPT`, or a config override `compact_prompt`), then replaces history
with: recent real user messages verbatim, budget-capped at `COMPACT_USER_MESSAGE_MAX_TOKENS = 20_000`
tokens total (selected newest-first, with the oldest surviving one hard-truncated if it doesn't fully
fit, `build_compacted_history_with_limit`, lines 679-756) followed by the generated summary
(`SUMMARY_PREFIX` marker). Canonical initial context (environment/AGENTS.md/etc.) is then re-spliced
back in at a model-expected position — "immediately before the last real user or agent message" if one
remains, else before the summary, else before the last compaction marker, else appended
(`insert_initial_context_before_last_real_user_or_summary`, lines 598-664, with an extensive doc
comment explaining exactly why each placement rule exists). If the *compaction request itself* exceeds
the context window (a pathological case — summarizing a too-large history), the harness recovers by
trimming from the **front** of the input it's compacting and retrying, explicitly "to preserve cache
(prefix-based) and keep recent messages intact" (lines 308-317) — a caching-aware repair loop, not a
truncate-and-give-up. Every compaction attempt is tracked as an analytics event
(`CompactionAnalyticsAttempt`, lines 407-495) recording trigger/reason/phase/tokens-before/after/
duration — compaction has first-class telemetry, unlike the other three harnesses.

### 4.2 Prompt caching

Codex targets OpenAI's Responses API, which caches based on conversation continuation
(`previous_response_id`) plus a **stable `prompt_cache_key`**, rather than explicit per-message
breakpoints like the Anthropic-family harnesses. `codex-rs/core/src/client.rs:541-553`
(`prompt_cache_key`) derives this key as: an explicit override if set, else
`"{internal_source}:{parent_thread_id}"` for internal (non-root) agent sessions, else the session id —
i.e. every request in a thread (and every non-root sub-agent thread) gets a stable identity string so
upstream cache/session affinity is preserved across turns and across sub-agent spawns. Separately,
`responses_request_properties_match()` (lines 329-384) decides whether the *current* request is
"the same shape" as the previous one (same model/instructions/tools/tool_choice/reasoning/store/stream/
include/service_tier/**prompt_cache_key**/text) to decide whether the websocket transport can send an
**incremental** continuation of the prior request instead of replaying the full history — this is a
stronger caching strategy than breakpoint hints: Codex avoids re-sending unchanged history at the
transport level entirely when possible.

**No explicit `cache_control` breakpoint mechanism was found** (Codex does not talk to Anthropic
directly in the files read) — caching is entirely the provider-side responsibility, driven by Codex
keeping `prompt_cache_key` and request shape stable.

### 4.3 Multiple providers and models

Configurable but comparatively thin: `codex-rs/model-provider-info/src/lib.rs` defines
`ModelProviderInfo` (base URL, `wire_api: Chat|Responses`, auth) with built-ins for `"openai"`
(`OPENAI_PROVIDER_ID`, line 72) and a local `"ollama"`/OSS provider
(`OLLAMA_OSS_PROVIDER_ID`, line 624, `create_oss_provider`); `codex-rs/core/src/config/mod.rs:878`
holds a `model_providers: HashMap<String, ModelProviderInfo>` merged from user config
(`merge_configured_model_providers`, allowing e.g. Azure-OpenAI-compatible endpoints to be declared).
However, **one `model_provider` is active per config/profile at a time**
(`config/mod.rs:637-641, 3707-3720`) — there is no per-turn or per-agent-role vendor switching observed
comparable to opencode's per-agent provider or Goose's per-subagent provider. What *does* vary per
agent role is the **model and reasoning effort within the same provider**:
`codex-rs/core/src/agent/role.rs` defines built-in roles (`default`, `explorer`, `worker`) each of
which can lock a `model`/`model_reasoning_effort` in its role TOML
(`AgentRoleOverrides`, lines 36-48, applied in `apply_role_to_config_inner`), and the `spawn_agent` tool
lets the calling model additionally request an explicit `model`/`reasoning_effort` override per spawn
(`multi_agents_v2/spawn.rs:272-280`, `SpawnAgentArgs`). *(Inference: because `model_providers` is
per-config rather than per-role, a genuinely different vendor per sub-agent would require running
separate Codex profiles, which is architecturally heavier than opencode/Goose's per-agent provider
field.)*

### 4.4 Sub agents and parallel work

The most explicit and richest sub-agent system of the four, implemented as a `spawn_agent` tool
(`codex-rs/core/src/tools/handlers/multi_agents_v2/spawn.rs`) backed by
`codex-rs/core/src/agent/control.rs` (981 lines) and `codex-rs/core/src/agent/child_config.rs`. Each
spawned agent is a **first-class independent thread** (`ThreadId`) with its own turn loop, not a
one-shot call. Roles are named and described directly in the tool surface, e.g. `explorer` ("fast and
authoritative... encouraged to spawn up multiple explorers in parallel when you have multiple distinct
questions... this parallelism is a key advantage of delegation, so use it whenever you have multiple
questions to ask", `role.rs:353-365`) and `worker` ("Explicitly assign **ownership** of the task
(files/responsibility)... tell workers they are **not alone in the codebase**... adjust their
implementation to accommodate the changes made by others", `role.rs:367-380`) — the harness's built-in
prompt text directly coaches the parent model on how to parallelize and avoid merge conflicts between
concurrent sub-agents, which is unique among the four.

Context handoff is explicit and tunable via `fork_turns` (`spawn.rs:270-317`): `"none"` (subagent gets
only the seed message, like Goose/opencode's default), `"all"` (full parent history forked into the
child, `SpawnAgentForkMode::FullHistory`), or an integer N (last-N-turns fork). Results come back via a
message-passing layer (`agent_communication`, `AgentCommunicationContext`/`AgentCommunicationKind::Spawn`,
`spawn.rs:168-173`) rather than a single synchronous return value: the parent can `wait` on a spawned
agent (`multi_agents_v2/wait.rs`), send it follow-up input (`send_message.rs`,
`followup_task.rs`), interrupt it (`interrupt_agent.rs`), or list all currently active agents
(`list_agents.rs`). There's a v1 (`multi_agents/`) and v2 (`multi_agents_v2/`) generation of this tool
family coexisting, plus `resume_agent.rs`/`close_agent.rs` for lifecycle control — this is closer to a
real multi-agent runtime than the other three harnesses' "fire task, block for text result" pattern.

### 4.5 Rules and instructions

`codex-rs/core/src/agents_md.rs` (well-commented, doc comment lines 1-18): walks upward from cwd to a
project root (found via configurable `project_root_markers`, default `.git`) and concatenates every
`AGENTS.md` (or configured fallback filenames, or `AGENTS.override.md` as a preferred local override,
lines 42-49, 272-296) found from the root down to cwd, **inclusive**, never walking past the root. This
is explicitly a hierarchy, but a linear directory-chain one (root→cwd) rather than the
global/project/directory *categories* Goose exposes. Content is capped by `project_doc_max_bytes`
(truncated with a warning if exceeded, `read_agents_md`, lines 125-187) and skipped entirely for
untrusted projects (`config.active_project.is_untrusted()`, line 64).

In the assembled request (`codex-rs/core/src/session/mod.rs:4175-4384`,
`build_initial_context_with_world_state`), rules land in **two structurally distinct buckets**: a
`developer_sections` bundle (config-level `developer_instructions`, extension/plugin-contributed
policy/capability fragments, rendered as `codex-protocol`'s "developer" role, distinct from
`system`/`user`) and a `contextual_user_sections` bundle (AGENTS.md content plus recommended-plugin
notices, rendered as a "user" role message, line 4358). This means Codex, uniquely among the four,
uses OpenAI's dedicated **developer** message role for host/config-level policy, keeping project
AGENTS.md content in a separate user-role context message — a three-way split (system/base
instructions, developer instructions, user-visible project docs) rather than the single flattened
system-prompt string the other three harnesses build.

### 4.6 Cost and token observability

`codex-rs/tui/src/status/thread_usage.rs` backs a live `/status` card
(`StatusThreadUsage`, lines 37-159): it shows total **credits** used (`estimated_usage_credits_micros`,
formatted with K/M/B/T suffixes, `format_credit_micros`, lines 298-317) plus, when available, an
estimated USD figure (`format_estimated_usd_micros`, lines 319-333, scaling precision from `~$0.000042`
up to `~$12.34` depending on magnitude) — reflecting that Codex is billed primarily through
subscription/credit plans rather than a simple per-token invoice. Usage is broken down by **model**,
**reasoning effort**, and **speed tier** within the thread (`grouped_usage`, lines 169-263,
percentage-weighted by credits), plus a separate input/cached/output token line
(`BILLED_TOKENS_LABEL`, lines 130-156). The context-window indicator itself is a separate, always-on
status line ("Context 30% left · Context 70% used · N in · N out", tested in
`tui/src/chatwidget/tests/status_and_layout.rs:114`) computed from `context_window_token_status()`
(§4.1). Compaction events are additionally emitted to an internal analytics pipeline
(`codex_analytics::CodexCompactionEvent`, `compact.rs:407-495`) recording active-context-tokens
before/after, cached/cache-write tokens, and duration — i.e. Codex has both a user-facing cost display
and a separate structured telemetry stream, the latter not found in the other three harnesses.

---

## 5. Comparison

| | **opencode** | **goose** | **plandex** | **codex** |
|---|---|---|---|---|
| **1. Context management** | Threshold-triggered summarization of a token-budgeted *head*, verbatim recent *tail* kept whole where possible (`session/compaction.ts`); separate destructive pruning of old tool output past a 40K-token watermark, replacing content with `"[Old tool result content cleared]"` (`session/compaction.ts:273-317`). Threshold = model input limit minus a reserved buffer (default 20K or max output tokens). | Threshold-triggered whole-conversation summarization at 80% of context (`DEFAULT_COMPACTION_THRESHOLD = 0.8`), messages marked agent-invisible but kept in storage; plus an optional, separate per-tool-pair summarization pass (batches of 10, `context_mgmt/mod.rs`). | Rolling **stored** summary checkpoints: picks the earliest existing `ConvoSummary` row that brings totals under a per-model `MaxConvoTokens`/`EffectiveMaxTokens`, else errors out explicitly (`tell_summary.go`). Separate per-request context-window trimming with a hard token cap and per-subtask file scoping (`tell_context.go`). | Threshold triggered by a **per-model** `auto_compact_token_limit` (scope configurable: full context vs. "body after prefix"), hard-capped by the model's real context window regardless of scope. History is replaced by up to 20K tokens of verbatim recent user messages + an LLM-written summary, with careful re-splicing of canonical context at a model-expected position (`compact.rs`). |
| **2. Prompt caching** | Explicit, provider-keyed cache breakpoints on last 2 system + last 2 non-system messages (Anthropic/OpenRouter/Bedrock/OpenAI-compatible/Copilot/Alibaba); native `prompt_cache_key`/`promptCacheKey` for OpenAI-family providers; deliberately stabilizes the system-prompt header across plugin edits. | Explicit Anthropic `cache_control` on system, last tool spec, and last 2 user messages, with configurable TTL; **rounds the injected timestamp to the hour and sorts tool metadata** specifically to preserve cache hits across sessions. | Explicit `cache_control: ephemeral` at multiple stable prefix boundaries (context block, stage-specific system prompt, subtask list); capability-gated per model and dynamically stripped/retried on provider cache errors. | No manual breakpoints (no direct Anthropic wire format); relies on a stable per-thread `prompt_cache_key` plus request-shape matching to enable OpenAI Responses-API server-side caching and websocket-level incremental (delta) requests that avoid re-sending unchanged history altogether. |
| **3. Multiple providers and models** | Broadest provider catalog (~20+ via `@ai-sdk/*`), all independently "connected" at once; model chosen **per agent** (`agent.model`), with a distinct cheap "small model" role; remembers recently used models. | Many first-class provider crates; one active provider per session, but **subagents can be given a wholly different provider/model** via recipe/env/config precedence, independent of the parent's provider. | Not one model but a **`ModelPack`** of named **roles** (Planner/Coder/Builder/WholeFileBuilder/Summarizer/Namer/CommitMsg/ExecStatus), each with its own model+provider and its own fallback chain (large-context / error / strong-model); a single request path shapes payloads for OpenAI/Vertex/Azure/Bedrock/Ollama/OpenRouter. | One active `model_provider` per config profile (OpenAI-first, plus configurable OpenAI-compatible endpoints and local OSS/Ollama); model + reasoning effort (not vendor) varies **per agent role**, lockable in role config, overridable per `spawn_agent` call. |
| **4. Sub agents / parallel work** | `task` tool spawns a nested `Session` with fresh context (only the given prompt, no parent history); result returned as a wrapped text block; optional async "background" mode with result injected back as a synthetic message; depth-limited. | Subagents are full independent `Agent` instances with their own provider/model/extensions, seeded with only the task text (not parent history); a single `delegate` tool whose own description teaches the model to run them with `async: true` + a later `load(taskId)` for parallelism, and warns delegates "cannot coordinate" so same-file work must be partitioned by the caller; text (or schema-validated) result returned; max-turns bounded. | **No agent-invoked delegation mechanism.** Parallelism is structural: one goroutine per file during the build/apply stage, each an independent LLM call; no inter-agent communication or spawning. | Richest system: `spawn_agent` creates a first-class independent thread with a named role (`explorer`, `worker`, ...), **configurable context fork** (none / last-N-turns / full history), and full lifecycle tooling (wait / send-message / interrupt / list / resume / close) via a message-passing layer, not just a blocking call-and-return. Built-in role prompts explicitly coach the parent model on parallel delegation and ownership boundaries. |
| **5. Rules and instructions** | Global (`AGENTS.md`/`CLAUDE.md`) + project (first match walking up from cwd) + arbitrary configured files/URLs + **dynamic per-directory** injection triggered by `read` tool usage; placed in the system message after the agent/model base prompt, before MCP/skill instructions. | Explicit **global / project / dynamic-subdirectory** three-tier hierarchy with `@file` import expansion bounded by the git root and filtered by `.gitignore`; assembled into one `system.md`-templated prompt with an "Additional Instructions" trailer. | **No automatic rule-file discovery at all.** "Rules" are only the user's own prompt and explicitly `load`-ed context files — a clear absence relative to the other three. | Linear root→cwd `AGENTS.md` chain (with a `.override.md` local override), byte-budgeted; placed as its own **user-role** context message, structurally separate from a **developer-role** bucket used for config/plugin policy instructions — a three-way message-role split unique to Codex. |
| **6. Cost / token observability** | Per-message token/cost computed from tiered per-model pricing and **persisted** in the session's message rows (DB columns); overflow re-checked live during streaming. No dedicated usage CLI command found. | Terminal token-usage progress bar + per-request `"Cost: $X.XXXX USD (...)"` line from a canonical pricing table; usage totals also persisted on the session record and reused for compaction threshold checks. No dedicated usage-ledger command found. | Most product-grade: every request (including early-terminated ones) reports through a server-side hook capturing tokens/cost/model/role/plan id; a dedicated `plandex usage` CLI command exposes a paginated, filterable (session/day/month/plan) persisted usage/credit ledger. | Live `/status` card breaking down **credits** and an estimated USD figure by model/reasoning-effort/speed-tier within the thread, plus a separate always-on context-window percentage indicator; compaction and usage events also feed a structured internal analytics pipeline distinct from the user-facing display. |

### Cross-cutting observations

- All four harnesses converge on the same core context-management idea — **LLM-generated
  summarization once some token threshold is crossed, with the raw history either hidden or
  discarded, never a naive sliding window** — but differ sharply in *what survives*: opencode and
  Codex keep a budgeted amount of the most recent turns verbatim alongside the summary; Goose keeps
  the immediately-preceding user message verbatim and otherwise hides (not deletes) the rest; Plandex
  keeps only whichever previously-generated summary checkpoint happens to fit, and fails loudly if
  none does.
- Deliberate prompt-cache engineering shows up in three of the four (opencode, Goose, Plandex), all
  converging independently on "tag the last one or two stable blocks with an ephemeral cache marker."
  Codex's approach is qualitatively different because it targets a provider (OpenAI Responses API)
  whose caching is session/key-based rather than breakpoint-based; Codex compensates with
  transport-level incremental requests, which is arguably a stronger mechanism than any of the
  breakpoint-based approaches, but is only inferable, not directly comparable, since it depends on
  server-side behavior not visible in this codebase.
- Plandex is the clear outlier on both sub-agents (structurally absent) and rules (structurally
  absent) — it substitutes a fixed multi-role pipeline plus explicit user-loaded context for both,
  which is a defensible but very different design point from the other three's "model can decide to
  delegate" / "filesystem convention decides rules" approaches.
- Codex's sub-agent system is the only one with genuine cross-agent messaging (send/interrupt/wait/
  list as separate primitives) rather than a single blocking call; this tracks with it being the only
  harness with a dedicated multi-agent protocol version history (`multi_agents` vs `multi_agents_v2`).
