# Worker Reuse Economics — Trade-off Investigation

## Problem

Aktuelle Reuse-Regel (`workers-3.md` AGGRESSIVE REUSE: "reuse wenn Files überlappen, sonst fresh spawn") ist heuristisch und vermutlich zu konservativ. User-Beobachtung 2026-04-27: Worker werden nicht oft genug reused. Trade-off quantitativ unklar:

- **Fresh worker:** REQ#1 ~27k CC, sauberer Context, aber Discovery-Cost (Read jedes File von Null).
- **Reused worker:** CR wächst über Lifetime (27k → 100–150k+), spart Discovery-Reads, aber Context-Rot-Risiko.

Offene Fragen: Wo Cost-Sweetspot? Ab welcher Task-Anzahl explodiert CR vs flacht ab? Quality-Cliff (steigende Tool-Error-Rate, Backtrack-Edits, sinkende Output-Qualität)?

## Geplante Phasen (nicht ausgeführt)

### Phase A — Empirische Messung

Script `dev/worker_reuse_analysis/aggregate_worker_costs.py` aggregiert pro Worker-Session aus `src/logs/api_requests_worker_*.jsonl` + Worker-Session-JSONLs in `~/.claude/projects/`:

- Spawn-Mode (fresh / reused-via-send — ableitbar aus Task-Boundaries = user-turns)
- Lifetime: REQ-count, total CR/CC/output_tokens, Dauer
- Pro-Task-Breakdown: REQs/Task, Read-Count/Task, Edit-Count/Task, Tool-Error-Count/Task, thinking-sig-Länge/Task, output_tokens/Task
- Final: LOC-Diff aus worktree-Git (Productivity-Proxy)

Output: Markdown-Report + CSV. Pro Worker eine Zeile + Aggregat pro Spawn-Mode.

### Phase B — Literatur-Research

Theoretische Basis (arxiv + reddit + searxng), Funde in `sources/sources.md` mit Type=Paper/Web:

1. Context-Length vs Quality-Degradation — Lost in the Middle (Liu et al, 2023), LongBench/RULER, Anthropic-Studien zu Claude effective context window.
2. In-Context Learning across long conversations — Multi-Turn-Dialogue-Degradation, "Lost in conversation", Multi-Session-Memory.
3. Attention dilution / Attention sinks — StreamingLLM (Xiao et al).
4. Practical engineering — LangChain/LlamaIndex Multi-Agent, Anthropic Engineering Blog zu Claude Code, Cursor/Cline Eng-Posts.

### Phase C — Synthese + Rule-Update

Nach Daten + Lit:
- Cost-Sweetspot → Regel "reuse bis CR > X tokens" oder "reuse bis Lifetime > N tasks".
- Quality-Cliff → Regel "reuse stop bei tool_error_rate > Y%".
- Decision-Doc mit konkreten Schwellen, dann `opus/workers-3.md` AGGRESSIVE-REUSE-Section schärfen.

## Status

Spec only. Keine Phase ausgeführt — weder Aggregat-Script noch Literatur-Pass. Geparkt.

## Out of Scope

- Generelle Cost-Optimization.
- Worker-Spawn-Time-Optimization (Spawn <5s, irrelevant).
- Cross-Model Trade-offs (Sonnet vs Haiku Workers).
