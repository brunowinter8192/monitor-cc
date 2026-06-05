# Green-Overlay False-Injection — Investigation (2026-06-04 → 2026-06-05)

Status: Root-cause CONFIRMED on real input. Three fix approaches evaluated; Ground-Truth (GT) approach validated in dev/ probe. Port to src/ pending.

## Symptom

Proxy pane colors UNCHANGED content green (=injected). Confirmed live: req#169 msg[336] tool_result — `arm64\n\n` rendered green although it is byte-identical in original AND forwarded; only the trailing `<system-reminder>…</system-reminder>` was stripped (yellow). The green should only mark genuinely-injected content; unchanged content must be grey.

## Evidence (write-side, not renderer)

`_injected` dual-log for that block (`messages_delta["336"]["0"]`) stores the span list:
- `["equal", "{\"tool_use_id\": …, \"type\": \"tool_result\", \"content\": …"]`
- `["injected", "arm64\n\n\","]`   ← unchanged `arm64\n\n` mis-tagged injected
- `["equal", "\"is_error\": false}"]`

So the diff engine itself tags `arm64\n\n",` as injected. The renderer is CORRECT: `render_messages.py` / `render_sections.py` set `bg = DIM_GREEN_BG if tag == "injected" else ""` — equal spans stay grey. → bug is in the WRITE side (`diff_engine._diff_text`).

## Root-cause CONFIRMED (2026-06-05, green_overlay_probe.py)

`_diff_text` (`src/proxy/diff_engine.py`) word-level path confirmed on the EXACT original input:

**Session:** `badge-recap_1780678180`, flow `7a12336f…`, `messages[18]` block 0 (tool_result).
**o_text** = `json.dumps(blk)` = `{"…, "content": "…set()))\n\n<system-reminder>\n…", "is_error": false}` (649 chars).
**f_text** = `json.dumps(mod_blk)` = same with SR removed (191 chars).

Word-level diff on json.dumps:
- `set()))\n\n<system-reminder>…</system-reminder>` and `set()))\n\n",` share prefix `set()))\n\n` — single word token each (escaped `\n` = NOT whitespace). SequenceMatcher 'replace' → common prefix tagged BOTH stripped AND injected.
- Confirmed injected phantom: `'set()))\\n\\n",'` — pure JSON structural chars, never injected by proxy.

Disconfirmation control remains valid: real `\n` gets split, so arm64 would land in equal.
No stale-copy issue: all `_diff_text` copies identical.

## Fix approach A — char-level (PARTIAL, insufficient)

`diff_text_char`: replaces `ow,fw=orig_text.split()` path with `SequenceMatcher(None, orig_text, fwd_text).get_opcodes()` on chars. Results on bug case:
- Common 280-char prefix correctly equal ✅
- `<system-reminder>` stripped ✅
- Residual phantom: `', "is_error": false}'` — chars `", "is_error": false}` in the JSON suffix that LCS aligns suboptimally across the changed boundary. Still phantom green.
- Fidelity: orig_ok=True, fwd_ok=True ✅

Probe: `dev/proxy_dual_log/green_overlay_probe.py` (Variant 2).

## Fix approach B — attribution gating (DEAD END)

`diff_text_char_gated`: char-level + gate: injected spans where `_fn_for_inject(text)=="unknown"` → reclassify equal. Eliminates residual phantom on bug case. But:
- **Fidelity break:** gated spans reclassify injected→equal, so equal+injected reconstruction of fwd_text fails (the gated span is no longer counted as injected). `gated_fid_ok=False` on some cases.
- **Real injects suppressed:** 144 msg-level injects in live logs also attribute to `"unknown"` (dot-replacements, sidecar markers, file-path injects) — would be mis-coloured grey.
- Only `_apply_bg_exit_strip` (78 bg-done cases) reliably avoids gating.

Verdict: gating cannot distinguish phantom from real unknown-attributed injects. DEAD END.

Probe: `dev/proxy_dual_log/green_overlay_probe.py` (Variant 3 + soundness scan).

## Fix approach C — Ground-Truth spans (VALIDATED 2026-06-05)

**Core insight:** the proxy never injects on messages — it only STRIPS (and some strips REPLACE with a small placeholder). `apply_modification_rules` already records exactly what it stripped per message in `stripped_msg_removed: {msg_idx: [chunk, …]}`. Build spans from those records instead of diffing.

**Algorithm** (`build_message_spans(orig_text, fwd_text, stripped_chunks)`):
1. Split `orig_text` at exact positions of each `stripped_chunk` → alternating EQUAL + STRIPPED segments.
2. Walk `fwd_text` matching each EQUAL segment in sequence.
3. Text in `fwd_text` between matched EQUAL segments = INJECTED (the real placeholder, if any).
4. Emit spans: equal / stripped / injected.

**Probe:** `dev/proxy_dual_log/groundtruth_message_spans_probe.py` (session 2026-06-05).

**Results on 4 real cases:**

