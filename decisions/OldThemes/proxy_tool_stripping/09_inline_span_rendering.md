# Inline Span Rendering — Form A vs Form B Data Model

Probe step 2026-06-03. Read-only dev/ analysis — no src/ changes.

## Root Cause: Equal Spans Discarded

`logging.py._build_stripped_injected_deltas` receives the full ordered span sequence
`[(tag, text), ...]` from `diff_engine._diff_text` but stores only the stripped/injected
texts, dropping the equal spans and their ordering.

Concrete lines (logging.py):

| Location | Code | Effect |
|---|---|---|
| sys, line 300–301 | `s_texts = [t for tag, t in d["spans"] if tag == "stripped" and t]` / `i_texts = [... "injected" ...]` | equal spans dropped, ordering lost |
| msg blocks, line 355–356 | same filter pattern on `bd["spans"]` | same |
| tool desc_changes, lines 333–341 | same | same |

Consequence: the read-side has `_stripped` = list of stripped texts and `_injected` = list of
injected texts, but no equal spans and no positional order. It cannot tell which parts of the
forwarded block text are unchanged vs injected → falls back to showing full forwarded block
as gray "preview" plus injected texts again as green → **content duplication**.

## Decision Context

Four-log architecture (`_original`, `_forwarded`, `_stripped`, `_injected`) stays. No log
consolidation. Fix = enrich the stored spans so the read-side can render inline without
duplication: each part exactly once, gray=equal, yellow=stripped, green=injected.

## Candidate Forms Evaluated

### Form A — position offsets

Store each stripped/injected span with its character offset in the normalized reference text
(stripped→orig_norm, injected→fwd_norm). Read-side overlays colors at those offsets onto the
raw forwarded/original text it already holds.

### Form B — full ordered span list per log

Store the complete `[(tag, text), ...]` sequence per changed block, split across the two logs:
- `_stripped`: equal + stripped spans in order
- `_injected`: equal + injected spans in order

Equal spans are duplicated in both logs as alignment anchors.

## Probe Results (log 1780517466, 3 representative blocks)

Dev script: `dev/proxy_dual_log/span_inline_probe.py`
Report: `dev/proxy_dual_log/span_inline_probe_reports/20260603.md`

### B1 — sys[2] full-replace (REQ#3)

`diff_text` on normalized text: `[("stripped", 7471c), ("injected", 130441c)]` — ratio<0.1,
no equal spans. Form B = Form A = current format. Zero overhead (+28B tag encoding only).

### B2 — sys[3] strip-to-dot (REQ#3)

`diff_text`: `[("stripped", 5485c), ("injected", "." 1c)]` — ratio<0.1, no equal spans.
Same conclusion: Form B = current format. +28B.

### B3 — msg[8][0] word-level mixed (REQ#7)

`diff_text` on normalized text:
```
[0] (equal   , 153c  '{"tool_use_id": "toolu_...", "content": "<persisted-output>...:')
[1] (stripped, 1985c '/Users/...bs7cdmx6w.txt\n\nPreview (first 2KB):\n...')
[2] (injected, 173c  '/Users/...bs7cdmx6w.txt\n</persisted-output>",')
[3] (equal   , 18c   '"is_error": false}')
```

Inline mock: `[=]preamble  [-]long_path+preview  [+]short_path+close  [=]is_error_close`
→ each part exactly once. ✓

#### Form A empirical refutation

| Span | pos_in_fwd_norm | pos_in_fwd_raw | exact_in_raw | Verdict |
|---|---|---|---|---|
| equal[0] 153c | 0 | 0 | 0 | OK |
| stripped[1] 1985c | 154 | 154 | 154 | OK (prefix probed) |
| injected[2] 173c | 154 | 154 | 154 | OK |
| **equal[3] 18c** | **328** | **-1** | **-1** | **BROKEN** |

Trailing equal span text `'"is_error": false}'` exists in `fwd_norm_text` at char 328 but
is **NOT FOUND** (`find()` = -1) in `fwd_raw_text`. Explanation:

- `fwd_norm_text` ends with `..., "is_error": false}` (cache_control stripped by `_strip_cache_control`)
- `fwd_raw_text` ends with `..., "is_error": false, "cache_control": {"type": "ephemeral", "ttl": "1h"}}`

In raw text there is no `false}` substring: `false` is followed by `, "cache_control"`, and
the closing `}` is 52 chars later. Form A's offset 328 correctly points to the start of
`"is_error"` in both texts, but the span text length (18) overshoots the actual `}` position
in raw text — the read-side cannot use the equal span text to slice the raw text for coloring.

**Word-join gap (structural, independent of cc):** `_diff_text` produces spans via
`' '.join(words[i:j])`. System-block texts (`.text` field) are raw multi-line strings; their
words are split on `\n` and rejoined with spaces, so any word-level system-block diff produces
spans whose rejoined text ≠ the original character-for-character. For B1/B2 (ratio<0.1) the
whole original text is returned unchanged — trivially correct — but this fails for any
word-level system-block diff.

#### Form B per-log result

`_stripped` entry for this block:
```
[(equal, 153c preamble), (stripped, 1985c long_path+preview), (equal, 18c is_error_close)]
```

`_injected` entry for this block:
```
[(equal, 153c preamble), (injected, 173c short_path+close), (equal, 18c is_error_close)]
```

3-color merged sequence (read-side lock-step zip by equal anchors):
```
[(equal, 153c), (stripped, 1985c), (injected, 173c), (equal, 18c)]
```

Storage:

| Format | _stripped B | _injected B | total B | overhead |
|---|---|---|---|---|
| Current | 2032 | 179 | 2211 | baseline |
| Form B per-log | 2261 | 408 | 2669 | +21% (+458B) |
| Form B merged (hypothetical) | — | 2454 | 2454 | |

The 21% overhead is the equal context (153c prefix + 18c suffix duplicated in both logs).
For whole-block replaces (B1, B2): 0% overhead on span content, +28B tag encoding only.

## Design Tension: Per-Log Form B vs 3-Color Render

Per-log Form B gives each log 2 colors (equal + own). For the 3-color inline render the
read-side must merge both logs by equal-anchor alignment:

```
lock-step zip: advance together through equal anchors,
               emit stripped (from _stripped) then injected (from _injected) between anchors
```

Complexity for all blocks in session 1780517466: **trivial** — single anchor pair per block,
1-pass lock-step. No ambiguous interleavings observed.

When non-trivial: blocks with 3+ distinct change regions each with both strip and inject.
Merge remains well-defined by equal-anchor zip but requires the read-side to implement the
join algorithm.

**Alternative (decision needed):** store the full 3-color merged sequence in `_injected` only.
Eliminates read-side merge. Cost: `_injected` carries stripped content → breaks per-log
semantic separation (the four-log architecture user decision). Whether the merge complexity
justifies deviating from the four-log separation is an open question for the build step.

## Conclusion

**Form B chosen. Form A rejected.**

Form A rejected on empirical grounds: trailing equal span text NOT found in `fwd_raw_text`
(B3, exact numbers in table above). The read-side would need normalized offsets + normalized
text for accurate coloring — it doesn't have those; it has the raw text from `_forwarded`.

Form B is self-contained: span texts ARE the rendered content. The equal spans display as
gray context without the read-side ever needing to match them against raw text. Zero storage
overhead for whole-block replaces (the dominant case); bounded overhead for word-level diffs.

**Next step (not in this probe):** update `logging.py._build_stripped_injected_deltas` to
store the enriched per-log span lists instead of flat text lists, and migrate the read-side
(`render_sections.py`) to render from span sequences.
