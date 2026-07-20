# Proxy Prefix-Hash Instrumentation (Removed)

Demoted from the proxy-cache pipeline's current-state documentation — feature built, shipped, then removed as dead code.

**Built:** commit `feat/prefix-hash-instrumentation` (2026-04-19 refactor, `_build_sent_meta` in `src/proxy/hash_meta.py`, called from `addon.py`)
**Removed:** commit `e2af735` ("Block A: remove dead logging fns + hash_meta.py", 2026-06-06) — reason: no callers. `_build_sent_meta` lost all callers when the main-log write path was eliminated. The logging current-state doc documents the deletion explicitly: "no callers".

---

## Prefix-Hash Instrumentation

`_build_sent_meta` (since the 2026-04-19 refactor in `src/proxy/hash_meta.py`, called from `addon.py`) wrote four additional fields per `sent_meta` entry:

- `prefix_hash_bp1_sys` — MD5[:10] of `json.dumps(system[0:bp1_idx+1])`
- `prefix_hash_bp2_tools` — MD5[:10] of `json.dumps({"system":..., "tools": tools[0:bp2_idx+1]})`
- `prefix_hash_bp3_msg` — MD5[:10] incl. `messages[0:bp3_idx+1]`
- `prefix_hash_bp4_msg` — MD5[:10] incl. `messages[0:bp4_idx+1]`

Serialization via `json.dumps(...).encode("utf-8")` — matched byte-for-byte what mitmproxy sends to the API wire in line 80 of `request()`.

Purpose: a byte-exact comparison of BP-prefix bytes between consecutive requests, to distinguish whether cache misses were caused by byte drift in the prefix (then visible as a hash change) or by something outside the payload (headers, account state, fingerprint — then all hashes stay the same despite the cache miss).

Usage: a dev script read `sent_meta` entries from `api_requests_*.jsonl`, comparing `prefix_hash_bp*` pairwise per request boundary.

## Granular Hash Fields + Drift Report

`_build_sent_meta` additionally wrote per-element hashes and an automatic drift report:

**Hash fields:**
- `sys_block_hashes: list[str]` — MD5[:10] per system block (index 0..N-1). Detects when a single block changes.
- `tool_hashes: list[str]` — MD5[:10] per tool. Detects tool changes (not just append at the end).
- `msg_hashes: list[dict]` — a compact message-hash array:
  - First 10 messages: `{"idx": i, "role": "user|assistant", "hash": "xxxxxxxxxx"}`
  - Middle (idx 10 to N-6): `{"idx": "10-N-6", "role": "middle", "hash": "count=K,rolling=xxxxxxxxxx"}` — rolling = MD5[:10] of the concatenated middle hashes
  - Last 5 messages: individually, like the first 10
  - At N≤15: no middle entry, everything individual
- `msg0_block_hashes: list[str]` — MD5[:10] per content block in messages[0]. Block 0 = the injected project-rules block (should be session-stable after fixation).

**Drift report:**
- `drift_report: dict` — an automatic comparison against the previous request (from `self.prev_sent_hashes_by_model`):
  - First request of the session: `{"initial": True}`
  - Subsequent requests: `{"sys": [changed_indices], "tools": [changed_indices], "msgs": [changed_indices], "msg0_blocks": [changed_indices]}`
  - `sys`: all indices with a byte change
  - `tools`: only indices < min(len(prev), len(curr)) — new tools at the end are expected, not reported
  - `msgs`: only indices < N-2 (the last 2 messages = a new turn, expected)
  - `msg0_blocks`: all indices — block 0 should always be empty after fixation

Purpose: drift in should-be-stable prefix fields becomes automatically visible per request. No manual pairwise comparison in a dev script needed. A `drift_report.sys != []` or `drift_report.msg0_blocks != [0]` after the first request is a direct signal of a fixation problem.