| Case | GT fidelity | GT injected | Phantom |
|---|---|---|---|
| BUG msg[18] blk[0] tool_result, SR stripped | ✅ lossless | 0 | none ✅ |
| TEXT_REPLACE msg[0] blk[0] DEF-SR → '.' | ✅ lossless | 1 (`'.'`) | none ✅ |
| BG_REPLACE msg[78] blk[0] TN→wakeup | ✅ lossless | 1 (`'background done…'`) | none ✅ |
| LARGE_SR msg[0] blk[1] 5777-char SK-SR → '.' | orig_ok ✅ fwd_ok ❌ precision-gap | 1 (`'.'`) | none ✅ |

**Precision gap (LARGE_SR fwd_ok=False):** `_find_system_reminder_blocks` extracts SR without trailing `\n?`, but `_STANDALONE_SR_RE` strips SR + optional trailing newline. The orphaned `\n` appears in GT as 'equal' but is absent from fwd_text. Fix: include `\n?` in extraction pattern.

**Inner-content level (Phase B finding a):** GT algorithm operates on `block["content"]` for tool_result blocks and `block["text"]` for text blocks — NOT on `json.dumps(block)` (production `_get_text` path). This is cleaner: JSON structure (`"is_error": false}`, `"type": "tool_result"`) is never coloured at all. The eventual port must decide: (i) keep at inner-content level and adapt `_diff_messages` to call inner-text extractor, or (ii) JSON-escape stripped chunks before searching in `json.dumps` output.

**Recording gaps (Phase B finding b):** Two gaps where `stripped_msg_removed` does not capture all strips:
- **ENV-context SR:** `_apply_cumulative_sr_strips` strips ENV-context SR via `_ENV_CONTEXT_RE` as a side-effect of the SK-template pass, but `_find_system_reminder_blocks` only records SK-marked SRs. The ENV SR is silently excluded from `pass_removed_by_idx`.
- **Trailing `\n`:** `_STANDALONE_SR_RE` captures `\n?` after `</system-reminder>`, but `_find_system_reminder_blocks` uses a pattern without `\n?`. The trailing newline is stripped but not in the recorded chunk.

Port must close both gaps before GT spans can be used in production.

**Nested-chunk case (flagged):** BG_REPLACE has chunk[1] (BG command, 77 chars) nested inside chunk[0] (TN block, 406 chars = entire o_text). Later-pass chunks extracted from intermediate content may be nested inside earlier-pass chunks. Algorithm detects this (NESTED_CHUNK flag) and skips; fidelity unaffected.

## Phase B Step 1 — Recording (DONE)

Inject-side fully recorded. Two recording gaps closed. Byte-identical forwarded payload confirmed.

**`injected_msg_added` accumulator added to `apply_modification_rules`.** New 7th return element, parallel to `stripped_msg_removed`. All eight private pass helpers return 5-tuple `(new_messages, pass_mods, pass_removed_by_idx, changed_indices, pass_injected_by_idx)`; orchestrator accumulates via `injected_msg_added.setdefault(idx, []).extend(pass_injected.get(idx, []))`. Four inject points captured:
1. `_apply_first_pass` TN branch → `[_WAKEUP_TEXT]`
2. `_apply_first_pass` plan-mode FULL-strip branch → `["(plan-mode reminder stripped by proxy)"]`
3. `_apply_bg_exit_strip` when `bg_removed` non-empty → `[_WAKEUP_TEXT]`
4. `_check_sidecar` / `_check_idle_recap` short-circuits → 7-tuple with `{idx: [marker]}` directly

**Gap 1 — ENV-context SR recording closed.** `_apply_cumulative_sr_strips` switched from marker-by-marker `_find_system_reminder_blocks(original, marker)` calls to diff-based extraction: `[sr for sr in _find_all_system_reminder_blocks(original_before_pass) if sr not in _find_all_system_reminder_blocks(content)]`. Captures ENV-context SRs stripped via `_ENV_CONTEXT_RE` that the per-marker approach excluded.

**Gap 2 — trailing `\n` closed.** Both `_find_system_reminder_blocks` and `_find_all_system_reminder_blocks` in `payload_helpers.py` updated to `</system-reminder>\n?` with `re.DOTALL`. Recorded chunk now includes the trailing newline that `_STANDALONE_SR_RE` strips — eliminates the LARGE_SR `fwd_ok=False` precision gap.

**`addon.py` stash.** After `stripped_msg_removed` in the entry dict: `if injected_msg_added: entry['injected_msg_added'] = {str(k): v for k, v in injected_msg_added.items()}`. Not consumed yet — Step 2 wires it to the span builder.

**Short-circuit strip-record status.** Both `_check_sidecar` and `_check_idle_recap` already recorded `orig_content` in `stripped_msg_removed` (element 5 of the 7-tuple, pre-existing). Both yellow (orig) and green (marker) available to Step 2 builder. No inject-without-strip gap.

**Byte-identical proof.** 194 payloads from `api_requests_opus_monitor_cc_1780670328_original.jsonl` — `json.dumps(modified_payload["messages"], sort_keys=True)` per payload diff-compared before/after change (git stash / pop): identical.

### Next — Phase B Step 2

