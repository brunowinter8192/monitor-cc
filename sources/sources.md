# Sources

External references used as evidence for pipeline decisions.

| Source | URL | Relevance | Pipeline Steps |
|--------|-----|-----------|----------------|
| tmux man page | github.com/tmux/tmux `tmux.1` | split-window, pane targeting, layout, `-l size%` behavior | pipe01 |
| Claude Code #30973 | github.com/anthropics/claude-code/issues/30973 | InstructionsLoaded hook behavior | pipe03 |
| Claude Code #33275 | github.com/anthropics/claude-code/issues/33275 | InstructionsLoaded session_start bug | pipe03 |
| Claude Code #31017 | github.com/anthropics/claude-code/issues/31017 | InstructionsLoaded /clear behavior | pipe03 |
| Claude Code #12151 | github.com/anthropics/claude-code/issues/12151 | Plugin hook output bug (not affecting us) | pipe03 |
| Claude Code #19377 | github.com/anthropics/claude-code/issues/19377 | paths: YAML array syntax broken (CSV parser bug) | pipe04 |
| Claude Code #33581 | github.com/anthropics/claude-code/issues/33581 | Multiple paths: entries silently fail (same root cause as #19377) | pipe04 |
| Claude Code #16299 | github.com/anthropics/claude-code/issues/16299 | Path-scoped rules load globally (version-dependent) | pipe04 |
| Claude Code #27724 | github.com/anthropics/claude-code/issues/27724 | JSONL format undocumented, changes without changelog | pipe02, pipe04 |
| Claude Code #27361 | github.com/anthropics/claude-code/issues/27361 | Token counts ~2x too low in JSONL (streaming snapshots, no message_stop) | pipe03 |
| Claude Code #31585 | github.com/anthropics/claude-code/issues/31585 | Thinking tokens not in JSONL/OpenTelemetry metrics (open feature request) | pipe03 |
| Claude Code #33414 | github.com/anthropics/claude-code/issues/33414 | FireHose monitoring feature request | pipe02 |
| unified-cowork JSONL Spec | github.com/yjjoeathome-byte/unified-cowork | Community reverse-engineered Cowork audit.jsonl spec (related format) | pipe02 |
| termshot | github.com/homeport/termshot | ANSI text → PNG rendering (terminal screenshots) | pipe04 |
| mitmproxy #4456 | github.com/mitmproxy/mitmproxy/issues/4456 | Long-running mitmdump RSS growth + SIGUSR1 gc.get_objects diagnostic + flow.response.stream pattern | pipe05 (RAM) |
| mitmproxy http-stream-simple | github.com/mitmproxy/mitmproxy/blob/main/examples/addons/http-stream-simple.py | 15-LOC reference: enable response streaming for ALL flows | pipe05 (RAM) |
| textual #6381 | github.com/Textualize/textual/issues/6381 | Python gen2 GC pause stutters TUI render — gc.disable() workaround pattern | pipe04 (display) |
| glances #1447 | github.com/nicolargo/glances/issues/1447 | Long-running monitor RSS growth — memory_profiler + library-swap + --disable-history architectural option | pipe05 (RAM) |
| sources/RAM_research_2026-04-25.md | local | Synthesis: mitmproxy/textual/glances findings + 5 action-items for RAM investigation 2.0 | pipe05 (RAM) |
| claudeoo | github.com/monk1337/claudeoo | SSE stream interceptor for accurate token counts (solves #27361 undercount) | pipe02, pipe03 |
| better-ccusage | github.com/cobra91/better-ccusage | Post-hoc JSONL parser with session block aggregation, multi-provider | pipe02, pipe03 |
| ccusage | github.com/ryoppippi/ccusage | 5h billing block ceiling, session boundary detection, hash-based dedup, dual token naming convention | pipe02, pipe03 |
| hooks-observability | github.com/disler/claude-code-hooks-multi-agent-observability | 12 hook types, universal dispatcher pattern, HTTP+WebSocket real-time, SQLite storage | pipe03, pipe04 |
| claude-hud | github.com/jarrodwatts/claude-hud | CC statusline plugin, native context_window/rate_limits stdin data, transcript caching | pipe02, pipe03, pipe04 |
| Claude-Code-Usage-Monitor | github.com/Maciek-roboblog/Claude-Code-Usage-Monitor | Real-time TUI token monitor (7k stars), Python, P90 session limits | pipe02, pipe03 |
| tokscale | github.com/junhoyeo/tokscale | CLI token tracking with contributions graph, multi-agent support | pipe02, pipe03 |
| claude-code-hook-hero | github.com/damahua/claude-code-hook-hero | Plugin capturing 14 hook events, universal hook logging pattern | pipe03 |
| HitCC | github.com/hitmux/HitCC | Deep technical analysis: 25 hook events, InstructionsLoaded schema, hook return types | pipe03 |
| claude-howto | github.com/luongnv89/claude-howto | Comprehensive 25-event hook guide with JSON I/O schema, practical examples | pipe03 |
| Claude Code source | github.com/anthropics/claude-code | Hook internals: additionalContext merging, 50K truncation limit (v2.1.89), _meta override (MCP only), hookSpecificOutput format | pipe03, pipe04 |
| Claude Code #41799 | github.com/anthropics/claude-code/issues/41799 | 50K hook output truncation undocumented | pipe04 |
| Claude Code #42869 | github.com/anthropics/claude-code/issues/42869 | _meta maxResultSizeChars undocumented (MCP only, not hooks) | pipe04 |
| Reddit: cc-cache-fix | reddit.com/r/ClaudeCode/comments/1seo9gg/ | Cache investigation, community discussion | cache-investigation |
| Claude Code #42796 | github.com/anthropics/claude-code/issues/42796 | Cache investigation | cache-investigation |
| HackerNews: 47660925 | news.ycombinator.com/item?id=47660925 | Cache investigation | cache-investigation |
| cc-cache-fix repo | github.com/Rangizingo/cc-cache-fix/ | Cache investigation, reference implementation | cache-investigation |
| Reddit: adaptive-thinking | reddit.com/r/ClaudeCode (post) | CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING + MAX_THINKING_TOKENS env vars for restoring pre-adaptive thinking quality | proxy-tuning |
| Anthropic Prompt Caching | docs.anthropic.com/en/docs/build-with-claude/prompt-caching | cache_control placement, prefix order (tools→system→messages), max 4 breakpoints, auto-detection at block boundaries, TTL (`"1h"` string format confirmed), pricing, scope:global, content-hash-based cache keys, org-isolated, **20-block lookback window** for prefix matching | proxy-tuning, cache-investigation, pipe05 | Verified |
| Anthropic Prompt Caching (local mirror) | `sources/PromptCaching1.md` – `PromptCaching6.md` | Local copy of the above. Drove `decisions/cache_rebuild_cases.md` Case 5 + BP-layout v2 rewrite (commit `060ff07`): 20-block lookback explicitly requires a second breakpoint when growing tools push the old write outside the window. | pipe05 | Referenced |
| CC Architecture Deep Dive (Cache) | github.com/yaojunfeng-collab/claude-code-architecture-deep-dive `03-cache-optimization.md` | Cache key composition (system+tools+model ID+thinking+betas+messages), 3-layer caching (global system, message BP, beta latch), scope options (null/org/global), DYNAMIC_BOUNDARY, sticky-on latch, MCP delta mode | cache-investigation, proxy-tuning | Referenced |
| Anthropic API Docs Mirror — Context Management | `sources/Compaction1-4.md`, `ContextEditing1-5.md`, `ContextWindow.md`, `Msgs1-2.md`, `Files1-2.md`, `FineGrained1.md` | Local mirror of server-side compaction, context editing, context window behavior, message structure, file handling, fine-grained tool streaming docs. Input for Monitor_CC-m8u feature catalog Section 1 (Context Preservation). | features_catalog, m8u | Indexed (local) |
| Anthropic API Docs Mirror — Instruction Following | `sources/Effort.md`, `Stop-Verhalten1-5.md`, `Skills1-6.md`, `Structured_outputs1-4.md` | Local mirror of effort parameter, stop reasons, skills cache behavior, structured outputs. Input for Monitor_CC-m8u feature catalog Section 2. | features_catalog, m8u | Indexed (local) |
| Anthropic API Docs Mirror — Display / Blocks | `sources/Citations1-3.md`, `ProgToolCalling1-5.md`, `Search_results1-4.md`, `Streaming_Messages1-5.md`, `Streaming_Refusals.md`, `TokenCounting1-2.md`, `Tools1-7.md`, `ToolSearch1-3.md`, `Vision1-2.md`, `PDF_support1-3.md` | Local mirror of block types, tool calling protocols, streaming behavior, token counting, vision/PDF support. Input for Monitor_CC-m8u feature catalog Section 3 (Display Features). | features_catalog, m8u | Indexed (local) |
| Anthropic API Docs Mirror — Extended Thinking | `sources/ExtendedThinking1-4.md`, `ExtendedThinking5-6.txt` | Thinking blocks, signature encryption, summarized vs omitted display, preserving across tool loops, interleaved thinking on Opus 4.7. Key facts: signature decrypts server-side to reconstruct raw thinking; past-turn thinking not billed; tool-loop continuations keep thinking "current" (still billed). | fyl, pipe05, OldThemes/tokenizer_baseline | Indexed (local) |
| Anthropic API Docs Mirror — Adaptive Thinking | `sources/AdaptiveThinking1.md`, `AdaptiveThinking2.md` | `thinking.type: "adaptive"` — dynamic thinking budget, default for Opus 4.7 and Mythos Preview. Replaces deprecated `type: enabled + budget_tokens` on Opus 4.6/Sonnet 4.6. | fyl, pipe05 | Indexed (local) |
| Anthropic API Docs Mirror — Task Budget | `sources/TaskBudget1.md`, `TaskBudget2.md` | Effort parameter (`low`/`medium`/`high`/`max`), soft guidance for adaptive thinking allocation. | fyl | Indexed (local) |
| Monitor_CC-m8u Feature Catalog | `decisions/features_catalog.md`, `/Users/brunowinter2000/Documents/ai/Meta/blank/decisions/feature_*.md` (23 files) | Per-feature proposals with What/Why/How/Risk/Verification, derived from the Anthropic docs mirrors above. Top-3: KNOWN_MESSAGE_TYPES batch update, ToolSearch block types, stop_reason+effort display. | features_catalog, m8u | Referenced |
| ast-grep/ast-grep | github.com/ast-grep/ast-grep | Structural code search via tree-sitter AST — alternative to Grep for pattern-based code navigation. Zero-indexing CLI. Candidate for reducing Grep zero-results (Bead eew). | eew | Referenced |
| nesaminua/claude-code-lsp-enforcement-kit | github.com/nesaminua/claude-code-lsp-enforcement-kit | Claude Code hooks that intercept Grep/Glob/Read and force LSP-based symbol navigation via cclsp (TS) or Serena (multi-lang) MCP. Documented 73% token savings. Candidate for zero-result reduction via LSP routing. | eew | Referenced |
| oraios/serena | github.com/oraios/serena | MCP toolkit for semantic code retrieval/editing, SolidLSP backend for multiple languages (Python, Go, Rust, Java, TS, Vue). "IDE for agents" — evaluated for eew, deemed overkill for Monitor_CC codebase size. | eew | Referenced |
| rtk (Rust Token Killer) | reddit.com/r/ClaudeAI/comments/1r2tt7q + github.com/rtk-ai/rtk | CLI proxy sits between Claude Code and terminal commands; filters/compresses command output before it reaches the LLM. Reports 89% token savings (155-line cargo test → 3 lines). Community critiques: strangeness tax (LLMs spend extra tokens on unknown formats), opacity (user can't reason about what was stripped). Best pragmatic alternative from comments: tee-to-file + hint that Claude can re-read. | 06o, tool-use | Referenced |
| humanlayer — context-efficient backpressure | humanlayer.dev/blog/context-efficient-backpressure | Article on managing LLM context via backpressure (referenced in rtk thread above). | 06o, tool-use | Referenced |
| Catppuccin Mocha | catppuccin/catppuccin (palette spec) | Color palette source for proxy/zebra/badge ANSI codes | pipe-ui | Referenced |
| Claude Code #33949 | github.com/anthropics/claude-code/issues/33949 | SSE streaming hangs root-cause analysis (kolkov reverse-engineering of Stream-Watchdog: 30s warn / 60s abort / non-streaming retry; ping-resets-watchdog flaw); cli.js v2.1.74 offset ~10,437,656 documented | rkk, t1i | Referenced |
| Claude Code #25979 | github.com/anthropics/claude-code/issues/25979 | Claude Code hangs indefinitely when API streaming connection stalls (no read timeout); main tracking thread for community workaround `CLAUDE_STREAM_IDLE_TIMEOUT_MS` | rkk, t1i | Referenced |
| Claude Code #26224 | github.com/anthropics/claude-code/issues/26224 | "Claude Code hanging/freezing/stuck for 5–20 min or more"; 90+ comments; Anthropic single "actively investigating" comment Feb 2026, no follow-up; status page Operational throughout | rkk, t1i | Referenced |
| Claude Code #49500 | github.com/anthropics/claude-code/issues/49500 | "API Error: Stream idle timeout — partial response received"; active Apr 2026 thread; 90s hardcoded client timeout hits Opus 4.7 + thinking | rkk, t1i | Referenced |
| Claude Code #18028 | github.com/anthropics/claude-code/issues/18028 | API Streaming Stalls 59–138s — oldest precise timing data for stall pattern | rkk, t1i | Referenced |
| alanisme/claude-code-decompiled | github.com/alanisme/claude-code-decompiled | Community CC decompile (post-source-map-leak Apr 2026) — `docs/en/19-streaming-and-transport-layers.md`, `docs/en/02-hidden-features-and-codenames.md`, `docs/en/21-model-selection-and-routing.md` | t1i | Referenced |
| wzf1997/claude-code-source | github.com/wzf1997/claude-code-source | Community CC source extract (transport-layer details, retry/streaming) | t1i | Referenced |
| thepono1/claude-code-source | github.com/thepono1/claude-code-source | Community CC source extract — `INSIGHTS.md` aggregate of v2.1.88 source-extracted env vars + read-sites; primary cross-reference for env-var inventory v2.1.121 | t1i | Referenced |
| @anthropic-ai/claude-code (npm tarball) | npmjs.com/package/@anthropic-ai/claude-code | Direct binary extract of v2.1.121 darwin-arm64 binary via `grep -oa "CLAUDE_[A-Z][A-Z_]*"` — 291 CLAUDE_* strings, 52 perf-adjacent non-CLAUDE_ strings; basis for `dev/cc_source_research/20260428_env_var_inventory_v2.1.121.md` | t1i | Referenced |
