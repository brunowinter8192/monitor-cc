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
  the proxy legitimately changes message count (msg0-strip).

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

**Output:** `dev/proxy_dual_log/md/span_inline_probe_<YYYYMMDD>.md`

---

### main_log_elimination_probe.py

**Purpose:** Feasibility probe for eliminating the main log (`api_requests_<id>.jsonl`).
Answers two questions on a real session using the `_forwarded` + `_original` quartet logs:

- **Question A (Forwarded reconstruction):** Accumulates `_forwarded` delta log per-model-family
  into full `{system, tools, messages}` payloads, diffs against main log `raw_payload` after
  stripping `cache_control`. Reports content losslessness, BP-count divergence table, and classifies
  every top-level payload field as: delta-covered / MUST-ADD / metadata-pane-only-irrelevant.
- **Question B (Error extraction):** Extracts `is_error=True` tool_result blocks from `_original`
  payloads, deduplicates by `tool_use_id`, compares against `tool_errors.jsonl` for the session.

Matching strategy: positional (request_ids are empty in quartet; both logs written serially).
Inlines `_strip_cache_control` + `_normalize_msg_shape_for_hash` verbatim from `src/proxy/logging.py`.

**Findings (session `opus_monitor_cc_1780602018`, 47 requests):**
- A: LOSSLESS — system/tools/messages reconstruct exactly after cache_control normalization
- A: BP-count diverges structurally (pre-ops 3 markers → post-ops grows +1/request)
- A: MUST-ADD `max_tokens` + `output_config` to `_build_forwarded_delta` for proxy-pane header fields
- B: EXACT MATCH — 1 unique error (by tool_use_id) matches tool_errors.jsonl entry

**Usage (from project root):**
```bash
MONITOR_CC_ROOT=/path/to/monitor-cc \
./venv/bin/python dev/proxy_dual_log/main_log_elimination_probe.py <session_suffix>
```

Default session: `opus_monitor_cc_1780602018`

**Output:** `dev/proxy_dual_log/md/main_log_elimination_<YYYYMMDD>.md`

---

### green_overlay_probe.py

**Purpose:** Reproduces the green-overlay false-injection bug in `_diff_text` (word-level path)
on real log data and validates the char-level candidate fix. The bug: when a JSON-serialized
tool_result block is diffed, the escaped `\n` sequences are NOT real whitespace, so tokens
containing both code content and `<system-reminder>…` are treated as single words by `.split()`.
SequenceMatcher tags them as 'replace' → common prefix `set()))\n\n` mis-tagged as stripped
(yellow) AND injected (green). Only `<system-reminder>…` was actually stripped.

Implements both variants inline (self-contained, no `src/` imports at module level):
- `diff_text_word` — exact copy of production `_diff_text` (word-level path)
- `diff_text_char` — candidate fix: char-level SequenceMatcher, keeps early-exit branches

Also runs 4 regression cases (R1–R3 real logs ratio >= 0.1; R4 synthetic whitespace-collapse
test) to confirm no span explosion and correct whitespace fidelity.

**Key findings (2026-06-05, session `badge-recap_1780678180`):**
- Bug case: word=4 spans (common prefix `set()))\n\n` wrongly split), char=6 spans (280-char
  common prefix correctly equal ✅, `<system-reminder>` stripped ✅, fidelity ✅)
- R1 (ratio=0.76): word=4, char=6 — no explosion
- R2 (ratio=0.99): word=3, char=3 — identical span count
- R3 (ratio=0.95): word=4, char=3 — char fewer spans ✅
- R4 synthetic whitespace: word collapses `  ` / `\t` / `   ` to single space; char preserves exactly ✅
- All 4 regression fidelity checks: orig_ok=True fwd_ok=True ✅

**Usage (from project root):**
```bash
./venv/bin/python dev/proxy_dual_log/green_overlay_probe.py
```

**Output:** `dev/proxy_dual_log/md/green_overlay_probe.md`

---

### groundtruth_message_spans_probe.py

**Purpose:** Validates `build_message_spans(orig_text, fwd_text, stripped_chunks)` — the
ground-truth span construction algorithm that replaces the blind `_diff_text` for messages.
Instead of diffing, builds spans from the exact stripped chunks recorded by
`apply_modification_rules` (`stripped_msg_removed`): split `orig_text` at chunk positions →
EQUAL + STRIPPED segments; walk `fwd_text` matching EQUALs; gaps in `fwd_text` = INJECTED
(the real replacement placeholder, if any). Proves: zero phantom green on pure-strip cases,
lossless fidelity (equal+stripped rebuilds orig, equal+injected rebuilds fwd), and correct
small injected spans for replace cases (`.` placeholder, wake-up text).

