# Proxy-side pending-background-task state — design + implementation, 2026-08-06

Milestone 2: the orchestrator can arm a new background sleep-timer while an earlier background
task is still pending, producing stacked timers and duplicate wakeups. Design (agreed before
implementation): the proxy is the observer — it already sees the launch-ack
(`strip_bg_launch_ack.py` detection, `bg_escape.py` precedent for acting on it) and the completion
notice (the TN branch in `message_passes.py`, exit-code-agnostic per the Milestone 1 wording
inventory). This entry covers the proxy-side state-maintenance half; a later milestone-3 hook
(not built here) reads the state file to block new sleep-timers while a pending entry exists.

## The landmine — why an in-memory dedup set (bg_escape.py's approach) doesn't work here

`bg_escape.py` dedupes repeated ack sightings (the same genuine ack text resends on nearly every
subsequent request for the rest of a session — measured 142/169 in that module's own corpus pass)
with a module-global in-memory `set`, safe there because firing a tmux Escape twice is the only
failure mode, and a restart re-populating the set from scratch just risks one harmless extra fire.

Pending-state can't use the same trick alone, because it must survive a proxy restart (the
milestone-3 hook reads the file independent of proxy process lifetime). The naive fix — "arm iff
no CURRENTLY-pending file entry exists for this id" — has a real bug: after a legitimate clear
(entry removed on genuine completion), the task's OLD ack text is still sitting later in the
ever-growing conversation history (same resend mechanic `bg_escape.py` already established). The
next resighting of that stale ack, with no pending entry present, would RE-ARM a task that already
finished — the exact stacked-timer failure mode this milestone exists to prevent, self-inflicted.

**Fix: a tombstone, not a deletion.** On clear, the entry is never removed — only status-flipped
`pending → cleared` with a `cleared_at` timestamp (`armed_at` preserved). The arm path checks "does
ANY entry already exist for this id" (any status), not "is it currently pending" — an existing
cleared tombstone blocks re-arming exactly like an existing pending entry does. This is
restart-safe by construction, since it's a file-presence check, not an in-memory one. A small
in-memory `_arm_attempted_ids`/`_clear_attempted_ids` set pair is layered on top purely to skip
redundant file I/O for ids already resolved this process — correctness lives entirely in the file.

## Refinements added during Go (three, from review before implementation)

1. **Ordering within one request.** `stripped_msg_removed` (msg-idx → removed chunks, shared input
   with `bg_escape.py`) is iterated via `sorted(keys())`, ascending — an ack always sits at a lower
   message index than its own completion notice in real conversation history, so this guarantees
   arm-before-clear even when BOTH land in the same call: the first request after a proxy restart
   resends the whole history at once, so ack and TN for an already-completed task can both appear
   as "removed chunks" together. Verified with a probe case constructed with DESCENDING dict-key
   insertion order specifically (`{5: [tn], 0: [ack]}`) — Python dict iteration preserves insertion
   order, so an unsorted implementation would process the TN first and produce a no-`armed_at`
   orphan tombstone instead of a proper arm-then-clear; the test catches exactly that regression.
2. **TN with no prior entry writes a tombstone, not a no-op.** A completion notice for an id this
   proxy never armed (started mid-session, or the ack's id failed to extract) still writes
   `{status: cleared, cleared_at: <ts>}` with no `armed_at`. Costs nothing, and structurally
   guarantees that task id can never later be mistaken for a fresh arm target regardless of
   processing-order gaps — the same tombstone-not-deletion logic extended to the orphan case.
3. **24h tombstone pruning on write.** Mirrors the removed `block_concurrent_timer.py` hook's
   `timer_state.jsonl` convention (one entry per session, 24h prune by write-ts — see the
   `process-docs/tool_use_safety/` area's timer-guard concurrent-redesign entry). Only `cleared`
   entries are pruned; `pending` entries are NEVER pruned by the proxy — a pending entry's
   staleness/expiry is milestone-3's hook's job (it reads `armed_at` and applies its own threshold),
   pruning one here would defeat the tombstone dedup guarantee for a task whose completion notice
   simply hasn't passed through the proxy yet.

## A real bug caught by the probe suite, not by review

`_arm_pending`/`_clear_pending` originally wrote timestamps as
`datetime.now(timezone.utc).isoformat() + "Z"` — copied from `bg_escape.py`'s own `_log_*` pattern.
That pattern is fine for `bg_escape.py`, whose `ts` field is write-only (an informational JSONL
trace line, never parsed back). It is NOT fine for `armed_at`/`cleared_at`, which
`_prune_stale_tombstones` (and later, milestone-3's expiry check) must parse back: a tz-aware
`datetime.isoformat()` already appends `+00:00`, so concatenating `"Z"` after it produces an
unparseable `...+00:00Z` double-suffix. The probe's 24h-pruning test (seeded with a manually
constructed 25h-old timestamp) caught this immediately — the "old tombstone pruned" check failed
because the malformed timestamp fell into `_prune_stale_tombstones`'s except-and-keep branch,
silently defeating pruning entirely (in both the module's own code AND the test's initial seed
data, which had copied the same broken pattern). Fixed with a `_now_iso()` helper matching
`addon.py`'s existing `mc_timestamp` convention exactly (`strftime` + manual millisecond + `Z`,
never `isoformat()` for anything meant to be reparsed) — `bg_escape.py`'s own `ts` field was left
untouched, since it genuinely is write-only there.

## State file shape (for milestone-3, not built here)

`src/logs/pending_bg_tasks.json` — single JSON object keyed by task_id, `MONITOR_CC_ROOT`/`/tmp`
fallback convention (same as `bg_escape.py`'s log file), mutable current-state (not JSONL — a
milestone-3 hook needs random-access lookup, not an append log):
```json
{"<task_id>": {"status": "pending", "armed_at": "<ts>"}}
{"<task_id>": {"status": "cleared", "armed_at": "<ts>", "cleared_at": "<ts>"}}
```
Documented expiry semantics: `armed_at` is the sole signal for a pending entry's staleness;
milestone-3's hook is expected to treat a `pending` entry with `armed_at` older than a threshold IT
defines as non-blocking, without requiring this proxy to mutate anything. This proxy never prunes
or expires `pending` entries itself.

## Verification

35/35 checks in `dev/timer-loop/p2_pending_bg_state_probe.py` — mix of direct-call regression
guards (arm/clear/tombstone/prune/ordering logic) and real `ProxyAddon.request()` integration
tests (end-to-end arm, end-to-end clear, worker-context no-write, failure isolation with a corrupt
state file). No regressions in the three pre-existing suites this change touches by proximity:
`dev/proxy/test_strip_fix.py` (150/150), `dev/proxy_dual_log/proxy_176_bg_launch_ack_tests.py`
(0 failures), `dev/bg_wakeup_id_line/p2_bg_escape_probe.py` (29/29, re-run as a sanity check since
`addon.py`'s `request()` now carries a second call alongside `_trigger_bg_escape`). Milestone-3's
hook behavior itself is unverified here — out of scope; this entry only establishes the state
file's shape and write semantics that hook will depend on.
