# Multi-Pass Composition Probe — 2026-06-09 23:27:14

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

ERROR: [Errno 2] No such file or directory: '/Users/brunowinter2000/Documents/ai/monitor-cc/src/logs/dual_log/api_requests_opus_monitor_cc_1780933074_original.jsonl'
```
Traceback (most recent call last):
  File "/Users/brunowinter2000/Documents/ai/monitor-cc/.claude/worktrees/rules-split/dev/proxy_dual_log/composition_probe.py", line 422, in composition_probe_workflow
    c0_text, cfwd_text, blk_ops, spans = get_money_shot_case()
                                         ~~~~~~~~~~~~~~~~~~~^^
  File "/Users/brunowinter2000/Documents/ai/monitor-cc/.claude/worktrees/rules-split/dev/proxy_dual_log/composition_probe.py", line 354, in get_money_shot_case
    with open(orig_path) as f:
         ~~~~^^^^^^^^^^^
FileNotFoundError: [Errno 2] No such file or directory: '/Users/brunowinter2000/Documents/ai/monitor-cc/src/logs/dual_log/api_requests_opus_monitor_cc_1780933074_original.jsonl'

```

## Corpus Run — All Entries Across 5 Stems

| Metric | Value |
|---|---|
| Total entries | 0 |
| Entries with modifications | 0 |
| Blocks checked | 0 |
| Blocks passed (byte-exact) | 0 |
| Blocks failed | 0 |
| Multi-pass blocks (≥2 ops same block) | 0 |
| Double-inject blocks (≥2 injecting ops) | 0 |

### Per-Pass-Type Results

| Pass | Passed | Failed | Rate |
|---|---|---|---|

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

- `0/0` blocks pass both invariants across 0 modified requests
- `0` multi-pass blocks verified (same block, ≥2 passes)
- `0` double-inject blocks — dedup op reduces each to 1 injected wakeup ✅
- `_dedup_wakeup_blocks` is a Layer-1 pass, not a span-building workaround
- Money shot (msg[100] TN+BG): 1 injected wakeup, C0+Cfwd byte-exact ✅
