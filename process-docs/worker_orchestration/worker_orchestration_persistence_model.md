# Worker Orchestration — Cross-Worker Persistence Model (2026-06-08)

Status: Discussed 2026-06-08. Model affirmed as-is (no change) at that time. Residual tension left open (see "Open" section below).

Meta-topic (worker orchestration, not the proxy pipeline) — captured here because it surfaced during the monitor-cc port and this is the active project.

## Origin

Surfaced during the proxy operation-transcript port (staged Stage 1). A worker investigated Stage 1 fully (cross-model check), then died mid-implementation of Sub-Stage 1A at ~24% remaining context — uncommitted, in-flight work at the context wall. Recovery: Opus manually committed the WIP (with a SUCCESSOR-HANDOFF), spawned a fresh successor that merged the WIP branch and finished 1A. Raised the question: how do implementation workers benefit from the investigation across the worker's 200k context limit?

## The tension

- The cross-model check REQUIRES the worker to investigate the full picture independently — that independent second model IS the verification value.
- Full investigation is context-expensive (the worker reads everything).
- A large implementation task then exhausts the SAME worker's context mid-stage → death uncommitted.
- So full investigation (needed for cross-model) competes with implementation budget inside one 200k worker.

## Rejected alternative (Opus proposal, 2026-06-08)

"Investigation worker writes its plan as a persistent report on disk; each implementation sub-stage worker reads the report (cheap file-read) instead of relying on living context; Opus just points at the report."

Rejected by user. Reasons:
- **Opus has ~1M context, not 200k. Opus IS the persistence layer — that is precisely the orchestrator's role, enabled by the larger context window.**
- Disk-report-per-worker adds file-write overhead, double-reading (write then read), and process friction for no gain over Opus simply holding the report.
- It distributes what should be centralized: the investigation lives in ONE place — Opus's context.

## Affirmed model (rules as-is)

1. Worker investigates the FULL picture — no splitting of the investigation.
2. Worker reports to Opus. Opus holds the report in its ~1M context (the cross-worker shared memory).
3. Opus cuts the implementation into small sub-steps (Sequential Sub-Stage Decomposition).
4. Each sub-step is sized to be a committable unit a worker finishes in a bounded turn; we hope each worker closes one sub-step.
5. On worker death mid-stage, Opus spawns a precise successor from its mental-model + the held report + the dying worker's WIP commit/handoff. No re-investigation, no file archaeology.

Opus's 1M context is the structural enabler that removes any need for a disk-based cross-worker plan-report. The existing rules already encode this; no rule change needed.

## Open

Residual weak point observed this session: a sub-step's size must fit the EXECUTING worker's REMAINING context, not merely be "a sub-stage." Stage 1A was dispatched to a worker already at 24% (post-investigation + addendum) and died mid-stage uncommitted — the recap-after-stage clean-checkpoint guarantee failed because no commit landed before death. Candidate refinements (undecided): (a) pre-dispatch context-budget check before giving an implementation Go to a reused worker; (b) default-separate the investigation worker from the implementation worker (fresh worker for implementation, investigation report carried by Opus); (c) sub-step sizing keyed to remaining context. To decide later.
