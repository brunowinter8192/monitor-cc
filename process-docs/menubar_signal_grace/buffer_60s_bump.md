# Signal-Grace Buffer: 5s → 60s Bump

## What changed

`ORCHESTRATOR_SIGNAL_BUFFER_SECS` in `src/menubar/proc_cache.py` raised from `5.0` to `60.0`.

## Why 5s was insufficient

The original 5s value was sized to cover the send→UserPromptSubmit-hook latency only — the gap
between worker-cli writing the orchestrator signal and the CC hook firing to flip the worker's
hook-state to `working`. That race is <2s in practice.

The false-positive abort observed in production exposed a second, longer gap: after the hook fires
(status = `working`) the worker enters an initial thinking phase that can last 30-60s without
producing any JSONL writes. During that window:

1. `list_alive_sessions()` reads the JSONL mtime to determine `has_bg` / status
2. No new JSONL write → mtime stale → status inferred as `idle`
3. Signal is older than 5s → `_has_recent_send_signal` returns False
4. All workers bucketed as idle → `all_idle=True` → abort fires

The JSONL-mtime inference is the structural cause; the signal-grace buffer is the pragmatic
workaround until a proper status channel (hook heartbeat, explicit working-state file) is built.

## Why 60s

Empirical floor: observed thinking phases reach 30-60s for complex spawn prompts. 60s gives a
~0s margin for a 60s think, ~30s margin for a 30s think. A tighter value (e.g. 30s) would still
allow false aborts on longer thinking phases.

## Live-data evidence

During a 3-minute observation window after deploying the abort-decision logging
(`/tmp/menubar-abort.log`, 107 `abort_check` entries across two projects):
- 3 `decision=ABORT` entries observed
- All 3 fired when `sig_age` was well past 60s (workers genuinely done, signal stale)
- 0 false aborts with the 60s buffer in effect

Signal format: `sig_age=<N.N>` seconds since worker-cli wrote the signal. All abort-eligible
workers showed `sig=none` (no signal ever written for that session) or `sig_age` in the hundreds
of seconds, confirming the buffer correctly suppressed the false-positive window.

## Tradeoff acknowledged

A genuinely dead worker (crashed, stuck, no response) will not be auto-aborted until its signal
ages past 60s from the last send. This delays the cleanup by ~55s relative to the old buffer.
The abort check fires every 1.5s (POLL_INTERVAL), so the worst-case additional wait is 60s from
the time of send — acceptable given the orchestration poll cadence and the rarity of dead-worker
scenarios vs the frequency of long thinking phases.

## Pending

Long-term fix: replace JSONL-mtime status inference with an explicit working-state file or hook
heartbeat so the signal-grace buffer can return to a tight value (≤5s).
