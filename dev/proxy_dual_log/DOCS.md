# dev/proxy_dual_log/

## Purpose

Verification suite for the `src/logs/dual_log/` log quartet written by `src/proxy/addon.py`.
Proves losslessness and self-consistency of the forwarded-delta log against the original log,
and completeness of the strip/inject diff engine (`src/proxy/diff_engine.py`).

## Modules

### verify_delta.py

**Purpose:** Reads a `_original.jsonl` + `_forwarded.jsonl` pair, reconstructs the full forwarded
payload from the delta stream (per-model-family chain), and verifies two invariants:

- **Check 1 (hard):** Reconstructed element counts == counts declared in the delta entry. Pure
  delta self-consistency — must always hold. Violation = delta-builder bug → exit 1 + FAIL.
- **Check 2 (soft diagnostic):** `forwarded counts.messages` vs message count in the original.
  Mismatches are reported with context (request, delta indices, diff) but do NOT fail the script —
  the proxy legitimately changes message count (msg0-strip, sidecar path).

Output: per-request table (line, request_id, family, is_first, sys/tools/msgs counts, delta KB,
status, delta indices) + PASS/FAIL summary line.

**Usage (from project root):**
```bash
./venv/bin/python dev/proxy_dual_log/verify_delta.py \
    src/logs/dual_log/api_requests_<id>_original.jsonl \
    src/logs/dual_log/api_requests_<id>_forwarded.jsonl
```

**CLI flags:**

| Flag | Description |
|---|---|
| `original` (positional) | Path to `_original.jsonl` |
| `forwarded` (positional) | Path to `_forwarded.jsonl` |
| `--original` | Named alternative for original path |
| `--forwarded` | Named alternative for forwarded path |

**Exit codes:** 0 = all hard checks passed (soft mismatches possible); 1 = at least one hard-fail.

---

### verify_strip_inject.py

**Purpose:** Completeness proof for the strip/inject diff engine (`src/proxy/diff_engine.py`).
Simulates `_build_stripped_injected_deltas` on every request pair from a real `_original` +
`_forwarded` log and verifies three hard checks per request:

- **Check 1 (span reconstruction):** For every block where `orig_text != fwd_text`, spans
  produced by the engine reconstruct `orig_text` from (equal + stripped) and `fwd_text` from
  (equal + injected). Failure = `_diff_text` lost content.
- **Check 2 (field coverage):** Every non-collection top-level field that differs between
  original and forwarded appears in `fields_delta`. Failure = field-level modification (e.g.
  model override) silently omitted.
- **Check 3 (model cross-check):** `injected fields_delta["model"]` (if present) matches the
  `model` field on the `_forwarded` delta entry for the same request.

**Verified:** PASS 46/46 on `api_requests_opus_monitor_cc_1780497198` (historical log data).
Live proxy writing `_stripped`/`_injected` during a real session: pending user test session.

Imports `src.proxy.diff_engine` and `src.proxy.logging` via `sys.path.insert(0, parents[2])`.

**Usage (from project root):**
```bash
./venv/bin/python dev/proxy_dual_log/verify_strip_inject.py \
    src/logs/dual_log/api_requests_<id>_original.jsonl \
    src/logs/dual_log/api_requests_<id>_forwarded.jsonl
```

**CLI flags:**

| Flag | Description |
|---|---|
| `original` (positional) | Path to `_original.jsonl` |
| `forwarded` (positional) | Path to `_forwarded.jsonl` |
| `--original` | Named alternative for original path |
| `--forwarded` | Named alternative for forwarded path |

**Exit codes:** 0 = all 3 checks passed for all requests; 1 = at least one hard-fail.

---

### diff_strip_inject.py

**Purpose:** Span-level strip/inject diff of Original vs Forwarded proxy logs. Shows what the
proxy stripped (delete spans = yellow) and injected (insert spans = green) per request. Reads
a `_original.jsonl` + `_forwarded.jsonl` pair, reconstructs the full forwarded payload from
the delta chain (per-model-family), aligns blocks (system by index, tools by name, messages
by index + within-message by block position), and classifies spans as equal / stripped /
injected using difflib. One diff delivers both colors: delete spans = stripped, insert spans = injected.

Engine imported from `src/proxy/diff_engine.py` (via `sys.path.insert` — same engine used by
the runtime `_build_stripped_injected_deltas` in `logging.py`).

**Diff strategy:** Word-level when `SequenceMatcher.ratio() >= 0.1` (partial edits, e.g. a
cache_control suffix appended to a 55k base64 block — ratio ≈ 1.0, only the last few words
change). Whole-block 2-span replacement when `ratio < 0.1` (full replacements, e.g. sys[2]:
CC system prompt → proxy rules, ratio ≈ 0.004 — word-level would produce thousands of trivial
word-spans with zero information gain).

**Output:** Per-request sections with system / tools / messages blocks, per-block IDENTICAL /
REPLACED / STRIPPED / INJECTED tags, char counts, previews (120 chars), and a SPANS summary
line per request.

**Usage (from project root):**
```bash
./venv/bin/python dev/proxy_dual_log/diff_strip_inject.py \
    src/logs/dual_log/api_requests_<id>_original.jsonl \
    src/logs/dual_log/api_requests_<id>_forwarded.jsonl
```

**CLI flags:**

| Flag | Description |
|---|---|
| `original` (positional) | Path to `_original.jsonl` |
| `forwarded` (positional) | Path to `_forwarded.jsonl` |
| `--original` | Named alternative for original path |
| `--forwarded` | Named alternative for forwarded path |

---

### span_inline_probe.py

**Purpose:** Form A vs Form B inline-render data model probe. Validates that Form B (full
ordered span list per log) is the minimal enrichment that lets the read-side render
strip/inject inline without content duplication. Shows Form A's empirical failure via concrete
offset/substring mismatches on real data. Probes 3 blocks: sys[2] full-replace, sys[3]
strip-to-dot, and a word-level message block with cache_control diff.

Key finding: trailing equal span `'"is_error": false}'` from normalized diff NOT found in
`fwd_raw_text` (exact_in_raw=-1) — Form A's offset/text unusable as raw-text anchor.
Form B stores equal+stripped in `_stripped`, equal+injected in `_injected`; 3-color render
= read-side lock-step zip by equal anchors (trivial for all patterns in session 1780517466).

Imports `diff_engine._diff_text` via `importlib` (standalone load, no src/ package import).
Inlines `_strip_cache_control` (5-line mirror of `logging.py:_strip_cache_control`).

**Usage (from project root):**
```bash
./venv/bin/python dev/proxy_dual_log/span_inline_probe.py
```

**Output:** `dev/proxy_dual_log/span_inline_probe_reports/<YYYYMMDD>.md`
