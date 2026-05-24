# Signal-Grace — Fix A (worker_spawn signal) + Fix 6 (worker-cli hooks.json)

## What was open (from initial_design.md)

**Bug 1 — worker-cli false-working (deferred):** worker-cli used tmux `window_activity` heuristic
which is bumped by CC UI updates (spinner, cursor blinks). This produces stale `working` reports
divergent from menubar's hooks.json-based truth. Explicitly deferred in the initial design.

**Use Case 1 — spawn + bg timer unprotected:** only `worker_send` wrote orchestrator-signal
entries. Newly spawned workers in their initial thinking phase had no signal protection. If the
worker JSONL-mtime went stale before the first write (common during long thinking phases), the
menubar would demote to idle → all_idle=True → abort fires. With the original 5s buffer this
could fire within 5s of spawn; with the 60s buffer (see buffer_60s_bump.md) this window extended
to 60s, but the spawn use case was still structurally unprotected.

## Fix A — worker_spawn writes orchestrator-signal

**Where:** `iterative-dev/src/spawn/tmux_spawn.sh:worker_spawn`, immediately after
`tmux new-session` creates the new session (line ~461 post-fix).

**Mechanism:** calls `_orchestrator_signal_update "$session"` — the same atomic-rename write
used by `worker_send`. Writes `{tmux_session_name: unix_ts}` to
`orchestrator_signals.json`.

**Effect:** from the moment the worker is spawned, its tmux session name is registered in the
signal file. The menubar reads this on the next tick and treats the worker as `working` for
`ORCHESTRATOR_SIGNAL_BUFFER_SECS` (60s). The initial thinking phase — which can exceed 30-60s
without any JSONL write — is now fully covered.

**Without this fix:** stale-JSONL demote → idle → all_idle=True → Opus bg timer killed during
the worker's first thinking phase.

**With this fix:** signal valid for 60s from spawn, no abort. By the time the signal expires
the worker has produced its first JSONL write and the hook state is authoritative.

## Fix 6 — worker-cli reads hooks.json

**Where:** `iterative-dev/src/spawn/tmux_spawn.sh:_worker_detect_status` — replaces the
tmux `window_activity` heuristic with direct hooks.json lookup.

**Mechanism:**
1. Get `pane_current_path` from tmux for the worker's session.
2. CC-encode the path (replace `/`, `_`, `.` with `-`) → `~/.claude/projects/<encoded>/` dir.
3. Find newest `.jsonl` in that dir → stem = `session_id`.
4. Read `~/.claude/hooks.json` (Monitor_CC app-support) → `hooks.json[session_id].status`.
5. Apply the same demote rule as menubar: if `status == working` AND `(now - jsonl_mtime) > 10s`
   → demote to `idle` (covers context-limit-hit and crashed workers where Stop-hook never fired).

`pane_dead` check and claude-descendant exited-check retained from prior logic — these cover
the case where the tmux pane itself is dead.

**Effect:** `worker-cli status <name>` now reports the same status as the menubar display,
using the same truth source (hooks.json) with the same demote rule. Bug 1 closed by design.

## Live verification (this session, ~03:10)

| Check | Result |
|---|---|
| `orchestrator_signals.json` had worker-Monitor_CC-signal-test entry immediately on spawn | ✅ ts=1779585151.625 |
| `/tmp/menubar-abort.log` — 40 `abort_check` entries during 60s window | all `decision=hold` |
| `sig_age` progression in abort log | 1.4s → 59.9s (linear, no gap) |
| Opus bg timer `sleep 60` | completed naturally — exit 0, no SIGTERM |
| `worker-cli status signal-test` vs menubar hooks.json | same status post-demote ✅ |

## Cross-references

- iterative-dev commit: `02efcdb` (Meta/blank repo, plugin-published this session)
- Related OldThemes in this folder:
  - `initial_design.md` — original Bug 1 deferred section (now resolved), Buffer Tuning table (5s, superseded)
  - `buffer_60s_bump.md` — 5s→60s rationale and live-data evidence

## Status

All three fixes live in production:
- **Fix A** (signal-on-spawn) — iterative-dev `02efcdb`
- **Fix 6** (worker-cli hooks.json alignment) — iterative-dev `02efcdb`
- **Buffer 60s** — Monitor_CC `proc_cache.py` (commit 15163ce)

**Bug 1 closed** by Fix 6. **Bug 2 closed** by combined buffer-bump + signal-on-spawn.
