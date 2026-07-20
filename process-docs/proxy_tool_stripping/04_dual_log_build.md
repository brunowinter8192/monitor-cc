# Dual-Log Build — Additive Baseline Logging

Build step 2026-06-02. First concrete iteration of the architecture from the logging-redesign entry in this area. Purely additive logging — no monitor read-side, no janitor changes, no proxy-logic changes.

## What Was Built

**Only changed file:** `src/proxy/addon.py`

Two new, fully additive JSONL writes in `ProxyAddon.request()`, each isolated in its own `try/except`.
Write errors never propagate to the request-forwarding logic or the existing logs.

**Helper:** `_resolve_dual_log_file(suffix: str) -> Path` — mirrors `_resolve_log_file()`, writes to
`$MONITOR_CC_ROOT/src/logs/dual_log/api_requests_<log_id>_<suffix>.jsonl` (fallback: `/tmp/dual_log/`).
The subfolder `src/logs/dual_log/` is auto-created via `_write_entry` → `mkdir(parents=True, exist_ok=True)`.

**Envelope per line:**
```json
{"timestamp": "<iso>Z", "request_id": "<x-request-id or ''>", "model": "<model>", "payload": <full dict>}
```
`request_id` = `flow.request.headers.get("x-request-id", "")` — the same source as `_build_entry` → original/forwarded/main-log correlatable by `request_id`.

## The Two Snapshot Points

### Snapshot 1 — `_original` (before apply_modification_rules)

Write point: immediately BEFORE `apply_modification_rules(payload, ...)`.
`payload` is the raw CC payload from `_parse_payload(body)`. The schema check before it (lines 80–90)
reads `payload`, does not mutate it. Because it's serialized to JSONL immediately, later in-place
mutations by `apply_modification_rules` have no effect on the already-written line.

`model` field: `payload.get("model", "")` = the model CC requested, before any override.

### Snapshot 2 — `_forwarded` (the real wire payload)

Write point: immediately BEFORE `flow.request.content = json.dumps(modified_payload).encode("utf-8")`.
`modified_payload` has gone through the COMPLETE pipeline at this point — including
`_strip_all_cache_control` (line 158) and `_set_cache_breakpoints` (line 159).

**Deliberate difference from `entry["raw_payload"]` (main log, line 133):**
`entry` is built at line 133 — BEFORE the cache ops (lines 158–159). So `_forwarded` contains the
proxy's own `cache_control` breakpoints, `entry["raw_payload"]` does not.
That's intentional: `_forwarded` = exactly what Anthropic receives, byte-identical to the wire payload.

`model` field: `modified_payload.get("model", "")` = the possibly-overridden model value after `_inject_model_override`.

## What Was NOT Changed

- Existing log writes: schema_warning (line 84), main entry (line 152), sent_meta (line 173), latency_update (line 287) — byte-identical.
- Proxy modification logic: `apply_modification_rules`, `_strip_unused_tools`, `inject_mcp_tools`, `_strip_tool_descriptions`, `_strip_sys3`, `_strip_blocked_tool_references`, `_inject_context_management`, `_inject_model_override`, `_strip_all_cache_control`, `_set_cache_breakpoints` — all unchanged.
- Monitor read-side (`src/proxy_display/**`) — untouched.
- `claude_proxy_start.sh`, `log_janitor.py`, `logging.py._build_entry` — untouched.

## Orphan-Line Behavior

If the pipeline aborts with an exception between the two writes: `_original` has a line,
`_forwarded` doesn't. Deliberately informative, not artificially balanced.

## De-Risking Rationale

Logging-only first, against real traffic — before touching the monitor read-side or the janitor. The new
logs deliver the empirical baseline cut: which fields actually diverge between original vs. forwarded,
how large are the files, is the envelope format sufficient for later differentiation. Iteration after that is data-driven.

## Next Iterations (Planned, Not Built)

1. **Deltify message blocks** — tools + system blocks stay full per request (they are always
   sent completely), only messages get reduced to "new since the last request". Analogous to the
   existing `diff_from_prev` logic in `logging.py`, but directly in the `_forwarded` payload.

2. **Green-for-injected** — in addition to yellow-for-stripped in the monitor. Mark injections
   (wakeup text, model override, context-management, MCP tools) in the `_forwarded` log so the
   monitor display can color the original↔forwarded diff directly.

3. **Monitor read-side** — `src/proxy_display/` consumes `_original` as the display base, overlays
   `_forwarded` for strip highlighting. Requires a schema-compatibility check for old single-log sessions.

4. **Janitor 4 categories** — `_LOG_REGISTRY` in `src/log_janitor.py`: 2 api_requests categories
   (opus, worker) → 4 (opus-original, opus-forwarded, worker-original, worker-forwarded). The `count-30`
   logic also needs adapting in `claude_proxy_start.sh`. Retention strategy: `dual_log/` subfolder vs. main directory TBD.
