# Sidecar / Idle-Recap Strip — Removal (2026-06-08)

Status: **REMOVED + merged on dev** (commit `6da5410`, merge `2522af9`). The two short-circuit strips `_check_sidecar` / `_check_idle_recap` and their detectors are gone. This file is the demotion target for the old current-state history (formerly in the proxy-cache pipeline's current-state documentation) + the removal rationale.

## What Existed (Demoted from the Pipeline Current-State Doc)

- `stripped_sidecar_content` (added commit `54d743e`, 2026-04-23): `_check_sidecar` short-circuited early in `apply_modification_rules` (`src/proxy/rules.py`). Detected CC-internal sidecar requests via `_detect_sidecar` (`src/proxy/payload_helpers.py`): single-msg, plain-string content, empty system (≤10 chars), non-haiku. Replaced `messages[0].content` with marker `[SIDECAR_STRIPPED_<n>_BYTES]` before forwarding. Original rationale: a single sidecar injection once cost ~24k CC tokens (evidence: session 1776956156 REQ#80.1, 49,586c content). Short-circuit placement avoided a spurious `stripped_all_sr_msg0` on the marker.
- `stripped_idle_recap`: `_check_idle_recap` short-circuited the CC idle-recap injection via `_detect_idle_recap`: last-msg user, plain-string content starting with `"The user stepped away and is coming back."`. Replaced content with `[IDLE_RECAP_STRIPPED_<n>_BYTES]`.

Both bypassed the multi-pass span-derivation entirely (short-circuit BEFORE the pass chain). The op shape was the trivial full-replacement `Op(idx, 0, full_original, marker)`; the 7-tuple already carried `stripped_msg_originals` + `injected_msg_added` explicitly.

## Why removed — the use case is dead

CC 1.49 changed the payload structure. The detectors require **plain-string** content; current single-message non-haiku requests carry **list** content → `_detect_sidecar` never matches. `_detect_idle_recap` requires a last-msg plain-string starting with the idle marker → not present in current traffic. The strip targets a payload form CC no longer produces.

Decision: **remove**, not verify-synthetic, not blind-trust. Policy = observation over mutation (proxy pane = single source of truth). Stop mutating; rely on full-forward visibility in the proxy pane as the safety net. If a new sidecar-like structure ever appears, it becomes visible in the pane (full content forwarded → logged → rendered) and we react then. Removing a content-replacing strip IMPROVES visibility — real content flows to `_forwarded` instead of a marker.

## Investigation (how "absent from corpus" was confirmed real)

The `composition_probe` baseline (2026-06-08) reported `sidecar/idle_recap UNVERIFIED — absent from 5-stem corpus`. Two reframings settled it:

| Step | Method | Result |
|---|---|---|
| Opus initial (WRONG) | naive `grep stripped_sidecar_content` over dual_log | 127 sidecar / 66 idle_recap "matches" → concluded "data exists, just not in probe corpus" |
| Worker cross-check | production detectors `_detect_sidecar`/`_detect_idle_recap` over all 9 stems + `_stripped.jsonl` mod-records | **0 / 0** — corpus never captured a real sidecar/idle_recap |
| Opus verify | detector on stem `1780951598` + forwarded `modifications` field + match-context | detector 0/0; modifications field 0; raw matches are source-code-in-payload — first hit literally `src/proxy/rules.py:208: ["stripped_sidecar_content"]` |

The naive grep was fooled by monitor-cc dev sessions sending the proxy's OWN source (`rules.py`/`strip_vocab.py`, which contain the literal strings) as message payloads. The original "absent from corpus" was literally accurate. Cross-model divergence (worker contradicted Opus with stronger methodology) → Opus re-verified directly → worker correct.

## Safety condition (user) — verified

Full forwarded content must stay visible in the proxy pane. Worker-traced in `src/proxy/addon.py`: full original recorded before modification; with no short-circuit the payload returns unchanged; `_build_stripped_injected_deltas` finds zero changes (empty deltas); the proxy pane renders via `_build_forwarded_delta` as a standalone `'S'` entry (`_is_standalone_entry`, sys=0/tools=0) with full content. No drop path.

## Removal surface

- `src/proxy/rules.py` — `_check_sidecar` / `_check_idle_recap` defs + call-sites + imports (orchestrator now falls straight into the multi-pass chain)
- `src/proxy/payload_helpers.py` — `_detect_sidecar` / `_detect_idle_recap`
- `src/proxy/strip_vocab.py` — `SC` / `IR` RULES entries + `_SR_STRIP_RULES` exclusion (`('TN','SC','IR','PP')` → `('TN','PP')`, comment fixed to PP)
- `src/proxy/logging.py` — `SC` / `IR` in `_MSG_CODE_TO_FN`
- The proxy-cache pipeline's current-state documentation — `stripped_sidecar_content` entry removed
- `src/proxy/DOCS.md` — `rules.py` module entry (LOC 584→532, inject-points 4→3, Purpose + helper list)
- `dev/proxy_dual_log/` — `green_overlay_probe.py`, `composition_probe.py` (sidecar coverage block), `attribution_coverage.py`, `verify_delta.py`, `DOCS.md`

## Relation to the operation-transcript port

This emerged as "Stage 0" of the operation-transcript port (documented separately in this area) — originally "verify sidecar/idle_recap composition with real data". It became "remove" instead. The port's actual surface (multi-pass span-derivation) is UNAFFECTED: sidecar/idle_recap short-circuited before that path. `composition_probe` multi-pass stayed byte-exact post-removal (9509/9509 over the same 5 stems; count grew from the 7219 baseline only via append-only corpus growth, 492→567 entries). The port proper (pass-by-pass op recording → composition builder → CI invariant → fallback removal) is unchanged and pending.

## Runtime note

The running proxy carries the dormant old code until its next natural restart (live-copies under `src/logs/.proxy_live_*/proxy/` regenerate then). Zero behavioral gap meanwhile — the strip never fires on current CC traffic.