- Thread `injected_msg_added` through to `build_message_spans` in the GT span builder
- Switch `_diff_messages` (or its call site) from `_diff_text` to GT spans when records are available
- Resolve inner-content level decision (block["content"] / block["text"] vs json.dumps — see Phase B finding a above)

**Plumbing mechanism.** `stripped_msg_removed` and `injected_msg_added` are computed in `apply_modification_rules` (request hook, `addon.py`) and currently written only to the main log entry. Step 2 requires both to be stashed on `flow.metadata` in `request()` (parallel to `mc_original_payload`), read back in `response()`, and passed into `_build_stripped_injected_deltas` — which uses them for the message part instead of calling `_diff_text`.

**Display implication.** Strip/inject message blocks today render at `json.dumps`-level: the `_get_text` path serialises the entire block dict (`{"tool_use_id":…, "content":…, "is_error":…}`) before diffing, so yellow/green can bleed into JSON structural chars — this is the phantom source. Content-level spans (`block["content"]` / `block["text"]`) show only the actual content, same as normal (non-strip/inject) blocks already do. The change is targeted: today only strip/inject tool_result blocks show the JSON wrapper; normal blocks are already content-level. No pane-wide impact.

**Algorithm to port.** `build_message_spans(orig_text, fwd_text, stripped_chunks)` in `dev/proxy_dual_log/groundtruth_message_spans_probe.py` is the validated record-driven span builder. Port this function to `src/proxy/diff_engine.py` (or a new `src/proxy/gt_spans.py`) and call it from `_diff_messages` when `stripped_msg_removed` records are available for the block.

## Phase B Step 2 — Port (implementation)

**Ported to src/:** `_get_inner_text` + `build_message_spans` byte-faithfully from `dev/proxy_dual_log/groundtruth_message_spans_probe.py` into `src/proxy/diff_engine.py`. No algorithmic changes; probe IS the validation baseline.

**Plumbing:** `stripped_msg_removed` (int msg_idx → list[str]) computed in `request()` by `apply_modification_rules` was not on `flow.metadata`. Added `flow.metadata["mc_stripped_msg_removed"] = stripped_msg_removed` in `addon.py` `request()` (after log write). In `response()`, read as `smr = flow.metadata.get("mc_stripped_msg_removed") or {}` and passed as new 7th parameter `stripped_msg_removed: Optional[dict] = None` to `_build_stripped_injected_deltas` in `logging.py`.

**Messages loop switch:** in `_build_stripped_injected_deltas`, for each message block:
1. Get `msg_chunks = stripped_msg_removed.get(md["idx"], [])`.
2. Derive inner text: for list-content messages use `_get_inner_text(ob)` / `_get_inner_text(fb)` on the raw block objects from `orig_msgs_norm`/`fwd_msgs_norm`; for string-content (normalized single-text-block) use the content string directly.
3. **Per-block gate:** `blk_chunks = [c for c in msg_chunks if c in o_inner]` — only call `build_message_spans` when `blk_chunks` is non-empty. Blocks with no matching chunks fall back to `bd["spans"]` (`_diff_text` result). Prevents a modified block whose chunks belong to another block from being collapsed to `[('equal', orig)]`.
4. **None-block guard:** if `ob` or `fb` is `None` (block index out of range) → fall back to `bd["spans"]` without calling `_get_inner_text`.

**Design question (a) — inner-content level:** confirmed correct. `_get_inner_text` returns `block["text"]` for text blocks and `block["content"]` (or `\n`-joined inner text for list content) for tool_result blocks. JSON wrapper (`"is_error": false}`, `"type": "tool_result"`) never enters span building. Consistent with renderer: `render_messages.py` "new format" inline path walks `span_text` directly; `full_text` for normal (non-strip) blocks already comes from inner content via `_summarize_message`. No renderer changes needed.

**Design question (b) — `injected_msg_added` left out:** GT algorithm discovers injected spans from gaps in `fwd_text` between matched equal segments — no external injection record needed. `injected_msg_added` would add complexity for zero correctness benefit. Left out.

**Verification:** byte-faithful port confirmed by import + spot-check (pure strip → zero injected, fidelity round-trip). Existing strip suite `dev/proxy/test_strip_fix.py`: 46/46 PASS (pre-existing crash in `w01_tn_in_tool_result_str` on `_apply_first_pass` return-arity is independent of this task). Live render verification of green-overlay fix in proxy pane: pending user review.

## Source refs
- `_diff_text`, `_diff_messages` in `src/proxy/diff_engine.py`
- `apply_modification_rules`, `stripped_msg_removed` in `src/proxy/rules.py`
- `_find_system_reminder_blocks`, `_find_all_system_reminder_blocks` in `src/proxy/payload_helpers.py`
- `_STANDALONE_SR_RE`, `_ENV_CONTEXT_RE` in `src/proxy/strip_sr.py`
- span render: `src/proxy_display/render_messages.py`, `src/proxy_display/render_sections.py`
- probe scripts: `dev/proxy_dual_log/green_overlay_probe.py`, `dev/proxy_dual_log/groundtruth_message_spans_probe.py`
- prior span-model work: `09_inline_span_rendering.md` (Form B equal-anchor spans)
