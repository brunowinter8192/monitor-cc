# Proxy Logging Redesign — Dual-Log (Full Raw Original + Forwarded Delta)

Design decision 2026-06-02. Replaces the single forwarded-full log with TWO logs per session, to
guarantee full version-robust transparency of CC→proxy→API.

## Motivation

Current: one log/session = the FORWARDED (post-strip) full payload (`raw_payload`). The ORIGINAL
(CC→proxy) is stored only as per-strip fragments → CC→proxy is NOT fully reconstructable; there are
gaps (git_status, model_override, blocked_tool_refs — see 02_proxy_modification_completeness.md).
Goal: full transparency of BOTH original and forwarded; the difference = our stripping/injection.

## Architecture (LOCKED)

**Log 1 — ORIGINAL, FULL, RAW, every request. ZERO logic.**
- Exactly what CC sends, byte-for-byte, untouched, no delta, no reconstruction. The irreplaceable
  source of truth. Size ≈ today's log.
- **Why full/raw and explicitly NOT delta:** any delta/reconstruction scheme encodes assumptions about
  CC's payload STRUCTURE. CC changes that structure across versions. A delta scheme that silently breaks
  on a new CC version would corrupt the source-of-truth original unnoticed — FATAL. We cannot afford it.
  Raw-full is version-robust by construction. The extra storage is the deliberate price.

**Log 2 — FORWARDED, DELTA (cache-create / new content per request only). Small.**
- Only the NEW content per request (not the re-sent history).
- **Why delta is acceptable here but NOT on Log 1:** if Log 2's delta logic ever breaks on a CC version,
  the full original (Log 1) still provides full recovery. Asymmetry is intentional — protect the
  irreplaceable (original = full), allow delta only on the recoverable (forwarded).

**Derivation:**
- Per-request strip/inject = Log1[req] (original) vs Log2[req] (forwarded), for the request's new content.
- Prefix (system blocks + tools) is re-sent + re-stripped every request but stable → logged at req1
  (where it is "new" content); prefix CHANGES (context-mgmt edit, cache invalidation, modified old
  message) detected via existing `diff_from_prev` (logging.py) and logged when they occur.
- Full forwarded payload = NOT stored directly anymore; reconstructable (original − strips + injects).
  Acceptable consequence — original is the priority; forwarded is recoverable.

## Terminology (the two deltas, disambiguated)

- **"delta" (user's term)** = req-to-req NEW content = cache-create (the Monitor's CC column). What the
  Monitor shows per request. NOT the strip-delta.
- **strip-delta** = original − forwarded = what the proxy removed/injected. A different thing.

## Storage

≈ today (Log 1 full ≈ today's forwarded-full) + a small Log 2. "Etwas mehr", NOT double.

## Janitor impact

- `_LOG_REGISTRY` (src/log_janitor.py): the 2 api_requests categories (opus, worker) → 4
  (opus-original, opus-delta, worker-original, worker-delta). Retention `count-30` UNCHANGED ("30er-Logik").
- `count-30` enforcement also lives in the proxy-start bash (`janitor_trigger="proxy-start-bash"`), NOT
  in log_janitor.py itself — BOTH must be updated.

## Build plan (user-directed)

1. (this file) OldThemes updated.
2. Build dual-log writer in the proxy addon: Log 1 = raw full original snapshot taken at proxy ENTRY
   (before ANY modification); Log 2 = forwarded delta (new content per request). Monitor read-side
   adapted to consume Log 1 as display base + Log 2 for strip-highlighting.
3. Update janitor: `_LOG_REGISTRY` 2→4 categories + proxy-start count-30 logic.
4. CUT — clean break; new schema from now on.
5. NEXT session: verify the new logs are written correctly; clean up all logs NOT matching the new
   schema; THEN do the proxy completeness analysis on clean data.

## Open build details (resolve at build)

- Log 2 exact granularity: strictly only-new-content vs. also recording the (stable) prefix mods once.
- Monitor display change is significant: it must read two files, use Log 1 (original) as the base,
  overlay Log 2 to yellow-highlight strips + mark injections, and reconstruct the forwarded.
- The cut means the Monitor must handle BOTH old-schema (single forwarded-full) and new-schema logs
  until old logs age out of the count-30 window, OR old logs are purged at the cut.
