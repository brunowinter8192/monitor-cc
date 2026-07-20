# Stage 1 Implementation — Inline-Span Render (Option B)

Session 2026-06-04. Implements the Option B decision from `09_inline_span_rendering.md` in src/.
Scope: system blocks, message blocks, tool-desc path. Stage 2 items (tool name-line color,
sys content-based unchanged-detection, block-level-delta visibility, marker-label cleanup) deferred.

## What We Did

### Investigation (Phase A)

Read `logging.py._build_stripped_injected_deltas`, `diff_engine._diff_text`,
`parser.accumulate_dual_log`, `render_sections.render_system_blocks`,
`render_sections.render_tools`, `render_messages.render_messages`.

Confirmed three resolution points before coding:

**1. Dedup hash adaptation**

Current `_hash_spans(texts: list)` pipes texts with `|`, used for `_stripped` (unchanged).
New `_hash_span_sequence(spans: list)` pipes `f"{tag}:{text}"` — namespace-separated so old
hashes on disk for `_injected` cannot collide with new format. Hash stability verified:
same span sequence → identical hash, different sequence → different hash.

**2. Backward-compat**

Detection: `isinstance(val[0], (list, tuple))`.
- Old format (on-disk JSONL): `["text1", "text2"]` → `val[0]` is str → old path
- New format (builder output): `[("equal","ctx"),...]` → `val[0]` is tuple → new path
- New format (after JSONL round-trip): `[["equal","ctx"],...]` → `val[0]` is list → new path

`accumulate_dual_log` in `parser.py` is format-agnostic (stores `json.loads` output directly).
No changes needed there.

Verified on 104 real `_injected.jsonl` entries from log `1780517466`: 0 false-positives.

**3. Render structure**

Three paths, same pattern:
- `isinstance(val[0], (list, tuple))` True → inline render: equal=DIM, injected=DIM_GREEN_BG, no gray preview
- Old-format or absent → gray preview + stacked yellow+green (unchanged behavior)
- `s_spans`/`s_blk`/`s_desc` (flat strings, `_stripped` format unchanged) → stacked DIM_YELLOW_BG below in both paths

**Design tension resolution** (captured also in `09_inline_span_rendering.md`):
The alternative "store full 3-color merged sequence in `_injected`" was rejected. Per-log Form B
chosen: `_stripped` stays semantically pure (flat stripped texts), `_injected` stores
`[(equal,ctx),(injected,text),...]`. No cross-log merge needed in renderer — each log renders
independently. Sent-vs-stripped visual separation preserved.

## What We Found

- `isinstance(val[0], (list, tuple))` must cover both tuples (in-memory builder output) and
  lists (JSON-deserialized). Checking only `isinstance(val[0], list)` fails for direct builder
  calls before JSONL round-trip — caught by verification script.

- `render_messages.py` has two structurally identical branches (added/modified msg-count paths).
  `replace_all=True` on the common block replaces both correctly.

- No changes to `parser.py` or `diff_engine.py` needed.

## dev/ Scripts Used

- `/tmp/verify_inline_render2.py` — one-shot throwaway, not committed. Drove B1/B3 builder
  output checks, hash stability, backward-compat against real JSONL, inline render mock.

## Decision / Next (Stage 2)

Stage 2 items per task brief:
- Tool NAME-line color (whole-injected tool header styling)
- Sys content-based unchanged-detection (replace char-count comparison with span data)
- Block-level-delta visibility (show delta indicator on changed blocks)
- Marker-label cleanup

Live-verify pending: proxy restart required before visual render in monitor TUI can be confirmed.
