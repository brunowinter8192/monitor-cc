# dev/proxy_dual_log/

## Purpose

Verification suite for the `src/logs/dual_log/` log pair written by `src/proxy/addon.py`.
Proves losslessness and self-consistency of the forwarded-delta log against the original log.

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

### diff_strip_inject.py

**Purpose:** Span-level strip/inject diff of Original vs Forwarded proxy logs. Shows what the
proxy stripped (delete spans = yellow) and injected (insert spans = green) per request. Reads
a `_original.jsonl` + `_forwarded.jsonl` pair, reconstructs the full forwarded payload from
the delta chain (per-model-family), aligns blocks (system by index, tools by name, messages
by index + within-message by block position), and classifies spans as equal / stripped /
injected using difflib. One diff delivers both colors: delete spans = stripped, insert spans = injected.

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
