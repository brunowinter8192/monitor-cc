# Rules Staging — observed-but-not-yet-codified shared-rules changes

**Purpose:** Holding area for proposed `~/.claude/shared-rules` changes that arose from observed friction but are NOT yet hardened into rules. Rule changes are expensive cross-session infra — codify only after a failure mode RECURS. Each entry: trigger → proposed rule text → target file → status. When a trigger recurs, promote to the actual rule; if it never recurs, drop.

Replaces the old `~/.claude/shared-rules/_staging/` date-file mechanism (deleted 2026-06-01, "fast nur bs drin"). Staging now lives here in Monitor_CC and is RAG-indexed via `Monitor_CC-docs`.

---

## 1. Skill activation — once per session

**Trigger:** A worker re-activated a skill (github-search) that was already active in the session. Redundant — one activation covers the whole session.

**Proposed rule** (target: `global/tool-use.md`):
> A skill is activated at most once per session. One activation suffices for the entire session — never re-activate the same skill.

**Status:** OBSERVE — watch for recurrence before codifying.

---

## 2. Workers do no external research

**Trigger:** A worker was directed to do GitHub research (had to activate github-search). External research via workers "geht immer schief" — worker lacks skill context, burns budget, result unreliable.

**Proposed rule** (target: `opus/workers-*.md`):
> Workers never perform external research. All `gh-cli`, `rag-cli`, web, and forum lookups are done by Opus only. Worker prompts MUST NOT delegate any external-source research; Opus gathers the external evidence and passes findings into the prompt.

**Status:** PARTLY CODIFIED 2026-06-01 — the worker-side prohibition is now live in `worker/worker-rules.md` § 1 ("NEVER run `rag-cli` or any external research (gh-cli, web)"), per user directive. Remaining to observe: the Opus-side half — worker prompts must not delegate any external lookup; Opus gathers all gh/RAG/web evidence and passes findings into the prompt.

---

## 3. list_collections-first before RAG search

**Trigger:** RAG searches issued without first confirming which collections exist for the context. A context-filtered `rag-cli list_collections --filter <Project>` should precede `search_hybrid` so the right collection is targeted (e.g. confirm "which Monitor collections exist" before searching).

**Proposed rule** (target: `global/tool-use.md` § RAG CLI):
> Before the first `search_hybrid` on a context this session, run a context-filtered `rag-cli list_collections --filter <pattern>` to confirm the target collection name. The `--filter` IS the grep. Skip only when the collection name is already confirmed this session.

**Status:** OBSERVE.

---

## Candidate observations (this session, not user-raised)

### C1. Worker cross-project without worktree (mechanical batch)
Current rule: cross-project edits = Opus directly; workers only the current project, always in a worktree. This session a single `--no-worktree` worker did a mechanical 7-repo sources-teardown (delete dir + manifest edit + ref removal, one commit per repo) cleanly under Phase-2 plan-review + Phase-4 per-repo diff-review. Candidate: permit no-worktree multi-repo workers for mechanical, git-recoverable batch tasks. OBSERVE — needs a second clean instance before codifying.

### C2. Collection-naming drift in the rules — RESOLVED 2026-06-01
The OLD pre-consolidation collection names (`<Project>-meta` / `<Project>-features`) lingered across global/opus/worker rules after the collections were merged into `<Project>-docs`. Reconciled this session: redundant re-descriptions removed, all operational search commands updated to `-docs`, the two-collection routing merged into one. `worker/worker-rules.md` § 1 (which carried the last `-meta` ref) was replaced wholesale alongside the CLAUDE.md + sources cleanup. `## RAG Collection Layers` in `documentation.md` remains the canonical definition. situational/ left untouched (not loaded).
