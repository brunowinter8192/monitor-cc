# Worker Reuse Economics — Trade-off Investigation

## Problem

Current reuse rule (`workers-3.md` AGGRESSIVE REUSE: "reuse if files overlap, otherwise fresh spawn") is heuristic and probably too conservative. User observation 2026-04-27: workers are not reused often enough. Trade-off unclear quantitatively:

- **Fresh worker:** REQ#1 ~27k CC, clean context, but discovery cost (read every file from scratch).
- **Reused worker:** CR grows over lifetime (27k → 100–150k+), saves discovery reads, but context-rot risk.

Open questions: Where is the cost sweet spot? At what task count does CR explode vs. flatten out? Quality cliff (rising tool-error rate, backtrack edits, declining output quality)?

## Planned Phases (not executed)

### Phase A — Empirical Measurement

Script `dev/worker_reuse_analysis/aggregate_worker_costs.py` aggregates per worker session from `src/logs/api_requests_worker_*.jsonl` + worker session JSONLs in `~/.claude/projects/`:

- Spawn mode (fresh / reused-via-send — derivable from task boundaries = user turns)
- Lifetime: REQ count, total CR/CC/output_tokens, duration
- Per-task breakdown: REQs/task, read count/task, edit count/task, tool-error count/task, thinking-sig length/task, output_tokens/task
- Final: LOC diff from worktree git (productivity proxy)

Output: Markdown report + CSV. One row per worker + aggregate per spawn mode.

### Phase B — Literature Research

Theoretical basis (arxiv + reddit + searxng), findings in `sources/sources.md` with Type=Paper/Web:

1. Context-length vs. quality degradation — Lost in the Middle (Liu et al, 2023), LongBench/RULER, Anthropic studies on Claude's effective context window.
2. In-context learning across long conversations — multi-turn dialogue degradation, "Lost in conversation", multi-session memory.
3. Attention dilution / attention sinks — StreamingLLM (Xiao et al).
4. Practical engineering — LangChain/LlamaIndex multi-agent, Anthropic Engineering Blog on Claude Code, Cursor/Cline eng posts.

### Phase C — Synthesis + Rule Update

After data + literature:
- Cost sweet spot → rule "reuse until CR > X tokens" or "reuse until lifetime > N tasks".
- Quality cliff → rule "stop reuse when tool_error_rate > Y%".
- Decision doc with concrete thresholds, then sharpen the `opus/workers-3.md` AGGRESSIVE-REUSE section.

## Status

Spec only. No phase executed — neither the aggregate script nor the literature pass. Parked.

## Out of Scope

- General cost optimization.
- Worker spawn-time optimization (spawn <5s, irrelevant).
- Cross-model trade-offs (Sonnet vs. Haiku workers).
