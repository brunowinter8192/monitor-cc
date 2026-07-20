# Stripped/Injected Delta Logs — Four-Log Architecture (Phase 5)

Build step 2026-06-03. Two new DELTA logs `_stripped` / `_injected` in `src/logs/dual_log/`.
New module `src/proxy/diff_engine.py` (144 LOC) extracted as the single source of the align+classify engine.

## Context: What Existed Before

After phase 4 (the forwarded-delta build + the strip/inject span-diff verification, both in this area), there was:
- `_original` — fully cumulative, raw CC payload, untouched.
- `_forwarded` — a delta log: what was sent to the API (REQ#1 full, from REQ#2 diff).
- `diff_strip_inject.py` in dev/ — offline analysis that span-diffs original↔forwarded.

The classification "what was stripped / injected" was NOT persisted — only derivable via offline analysis of a dev/ script. For the monitor read-side (green/yellow highlighting) that would be a runtime computation on every frame render — too expensive. Decision: materialize it.

## Decision: Four Logs, No Annotations

**User decision:** no log gets annotations or comments. Four logs, simply read as-is.

**Why `_stripped` needs its own log:** the stripped content has no other home. In `_forwarded` it is, by definition, absent (it was stripped after all). In `_original` it sits as bytes — but the classification "this is stripped" is stored nowhere, it has to be derived. Materializing it is the value.

**Why `_injected` needs its own log:** symmetry with `_stripped` — injected content is only in `_forwarded`, not in `_original`. Directly greppable for verifying the inject logic.

**Logical non-redundancy:** strip/inject content is *bytes-redundant* with original/forwarded (the bytes sit there too), but **not logically redundant**: the classification is stored nowhere else and would otherwise have to be re-derived every time. Persisting it is the value.

## Delta Encoding for Stripped/Injected

Stripping is highly repetitive: sys[2] CC prompt, sys[3], msg[0] SR blocks get stripped identically on every request. As a full log, `_stripped` would repeat the same 130k-char rules per request.

**Solution:** delta encoding analogous to `_build_forwarded_delta`. A per-location hash chain (`loc_key → MD5[:10]` of the span texts, via `_hash_spans`). REQ#1 (`is_first: true`) writes everything. From REQ#2 on: only locations whose hash changed relative to the previous request. Stable strips (sys[2] always the same rules) appear once in the first request, then never again.

Hash state: `prev_stripped_hashes_by_model` / `prev_injected_hashes_by_model` in `ProxyAddon`, keyed by model_family. Identical to the `prev_delta_hashes_by_model` architecture of `_forwarded`.

**Entry form `_stripped` (`type: stripped_delta`):**
```json
{
  "type": "stripped_delta",
  "request_id": "<id>",
  "timestamp": "<iso>Z",
  "model": "<post-override model>",
  "is_first": <bool>,
  "counts": {"system": N, "tools": N, "messages": N},
  "system_delta": {"<idx>": [<span_text>, ...]},
  "tools_delta": {"<name>": {"whole": true} | {"desc": [<span_text>, ...]}},
  "messages_delta": {"<msg_idx>": {"<block_idx>": [<span_text>, ...]}},
  "fields_delta": {"<key>": <orig_value>}
}
```

`_injected` is built identically (`type: injected_delta`), but contains the insert spans and `fwd_value` in `fields_delta`.

## Full Payload Diff — Correctness at Top-Level Fields

**Core correctness point:** the diff covers ALL top-level keys of the payload, not just system/tools/messages.

Concrete example: the `model` override (`claude-opus-4-7` → `claude-opus-4-8`) is a field-level strip+inject operation — exactly the same mechanism as the sys[2] replacement, just at field granularity instead of block granularity. If `_diff_top_level_fields` were missing, `_injected` would claim "everything injected" while the `model` field silently slipped through — an inconsistency/bug.

**`_diff_top_level_fields(orig_payload, fwd_payload) -> list`** (in `diff_engine.py`): iterates all keys from orig ∪ fwd, skips `_COLLECTION_KEYS = {"system", "tools", "messages"}`, classifies each non-collection key as:
- `stripped` (only in orig)
- `injected` (only in fwd)
- `replaced` (in both, value different)

`_build_stripped_injected_deltas` processes `field_diffs`: a `replaced` entry lands in both `s_fields` (the `orig` value) and `i_fields` (the `fwd` value). The engine doesn't enumerate proxy operations; it diffs the whole payload. Every current or future top-level modification is captured automatically.

## `response()` Hook Placement — Off the Hot Path

**Problem:** `request()` is synchronous — mitmproxy waits for the return before forwarding. An expensive diff in the `request()` hook would add client latency.

**Solution:** the strip/inject diff runs in `response()` — after the upstream send (zero forwarding latency).

**Metadata bridge:**
- `request()` stores `flow.metadata["mc_original_payload"] = payload` (a reference to the dict parsed before `apply_modification_rules`) and `flow.metadata["mc_modified_payload"] = modified_payload` (post-cache-ops, final).
- `flow.metadata["mc_model_family"] = model_family` — so `response()` can read the right hash chain.
- `response()` reads these three fields, calls `_build_stripped_injected_deltas`, writes to `_stripped`/`_injected`. Isolated in its own `try/except` — a failure never touches forwarding or the other logs.

## Aliasing Finding: the Reference Is Safe

**Question:** `mc_original_payload` is a REFERENCE to the dict that gets modified later by `apply_modification_rules` etc. Is the original payload mutated in place?

**Analysis + finding: no.** The entire modification pipeline is functional:
- `cache.py` and `rules.py` build new dicts/lists (`{**msg, ...}`, `dict(msg)`, fresh `new_blocks`/`new_system` lists).
- No nested object shared with `mc_original_payload` is mutated in place.
- The one potential touch point: `cache_control` keys. But those are filtered out by `_strip_cache_control` during normalization before the diff — neutralized even if in-place mutated.

No snapshot needed. The reference stays stable until `response()` reads it.

## Single-Source Engine: `src/proxy/diff_engine.py`

**Starting point (the strip/inject span-diff verification entry in this area):** `diff_strip_inject.py` had the align+classify logic inline (self-contained, no imports). That was correct as long as the engine was only needed in the dev script.

**New requirement:** `_build_stripped_injected_deltas` in `logging.py` needs the same engine. Two copies = two divergence risks.

**Assumption revised:** dev modules are allowed to import src/. `dev/test_cwd_desktop_sidecar.py` already does this (`import src.menubar`). The `sys.path.insert` in dev/ scripts is the established pattern.

**Solution:** verbatim extraction of the engine from `diff_strip_inject.py` into `src/proxy/diff_engine.py` (144 LOC). All callers import from there:
- `src/proxy/logging.py` — direct import (`from .diff_engine import ...`)
- `dev/proxy_dual_log/verify_strip_inject.py` — via `sys.path.insert(0, parents[2])`, then `from src.proxy.diff_engine import ...`
- `dev/proxy_dual_log/diff_strip_inject.py` — analogous

The earlier verification (ratio threshold, span classification, alignment strategy) documented in the strip/inject span-diff entry stays valid — git history is the frozen reference, no second copy needed.

## cache_control Normalization Before the Diff

**Problem:** the original payload contains CC's `cache_control` markers, the forwarded payload contains the proxy's own (after `_strip_all_cache_control` + `_set_cache_breakpoints`). A naive diff would report cache_control repositioning as strip/inject spans — noise. BP3/BP4 movement would make 1–2 messages per request falsely appear "stripped and injected" (because they carry a BP depending on the turn or not).

**Solution:** `_strip_cache_control` is applied **at the call site** to BOTH payloads (the call site is in `_build_stripped_injected_deltas`, not in the engine). The engine gets cache_control-free inputs. cache_control forensics live in the `sent_meta` log, no information loss.

## Whitespace Fidelity (Documented Limitation)

Word-level spans (ratio >= 0.1, real partial edits) are rebuilt as space-joined words. Interword whitespace gets normalized in the process (multiple spaces → one space). Whole-block two-span replacements (ratio < 0.1, e.g. sys[2]: CC prompt → rules) preserve the exact text.

For the primary use cases (sys[2] strip, tool whole-strip, msg[0] block strips) this is unproblematic — all of those are ratio < 0.1 (whole-block). cache_control suffix edits (ratio ≈ 1.0) may lose internal whitespace in the span-text representation. Sufficient for monitor highlighting, not suitable for byte-exact reconstruction.

## Correlation Key: flow_id

**Problem (found live):** the four dual-logs had no shared join key:
- `_original` and `_forwarded` carry `request_id: ""` — CC sends no `x-request-id` header on the request; that only comes back in the API response.
- `_stripped` and `_injected` carry a UUID from the `_build_entry` fallback (`flow.request.headers.get("x-request-id") or str(uuid.uuid4())`), stored via `mc_request_id`. Different from `""`, but also not a reliable join across all four.

**Why ORDER alone breaks:** `_original`/`_forwarded` are written in `request()` (request order). `_stripped`/`_injected` are written in `response()` (response-completion order). Under concurrent requests these orders diverge. Realistic trigger: CC's Haiku title-gen request (runs concurrently with the Opus main request) — request order ≠ response order → per-request join by position is wrong.

**Fix:** `flow.id` is mitmproxy's stable per-flow UUID (`str(uuid.uuid4())` at flow creation, immutable). The same `flow` object is passed to `request()`, `responseheaders()`, and `response()` — no `flow.metadata` relay needed.

Implemented as a **dedicated field `"flow_id": flow.id`** (stamped at the call site) on all four dual-log entries:
- `_original`: in the dict literal in `request()`
- `_forwarded`: `delta_entry["flow_id"] = flow.id` after the `_build_forwarded_delta` return, before `_write_entry`
- `_stripped`/`_injected`: `s_entry["flow_id"] = flow.id` / `i_entry["flow_id"] = flow.id` after the `_build_stripped_injected_deltas` return, before `_write_entry`

`request_id` stays untouched in all four — semantically "Anthropic API x-request-id", can later be backfilled from the response header. `flow_id` is the read-side join key. No change to function signatures, hash logic, or the main log.

**Code-review-verified.** Live four-log flow_id join (read-side) gets confirmed during the monitor read-side migration.

## Verification Status — LIVE-VERIFIED

**`verify_strip_inject.py`** (dev/proxy_dual_log/, 345 LOC) — completeness proof:
- **Check 1 (span reconstruction):** for every block where `orig_text != fwd_text`, the engine reconstructs `orig_text` from (equal + stripped) and `fwd_text` from (equal + injected) spans.
- **Check 2 (field coverage):** every non-collection top-level field that differs appears in `fields_delta`.
- **Check 3 (model cross-check):** `injected fields_delta["model"]` matches the `model` field in the `_forwarded` delta entry.

**Offline run against `api_requests_opus_monitor_cc_1780497198`:** PASS 46/46.

**LIVE verification: session `api_requests_opus_monitor_cc_1780507825`** — 6 requests (2 Haiku title-gen + 4 Opus), all four logs each 6 lines, balanced.

Findings:

**Model override correctly captured (REQ#3, first Opus):**
- `_stripped fields_delta.model` = `"claude-opus-4-7"`
- `_injected fields_delta.model` = `"claude-opus-4-8"`

**Full-payload diff catches more than just model (REQ#3):** the same request additionally showed in `fields_delta`:
- `max_tokens`: 64000 (stripped) → 128000 (injected)
- `output_config`: fully rewritten
- `thinking`: fully rewritten

These are silent field modifications the old logging never recorded. Validates the decision for `_diff_top_level_fields` — without it, these fields would have been missing from `fields_delta` unnoticed.

**sys[2] byte-exact (REQ#3):**
- Stripped span: 7471 chars — exactly the CC system prompt.
- Injected span: 130441 chars — the rules blob; confirmed NOT present in the original.

**Delta suppression (REQs 4–6):** empty `system_delta`, `tools_delta`, `fields_delta` (stable strips suppressed after the first Opus request). Only new messages appear: REQ#5 `msg[2]`, REQ#6 `msg[4]`.

**Haiku:** its own `is_first` chain, independent of Opus.

The monitor read-side (highlighting) stays deferred until the read migration.

## Follow-Up: Janitor Integration Still Open

`_stripped` and `_injected` are **not yet** entered into `_LOG_REGISTRY` / the count-30 rotation in `claude_proxy_start.sh`. They accumulate unbounded until this follow-up is done. Affects only space management, not correctness.
