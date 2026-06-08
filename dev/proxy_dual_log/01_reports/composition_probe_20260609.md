# Multi-Pass Composition Probe — 2026-06-09 00:36:23

Validates: per-pass ops `(offset_in_Ck, removed, injected)` composed via span-list
accumulation produce byte-exact reconstruction of both C0 and Cfwd.

**Invariants per block:**
- Inv1: `"".join(equal+stripped) == C0_block_text`
- Inv2: `"".join(equal+injected) == Cfwd_block_text`

**Op extraction**: common-prefix/suffix on each pass's `(before_pass, after_pass)`
block-text pair. Stand-in for what production passes would record directly.
Validated by the invariants — a fail implicates op extraction, not the algorithm.

**Layer clarification:** `_dedup_wakeup_blocks` is a Layer-1 payload modification
(changes what gets forwarded). Modeled here as a composed op. There is NO separate
dedup in the span-building path — the composition already reflects reality after dedup.

## Money Shot — msg[100] TN+BG Double-Inject

**Confirmed production bug.** C0 = one TN block containing a failed-BG `<summary>`.
Pass chain: `_apply_first_pass` strips TN wrapper + injects wakeup → reveals BG line;
`_apply_bg_exit_strip` strips BG line + injects wakeup again;
`_dedup_wakeup_blocks` removes second wakeup from Cfwd.
Composition must produce exactly ONE injected wakeup (= Cfwd byte-exact).

**C0** (406 chars): `'<task-notification>\n<task-id>bpvcpkcx3</task-id>\n<tool-use-id>toolu_01CNJDFzyJ9HWQHvzNtM9Z7z</tool-u'...`
**Cfwd** (48 chars): `'background done — check worker or other process\n'`

**Op chain (derived from per-pass before→after):**
- `first_pass` offset=0 removed='<task-notification>\n<task-id>bpvcpkcx3</task-id>\n<tool-use-i' injected='Background command "sleep 600 &amp;&amp; echo done" failed w'
- `bg_exit` offset=0 removed='Background command "sleep 600 &amp;&amp; echo done" failed w' injected='background done — check worker or other process\nbackground d'
- `dedup_wakeup` offset=48 removed='background done — check worker or other process' injected=''

**Composed span list over C0:**
```
  ('stripped'  , '<task-notification>\n<task-id>bpvcpkcx3</task-id>\n<tool-use-id>toolu_01CNJDFzyJ9H'...)
  ('injected'  , 'background done — check worker or other process\n')
```

- Injected wakeup spans: **1** ✅ exactly 1 — double-inject FIXED
- Stripped spans: 1 (full TN block shown as yellow ✅)
- Inv1 C0 recon:   ✅ PASS
- Inv2 Cfwd recon: ✅ PASS
- **Overall: ✅ BYTE-EXACT**

## Corpus Run — All Entries Across 5 Stems

| Metric | Value |
|---|---|
| Total entries | 567 |
| Entries with modifications | 559 |
| Blocks checked | 9509 |
| Blocks passed (byte-exact) | 9509 |
| Blocks failed | 0 |
| Multi-pass blocks (≥2 ops same block) | 1134 |
| Double-inject blocks (≥2 injecting ops) | 772 |

### Per-Pass-Type Results

| Pass | Passed | Failed | Rate |
|---|---|---|---|
| `bg_exit` | 772 | 0 | 100% |
| `cumulative_sr` | 1277 | 0 | 100% |
| `dedup_wakeup` | 772 | 0 | 100% |
| `final_sr` | 99 | 0 | 100% |
| `first_pass` | 7258 | 0 | 100% |
| `hook_prefix` | 418 | 0 | 100% |
| `po_preview` | 619 | 0 | 100% |

**No failing cases — all blocks pass both invariants byte-exact ✅**

## Op Shape Per Pass (Port Guidance)

What each production pass would emit directly (instead of probe's stand-in):

| Pass | Op shape at recording point | Notes |
|---|---|---|
| `_apply_first_pass` (SR strips) | `Op(blk_idx, sr_offset, SR_block, '.')` | '.' is proxy placeholder |
| `_apply_first_pass` (TN transform) | `Op(blk_idx, prefix_len, changed_region, new_region)` | common-prefix/suffix of full content; TN strips XML wrapper while keeping inner text — not a clean strip |
| `_apply_cumulative_sr_strips` | `Op(blk_idx, offset, SR_block, '.')` per SR | multiple ops if multiple SRs in one string |
| `_apply_final_sr_pass` | same as cumulative | |
| `_apply_bg_exit_strip` | `Op(blk_idx, match_offset, bg_line+'\n', _WAKEUP_TEXT)` first; `Op(blk_idx, offset, bg_line, '')` subsequent | injected only on first match |
| `_apply_po_preview_strip` | `Op(blk_idx, offset, preview_section, '')` | pure strip |
| `_apply_hook_prefix_strip` | `Op(blk_idx, 0, prefix_text, '')` | prefix at block start |
| `_apply_git_lock_strip` | `Op(blk_idx, offset, lock_advice, '')` | pure strip |
| `_apply_bd_noise_strip` | `Op(blk_idx, offset, bd_line, '')` | pure strip |
| `_dedup_wakeup_blocks` | `Op(blk_idx, offset_2nd+, wakeup, '')` | run AFTER all passes; Layer-1 payload op, NOT a span-building hack |

## Verdict

**Multi-pass composition: HOLDS BYTE-EXACT on all corpus data**

- `9509/9509` blocks pass both invariants across 559 modified requests
- `1134` multi-pass blocks verified (same block, ≥2 passes)
- `772` double-inject blocks — dedup op reduces each to 1 injected wakeup ✅
- `_dedup_wakeup_blocks` is a Layer-1 pass, not a span-building workaround
- Money shot (msg[100] TN+BG): 1 injected wakeup, C0+Cfwd byte-exact ✅
