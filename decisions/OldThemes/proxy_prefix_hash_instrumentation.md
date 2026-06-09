# Proxy Prefix-Hash Instrumentation (Removed)

Demoted from `decisions/pipe05_proxy_cache.md` IST — feature built, shipped, then removed as dead code.

**Built:** commit `feat/prefix-hash-instrumentation` (2026-04-19 refactor, `_build_sent_meta` in `src/proxy/hash_meta.py`, called from `addon.py`)
**Removed:** commit `e2af735` ("Block A: remove dead logging fns + hash_meta.py", 2026-06-06) — reason: no callers. `_build_sent_meta` lost all callers when main-log write path was eliminated. `decisions/logging.md:111` documents the deletion explicitly: "no callers".

---

## Prefix-Hash Instrumentation

`_build_sent_meta` (seit Refactor 2026-04-19 in `src/proxy/hash_meta.py`, aufgerufen aus `addon.py`) schreibt vier zusätzliche Felder pro `sent_meta`-Entry:

- `prefix_hash_bp1_sys` — MD5[:10] von `json.dumps(system[0:bp1_idx+1])`
- `prefix_hash_bp2_tools` — MD5[:10] von `json.dumps({"system":..., "tools": tools[0:bp2_idx+1]})`
- `prefix_hash_bp3_msg` — MD5[:10] inkl. `messages[0:bp3_idx+1]`
- `prefix_hash_bp4_msg` — MD5[:10] inkl. `messages[0:bp4_idx+1]`

Serialisierung via `json.dumps(...).encode("utf-8")` — matcht byte-genau was mitmproxy in Zeile 80 von `request()` ans API-Wire schickt.

Zweck: Byte-genauer Vergleich von BP-Prefix-Bytes zwischen aufeinanderfolgenden Requests, um zu unterscheiden ob Cache-Misses durch Byte-Drift im Prefix (dann sichtbar als Hash-Änderung) oder durch etwas außerhalb des Payloads (Header, Account-State, Fingerprint — dann alle Hashes gleich trotz Cache-Miss) verursacht werden.

Nutzung: Dev-Script liest `sent_meta`-Einträge aus `api_requests_*.jsonl`, vergleicht paarweise `prefix_hash_bp*` pro Request-Boundary.

## Granular Hash Fields + Drift Report

`_build_sent_meta` schreibt zusätzlich pro-Element-Hashes und einen automatischen Drift-Report:

**Hash-Felder:**
- `sys_block_hashes: list[str]` — MD5[:10] pro System-Block (Index 0..N-1). Erkennt wenn ein einzelner Block sich ändert.
- `tool_hashes: list[str]` — MD5[:10] pro Tool. Erkennt Tool-Änderungen (nicht nur Append am Ende).
- `msg_hashes: list[dict]` — Kompaktes Message-Hash-Array:
  - First 10 Messages: `{"idx": i, "role": "user|assistant", "hash": "xxxxxxxxxx"}`
  - Middle (idx 10 bis N-6): `{"idx": "10-N-6", "role": "middle", "hash": "count=K,rolling=xxxxxxxxxx"}` — rolling = MD5[:10] der verketteten middle-Hashes
  - Last 5 Messages: einzeln wie first 10
  - Bei N≤15: kein middle-Eintrag, alles einzeln
- `msg0_block_hashes: list[str]` — MD5[:10] pro Content-Block in messages[0]. Block 0 = injizierter project-rules Block (sollte nach Fixation session-stabil sein).

**Drift-Report:**
- `drift_report: dict` — Automatischer Vergleich gegen vorherigen Request (aus `self.prev_sent_hashes_by_model`):
  - Erster Request der Session: `{"initial": True}`
  - Folge-Requests: `{"sys": [geänderte_indices], "tools": [geänderte_indices], "msgs": [geänderte_indices], "msg0_blocks": [geänderte_indices]}`
  - `sys`: alle Indices mit Byte-Änderung
  - `tools`: nur Indices < min(len(prev), len(curr)) — neue Tools am Ende sind expected, werden nicht gemeldet
  - `msgs`: nur Indices < N-2 (letzte 2 Messages = neuer Turn, expected)
  - `msg0_blocks`: alle Indices — Block 0 sollte nach Fixation immer leer sein

Zweck: Drift in should-be-stable Prefix-Feldern wird automatisch pro Request sichtbar. Kein manuelles Pairwise-Vergleichen im Dev-Script nötig. Ein `drift_report.sys != []` oder `drift_report.msg0_blocks != [0]` nach dem ersten Request ist ein direktes Signal für ein Fixation-Problem.
