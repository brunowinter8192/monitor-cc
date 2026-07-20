# 16 — Operation-Transcript Redesign of the Strip/Inject Span Logs (2026-06-08)

Status: **Stages 1–4 CODE-COMPLETE; LIVE-VERIFY pending (proxy restart required).** Supersedes the patch-on-patch approach of the `_diff_text` fallback + `_dedup_wakeup_blocks` for the `_stripped`/`_injected` span construction.

## Origin

Two live proxy-pane bugs (issue #5 bundle), both surfaced 2026-06-08:
- **Green-overlay false-injection** — unchanged content rendered green (injected). Documented arc: `14_green_overlay_false_injection.md`.
- **bg-exit double-inject** — `_WAKEUP_TEXT` rendered green TWICE on a single bg-exit block (user screenshot "doppelt der inj gerendert").

## Layer diagnosis (the key reframing)

An API exchange through the proxy has three layers. Mapping the bugs to a layer settled the whole approach:

| Layer | What it is | State |
|---|---|---|
| 1. What the proxy actually SENDS | the forwarded payload | **correct** — verified: bg-exit forwarded content carries `_WAKEUP_TEXT` exactly once (per-message count = 1 across the corpus) |
| 2. What gets WRITTEN to the logs | the derived `_stripped`/`_injected` span deltas | **WRONG** — double-records the injection / phantom-tags unchanged content |
| 3. What the monitor SHOWS | the renderer | **correct** — faithfully renders whatever spans Layer 2 wrote |

Both bugs live in **Layer 2** — the derived span log. Layer 1 (the real send) is right; Layer 3 (render) faithfully shows wrong Layer-2 data. The renderer was never the bug (confirmed in `14`).

## Why the current Layer-2 derivation fails

The passes record text CHUNKS keyed by message index (`pass_removed_by_idx[idx] = [chunks]` in `rules.py`) — **no position, no operation order**. The span builder (`build_message_spans` / `_diff_text` in `diff_engine.py`) then RE-SEARCHES for chunk positions at build time (`fwd_text.find(chunk)`). That search is the bug surface: it finds the same chunk twice (double-inject) or, when no chunk is recorded, falls back to word-level `_diff_text` which mis-tags a shared JSON-structural prefix as injected (phantom). `_dedup_wakeup_blocks` is a patch on top of the double; the diff-fallback is a patch on top of the missing record. Patch-on-patch: fix one mole, the next pops up.

## The new model — operation transcript

Record each modification as a POSITION-ANCHORED operation at the moment the pass acts; compose all operations across passes into one span list over the original — deterministically. Three pillars:

1. **Position-anchored op records**, not text chunks. Each modification site emits `(block_idx, offset, removed_text, injected_text)`. The function knows the position — it found its target via regex at a concrete offset.
2. **Deterministic composition, no diff/dedup/fallback.** Compose the per-pass ops into a span list over the original. No re-search, no post-hoc dedup — each op is recorded once with its position.
3. **Reconstruction invariant as a TEST (not a runtime net).** `original + recorded ops == forwarded`, asserted over a real corpus, kept as a CI regression test.

## No runtime fallback — the decisive design stance

The user's hard constraint (and correct): the current bugs ARE caused by the fallbacks (`_diff_text`, `_dedup`). Adding a new runtime fallback repeats the mistake. Resolution:

- **Completeness is a CODE property, not an INPUT property.** Modifications happen at a finite, enumerable set of code sites. New input can only trigger an EXISTING (recorded) site or no modification (correctly equal). Input cannot manufacture an unrecorded modification. So completeness is verifiable EXHAUSTIVELY, not hoped for.
- The reconstruction invariant lives in **dev/ + CI test**, not production. A failure there = a code site that mutates without recording = fix the site. The test IS the guarantee; it catches future code that forgets to record.
- **Production runs one way.** Deterministic composition from records. No `_diff_text`, no `_dedup`, no "best-effort". The only residual case — a future code change adding a mutation without a record — is caught by the CI invariant, NOT a runtime branch.
- **Fallback vs tripwire (the line that matters):** a *fallback* produces alternative output by a second method (hides failure behind plausible-wrong output) → eliminate. A *tripwire/assertion* refuses to produce output and surfaces the failure → legitimate, never guesses. The redesign keeps zero fallbacks; any retained check is a tripwire.
- **Anti-pattern named:** proving the one-way path in dev/ and then STILL shipping a runtime fallback "just in case" = distrusting the proof = re-introducing the hell. If the dev/ proof holds and the invariant is in CI, production needs no fallback.

(This stance was generalized into the refactor skill: `Meta/iterative-dev/.../iterative-dev-refactor/SKILL.md` § 2.8 Silent-Fallback Scan + § One-Way Redesign Evaluation companion.)

## Composition algorithm + proof (dev/ probe, validated)

Algorithm (worker `composition-probe`): per block a span list `[(tag, text)]`, `tag ∈ {equal, stripped, injected}`, initialized `[("equal", C0)]`. Two invariants maintained after every op:
- `equal+stripped == C0` (original reconstruction)
- `equal+injected == Ck` (current content)

Applying op `(offset_in_Ck, removed, injected)`: walk the list tracking a Ck-cursor (stripped spans don't advance it); equal bytes in the removal range → stripped; injected bytes in the removal range → disappear; insert `("injected", injected)` at the splice point. The dual invariant solves the multi-pass offset-rebasing implicitly — the span list carries original AND current content simultaneously, so each new op's Ck-offset maps onto the structure without explicit rebasing.

**`_dedup_wakeup_blocks` is a Layer-1 payload op** (it changes what gets forwarded — Cfwd has one wakeup), modeled as a composed op `Op(offset_2nd, wakeup, '')`, NOT a span-building hack. There is no separate dedup in the span path.

**Proof** (dev/proxy_dual_log/composition_probe.py + 01_reports/composition_probe_20260608.md): **7219/7219 blocks byte-exact** across 484 modified requests / 492 entries / 5 stems. 676 multi-pass blocks, 480 double-inject blocks — all pass both invariants. Per-pass-type: first_pass 5499, cumulative_sr 1030, bg_exit 480, dedup_wakeup 480, po_preview 373, hook_prefix 320, final_sr 75 — all 100%. Money shot msg[100] (TN+BG double): composes to exactly ONE injected wakeup, C0(406)+Cfwd(48) byte-exact → double-inject FIXED by the model.

The report's **Op-Shape-Per-Pass table is the src/ port spec** — what each pass must record directly instead of the probe's `(before,after)` stand-in.

## Staged src/ Port

### ✅ Stage 1A — DONE (2026-06-09)

4 pure-strip passes migrated to position-anchored op recording in `src/proxy/rules.py`:
`_apply_po_preview_strip`, `_apply_hook_prefix_strip`, `_apply_git_lock_strip`, `_apply_bd_noise_strip`.

Each pass: initialises `pass_ops_by_msg_blk: dict = {}`, calls `_ops_from_content_change(old_content, new_content)` at its mutation site, returns it as 6th value. `apply_modification_rules` unpacks the 6th return for each of the 4 passes and merges into `_all_ops` (via `_merge_ops`) — additive only, 7-tuple intact, `_all_ops` not yet returned (Stage-2 hook point).

`composition_probe.py` wired with `_REAL_OPS_PASSES = frozenset({"po_preview", "hook_prefix", "git_lock", "bd_noise"})` — reads `result[5]` directly for these 4; stand-in path for the rest.

**Corpus (2026-06-09):** 9509/9509 blocks byte-exact across 567 entries / 559 modified / 5 stems. Both invariants hold. All per-pass-type rates 100%.

### ✅ Stage 1B — DONE (2026-06-09)

`_apply_bg_exit_strip` + `_dedup_wakeup_blocks` migrated.

`_apply_bg_exit_strip`: same 6th-return pattern as 1A — `pass_ops_by_msg_blk` init, `_ops_from_content_change(old_content, new_content)` at mutation site, 6th return, `_merge_ops` in orchestrator. `bg_exit` added to `_REAL_OPS_PASSES` in probe.

`_dedup_wakeup_blocks`: signature changed `list` → `tuple` — returns `(new_messages, ops_by_msg_blk)`. Records op per changed message via `_ops_from_content_change`; caller (`apply_modification_rules`) unpacks tuple + `_merge_ops`. Probe dedup block replaced with direct tuple-unpack of the real return — no stand-in.

**Corpus (2026-06-09):** 9509/9509 byte-exact. Money-shot msg[100] TN+BG: injected wakeup spans = **1** ✅ double-inject FIXED at recording level. 772 double-inject blocks all pass.

### ✅ Stage 1C — DONE (2026-06-09)

`_apply_cumulative_sr_strips` + `_apply_final_sr_pass` migrated. Same 6th-return pattern. `cumulative_sr` records op from `original_before_pass` → final `content` after all inner SR strips (one `_ops_from_content_change` call covers the composed multi-strip). `final_sr` records `_ops_from_content_change(old_content, new_content)`. Both added to `_REAL_OPS_PASSES`. Corpus 9509/9509, cumulative_sr 1277/0, final_sr 99/0.

### ✅ Stage 1D — DONE (2026-06-09) — **Stage 1 COMPLETE**

`_apply_first_pass` migrated — all 7 branches covered: plan-mode strip, plan-mode else (full placeholder replace), TN-transform (XML wrapper strip + wakeup append → list content), task-tools-nag, deferred-tools, user-interrupt, rejection. Each branch records `_ops_from_content_change(old_content, new_msg["content"])` inside its `if changed` guard. `first_pass` added to `_REAL_OPS_PASSES` — all passes now real, zero stand-in remaining.

**Full-proof corpus (2026-06-09):** 9509/9509 blocks byte-exact, both invariants. `first_pass` 7258/0 100%. Money-shot msg[100] TN+BG: injected wakeup spans = **1** ✅ with `first_pass` real.

## Stage 1 — Implementation Plan (for Sub-Stage Workers)

Self-contained reference for 1C/1D workers. Pattern established in 1A+1B.

### Data structure

6th return value on every pass function:
```python
pass_ops_by_msg_blk: dict  # {msg_idx: {blk_idx: [(offset, removed, injected)]}}
```
Orchestrator (`apply_modification_rules`) accumulates via `_merge_ops(dst, src)` into `_all_ops: dict = {}`. `_all_ops` is NOT returned — Stage-2 hook point only. Production 7-tuple intact, change is purely additive.

`_dedup_wakeup_blocks` is a special case: signature changed to return `(new_messages, ops_by_msg_blk)` — caller unpacks tuple directly, no 5-tuple unpacking pattern.

### Recording method

`_ops_from_content_change(old_content, new_content) -> dict`
- str content: calls `_extract_block_op(before, after)` → 1 op per block, keyed `{0: [(off, rem, inj)]}`
- list content: iterates blocks, calls `_extract_block_op` per block pair
`_extract_block_op` uses common-prefix/suffix scan → minimal single op `(offset, removed, injected)` per block. Returns `[]` on no change.

Call site: immediately after `result.append({**msg, "content": new_content})` at the mutation site:
```python
pass_ops_by_msg_blk[idx] = _ops_from_content_change(old_content, new_content)
```

### Probe wiring (`dev/proxy_dual_log/composition_probe.py`)

`_REAL_OPS_PASSES` final (after 1D): `frozenset({"po_preview", "hook_prefix", "git_lock", "bd_noise", "bg_exit", "cumulative_sr", "final_sr", "first_pass"})` — **all 8 passes real, no stand-in remaining**. Pass loop reads `result[5]` for every pass. Dedup unpacks `_dedup_wakeup_blocks(current)` as `(after_dedup, dedup_ops)` and iterates `dedup_ops` directly.

**Full proof (2026-06-09):** 9509/9509 byte-exact. Money-shot msg[100] = 1 injected wakeup ✅.

### Per-pass op shapes

See `Op Shape Per Pass` table in `dev/proxy_dual_log/01_reports/composition_probe_20260609.md`. Defines exactly what each pass records at its mutation site.

## ✅ Stage 2 — Consumer Switch COMPLETE (2026-06-09)

Three sub-stages shipped as three commits:

**Stage 2A** (`stage2A: port compose_block to diff_engine`): `apply_edit_to_spans` + `compose_block` ported byte-faithfully from probe to `src/proxy/diff_engine.py`. Production ops are 3-tuples `(offset, removed, injected)` — unpacking adjusted accordingly (no pass_name). Acceptance: import clean.

**Stage 2B** (`stage2B: thread _all_ops to flow.metadata`): `apply_modification_rules` now returns 8-tuple (`_all_ops` as 8th element, both return paths). `addon.py` `request()` unpacks 8th value + stashes `flow.metadata["mc_all_ops"] = all_ops`. No behavior change in logging. All callers audited: `addon.py` (FIXED), `proxy_addon.py` (import only, no unpack), `dev/proxy_dual_log/groundtruth_message_spans_probe.py` (4 unpack sites → `*_`).

**Stage 2C** (`stage2C: switch consumer to compose_block — double-inject fixed`): `_build_stripped_injected_deltas` signature: `stripped_msg_removed`/`injected_msg_added` replaced by `all_ops: Optional[dict] = None`. Messages loop: `gt_chunks`/`gt_injected`/`msg_chunks`/`ima_chunks_msg`/`blk_chunks`/`ima_chunks_blk`/`build_message_spans` call removed; replaced by `block_ops = msg_ops.get(bidx_int); if block_ops is not None: spans = compose_block(c0_text, block_ops)`. `bd["spans"]` fallback retained for op-less (unmodified) blocks. `addon.py` `response()` reads `mc_all_ops`, passes `all_ops` to `_build_stripped_injected_deltas`.

**Offline verification (money-shot msg[100] flow_id 58620c90, api_requests_opus_monitor_cc_1780933074):**
- Op chain on blk[0]: 3 ops — `first_pass` (TN strip + wakeup inject), `bg_exit` (BG line strip + wakeup inject), `dedup_wakeup` (removes 2nd wakeup, offset=48, injected="")
- `compose_block` output: 1 injected span, wakeup_count=1 ✅ (was 2 with old `find()`-based path)
- `has_i=True`, `i_fn_map["msg.100.0"]="_apply_bg_exit_strip"` → badge fires ✅

**LIVE-VERIFY:** pending proxy restart. Expected: single green line per TN+BG message, REQ inj-badge present, no double-green.

## ✅ Stage 3 — CI Invariant Test DONE (2026-06-09)

`dev/proxy_dual_log/test_composition_invariant.py` — standalone Python, exits 1 on any invariant violation. Committed synthetic fixture at `dev/proxy_dual_log/fixtures/invariant_corpus.jsonl`: 9 entries covering all 8 passes + dedup_wakeup + money-shot (fix-3: TN with BG summary → first_pass + bg_exit + dedup_wakeup). Negative check confirmed: dropping any single op from the 3-op money-shot chain → `ok=False` on both invariants. 12/12 checks passed, blocks_checked=11, exit 0.

## ✅ Stage 4 — `_diff_text` Fallback Removal DONE (2026-06-09)

`_build_stripped_injected_deltas` messages loop (Stage 4 commit `967cdd8`):
- Removed: `spans = bd["spans"]` default + `if block_ops is not None:` guard
- Now: `block_ops = msg_ops.get(bidx_int, [])` (empty default); `c0_text` always extracted; `spans = compose_block(c0_text, block_ops)` unconditionally
- Op-less blocks: `block_ops=[]` → `[("equal", c0_text)]` → nothing logged — identical output to pre-Stage-4
- Optional cleanup: `_diff_messages` in `diff_engine.py` no longer computes `spans` (removed `"spans": _diff_text(...)` from all 4 block_diffs construction sites)
- `_diff_text` still called by `_diff_system` and `_diff_tools` — untouched
- CI test (`test_composition_invariant.py`): still 12/12, exit 0 after Stage 4 changes

## Open

- **LIVE-VERIFY** (proxy restart required) — behavioral confirmation after merge to dev + restart. Expected: single green line per TN+BG message, REQ inj-badge present, no double-green.
- **sidecar / idle_recap UNVERIFIED** — absent from the 5-stem corpus. Theoretical model: `Op(0,0,full_original,marker)` single full-replacement, trivially composable. Port covers this theoretically; real-data confirmation deferred.

## Sources

- The prior green-overlay false-injection process history in this area (false-injection arc, GT approach)
- `dev/proxy_dual_log/composition_probe.py` + `01_reports/composition_probe_20260608.md` (the byte-exact proof)
- `src/proxy/rules.py` (passes + current recording), `src/proxy/diff_engine.py` (`build_message_spans`/`_diff_text` to replace), `src/proxy/logging.py` (`_build_stripped_injected_deltas` glue)
- `Meta/iterative-dev/.../iterative-dev-refactor/SKILL.md` § 2.8 (the generalized fallback-hell scan + one-way redesign companion)