Data source: re-runs `apply_modification_rules` on `_original` dual-log payloads to regenerate
`stripped_msg_removed`; validates mod payload == fwd delta per case. Operates at inner-content
level (`block["text"]` / `block["content"]`) rather than `json.dumps(block)` — JSON structural
chars (`"is_error": false}`) are never coloured.

**Key findings (2026-06-05):**
- BUG case msg[18] blk[0] tool_result SR strip: GT 0 phantom ✅; diff_text_word at production
  JSON level: injected phantom `set()))\\n\\n",` ❌
- TEXT_REPLACE DEF-SR → `.`: GT injected=`.` correct small ✅; fidelity ✅
- BG_REPLACE TN→wakeup: GT injected=`background done…` correct small ✅; fidelity ✅
- LARGE_SR 5777-char: precision gap — trailing `\n` not in stripped_chunks; `fwd_ok=False`
- Recording gaps: ENV-context SR and trailing `\n` not captured in `stripped_msg_removed`

**Usage (from project root):**
```bash
./venv/bin/python dev/proxy_dual_log/groundtruth_message_spans_probe.py
```

**Output:** `dev/proxy_dual_log/md/groundtruth_spans_<YYYYMMDD_HHMMSS>.md`

---

### composition_probe.py

**Purpose:** Proves multi-pass span composition over C0. Models each proxy pass as an
`Op(offset_in_Ck, removed, injected)` derived from the pass's `(before, after)` block-text
pair via common-prefix/suffix. Composes all passes into a single span list over C0 by walking
the accumulated `(equal/stripped/injected)` span list and applying each op — "equal" bytes in
the removal range become "stripped"; prior "injected" bytes re-removed disappear. Models
`_dedup_wakeup_blocks` as a final composed op (Layer-1 payload modification, not a span-build hack).

**Stage 1A wiring:** `_REAL_OPS_PASSES = frozenset({"po_preview", "hook_prefix", "git_lock", "bd_noise"})` — for these 4 passes the probe reads `result[5]` (directly-recorded ops from `src/proxy/rules.py`) instead of the `(before, after)` stand-in. Remaining passes still use the stand-in; both paths verified byte-exact.

**Proved (9509/9509 blocks, 567 entries, 5 stems — 2026-06-09 with Stage 1A ops):**
- Both reconstruction invariants byte-exact: `equal+stripped == C0`, `equal+injected == Cfwd`
- 1134 multi-pass blocks (same block, ≥2 passes) — all pass
- 772 double-inject blocks — dedup op correctly reduces each to 1 injected wakeup
- Money shot (msg[100] TN+BG double-inject): span list = 1 stripped (full TN block) +
  1 injected wakeup; Cfwd (48 chars) reconstructed byte-exact from C0 (406 chars)

**Usage (from project root):**
```bash
./venv/bin/python dev/proxy_dual_log/composition_probe.py
```

**Output:** `dev/proxy_dual_log/md/composition_probe_<YYYYMMDD>.md`

---

### attribution_coverage.py

**Purpose:** Read-only function-attribution coverage analysis for `_stripped`/`_injected` dual-logs.
Answers: can every strip AND inject entry be attributed to a responsible proxy function?
Processes all available `*_stripped.jsonl`/`*_injected.jsonl` pairs in `src/logs/dual_log/`
and produces a coverage report with per-category attribution tables, RAW/ADJUSTED coverage
percentages, full residual listing, and false-positive evidence.

Key findings from first run (19 pairs, 2026-06-04):
- Strip ADJUSTED 100% / Inject ADJUSTED 100% — zero truly unattributed entries
- 6 residual gap categories in strip_vocab (ENV/HP/UI_PARTIAL/DATE_SR/SN/FM) — all attributable,
  need vocab additions before `fn` field can be materialised
- **json_reserialization bug**: 409 false positive entries from `_set_cache_breakpoints`
  format-normalisation not being mirrored in `_build_stripped_injected_deltas` diff setup;
  renders as false yellow/green in the monitor

Loads `strip_vocab` via `importlib.util.spec_from_file_location` (block_dev_imports_src safe).
Auto-detects main repo vs worktree path for dual_log directory.

**Usage (from project root):**
```bash
./venv/bin/python dev/proxy_dual_log/attribution_coverage.py
```

**Output:** `dev/proxy_dual_log/md/attribution_coverage_<YYYYMMDD>.md`
