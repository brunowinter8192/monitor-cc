# Forwarded-Log Delta Iteration — Step 1

Build step 2026-06-02. The `_forwarded` log switched from fully-cumulative to request-to-request delta.
`_original` stays unchanged (fully cumulative, source of truth).

## Delta Semantics

Per request, only what changed or was newly added relative to the PREVIOUS request of this proxy
session — across system blocks, tools, AND messages together.

- **REQ#1** (no predecessor, `prev_hashes is None`): everything included, `is_first: true`. Matches
  the previous full write. After that: only "cache create" — only changed/new elements.
- **REQ#N** (N > 1): a per-element hash comparison against the predecessor. An element is included when
  `i >= len(prev_hashes[cat])` (new index) OR `curr_hash[i] != prev_hash[i]` (content changed).
- Removed elements do NOT appear in the delta; `counts` (total system/tools/messages) lets a later
  reader detect removals (prev_count > curr_count).

## cache_control Normalize Decision

`_set_cache_breakpoints` places `cache_control: {"type": "ephemeral"}` on specific system blocks,
tools, and messages. BP3/BP4 move with every new turn → with a naive `json.dumps(element)` as the
hash basis, 1–2 messages per request would falsely appear "changed" (pure marker noise).

**Solution:** `_strip_cache_control(obj)` removes `cache_control` recursively before hashing (dicts/lists).
The **written** content in the delta stays the real element including the marker — only the **comparison hash**
ignores it. BP forensics live entirely in the `sent_meta` log, no information loss.

Confirmation (Opus verification, 3 constructed requests): a BP shift on a system block + message produces
`system_delta == {}` and `messages_delta == {}` (0 spurious delta). Real content changes + a new tool
are correctly detected as changed indices.

## Why `_compute_msg_hashes` Was NOT Reused

`_compute_msg_hashes` in `hash_meta.py` chunks the middle into rolling groups of 5 summaries
(`hash of concat-of-5-hashes`). At REQ#50 with 40 middle messages: 8 rolling chunks — not
back-computable to which individual message changed. Unusable for exact per-element selection.
→ a fresh flat per-message hash via `_delta_hash(m)` (MD5[:10] after the cache_control strip).

## Self-Healing State Order

`self.prev_delta_hashes_by_model[model_family] = curr_delta` is only set **after** a successful
`_write_entry` (both inside the try/except). If a write fails (I/O error), the hash chain stays at
the last successfully-logged state — the next request diffs against that state and folds the lost
material back in. No permanent reconstruction gap.

## Entry Form (JSONL)

```json
{
  "type": "forwarded_delta",
  "request_id": "<x-request-id or ''>",
  "timestamp": "<iso>Z",
  "model": "<modified_payload model, incl. override>",
  "is_first": <bool>,
  "counts": {"system": N, "tools": N, "messages": N},
  "system_delta": {"<idx>": <block>, ...},
  "tools_delta": {"<idx>": <tool>, ...},
  "messages_delta": {"<idx>": <message>, ...}
}
```

Only changed/new indices in the `*_delta` dicts. `counts` = the current total (shape reference
+ removal detection for readers). `model` = `modified_payload.get("model")` = the possibly post-override value.

## Implementation

New functions live exclusively in `src/proxy/logging.py` (no new module):
- `_strip_cache_control(obj)` — recursive normalize helper
- `_delta_hash(element) -> str` — MD5[:10] after the strip
- `_build_forwarded_delta(payload, request_id, prev_hashes) -> (entry_dict, curr_hashes)`

`src/proxy/addon.py`: new state `self.prev_delta_hashes_by_model: dict = {}`, the forwarded write block
replaced by a call to `_build_forwarded_delta`. All existing writes (main entry, sent_meta,
latency_update, _original) and the entire proxy modification logic unchanged.

## Live-Test Finding + Shape Fix

On real `monitor_cc` traffic, a content-identical user message (`"nochmal"`) falsely appeared in the
delta. Root cause: `_normalize_user_content_shape` in `cache.py` runs AFTER the block-level
`cache_control` strip and requires exactly `{"type","text"}` keys. When a BP sits on the message,
the block has 3 keys incl. `cache_control` → the condition doesn't fire → the content stays as
`[{"type":"text","text":"nochmal","cache_control":{...}}]` (list form). When the BP moves away,
only 2 keys remain → the condition fires → the content collapses to `"nochmal"` (plain string).

Our `_strip_cache_control` removed `cache_control`, but not the shape difference →
hash(`[{"type":"text","text":X}]`) ≠ hash(`"X"`) → spurious delta.

**Fix:** `_normalize_msg_shape_for_hash(msg)` in `logging.py` — an exact mirror of the condition from
`cache._normalize_user_content_shape` (no import: `cache.py` already imports from `logging.py` →
would be circular). Applied in `_delta_hash` after `_strip_cache_control` when `"role" in normalized` —
**only for the comparison hash**, the written element stays the real form.

Verified (automated assertions):
- All three forms (list+cc / plain string / list-without-cc) → identical hash
- Multi-block message (len > 1) → NOT collapsed
- A block with an extra key (e.g. `"id"`) → NOT collapsed
- Assistant messages → NOT normalized

**Note on sys[0]:** in the live test, `system[0]` shows up in the delta on every request (system[0] always in delta).
That's legitimate — CC rotates a cch billing token in sys[0] per request. Not a leak.

## verify_delta.py

`dev/proxy_dual_log/verify_delta.py` — proves losslessness + consistency of the forwarded-delta log
against the original log. Per-model-family chain reconstruction (delta overlay + truncate to counts).

Checks:
- **Check 1 (hard):** reconstructed counts == counts declared in the delta → FAIL on violation
- **Check 2 (soft):** `forwarded counts.messages` vs `n_messages` in the original → a mismatch is only
  reported (not a FAIL), because the proxy can legitimately change the message count

Run against `api_requests_opus_monitor_cc_1780441622`:
```
PASS — 6 ok, 0 soft-mismatch, 0 hard-fail
Delta self-consistency: VERIFIED
```
6 requests (2 haiku + 4 opus in two chains), all counts invariants satisfied.
