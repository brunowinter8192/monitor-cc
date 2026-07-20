# Worker Context-% Window Fixed: 200k → 1M, 2026-07-21

## Problem

`extract_worker_context_pct` (`src/workers/worker_format.py`) computed remaining-context percentage against a hardcoded 200,000-token window: `(100 * (200000 - cr)) // 200000`. The worker fleet runs exclusively on 1M-context models (claude-opus-4-8, claude-sonnet-5, claude-fable-5) — haiku-4-5 (200k) is never spawned as a worker. Against a 1M actual window, a worker sitting at 170,000 cache-read tokens displayed ~15% remaining when the true figure is ~83%, making workers look near-exhaustion far earlier than reality.

## Decision

Flat constant, no per-model lookup: `_WORKER_CONTEXT_WINDOW = 1000000`. A model→window map was explicitly rejected — the fleet is uniformly 1M, so a single constant is both correct now and the intended long-term shape; threading the model into the JSONL-scan function was avoidable complexity for a fleet with only one active window size.

## Verification

Threw a temp script (`/tmp/wctx_verify_script.py`, not staged) at the real function with fixture JSONL files (`{"type": "assistant", "message": {"usage": {"cache_read_input_tokens": <cr>}}}`), calling `extract_worker_context_pct(Path(...))` directly:

| cr | old (200k formula) | new (1M formula, actual) |
|---|---|---|
| 170000 | 15 | 83 |
| 0 | 100 | 100 |
| 1000000 | N/A (would go negative) | 0 |

All three matched the expected values exactly. `py_compile` clean on `worker_format.py`. Live-pane visual confirmation deferred to the user per task spec — this is a code-level integration check (real function, real JSONL shape, real file I/O), not a rendered-pane check.

## Note — out of scope, flagged not fixed

`src/workers/DOCS.md` states `extract_worker_context_pct` "mirrors the `worker-cli context_pct` bash formula" — that bash-side formula (in the `worker-cli` plugin, outside this repo's `src/`) was not located or touched in this session; if it also hardcodes 200000 it is now out of sync with the Python side. Not investigated further — out of this task's file scope.
