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

## Source refs
- `_diff_text`, `_diff_messages` in `src/proxy/diff_engine.py`
- `apply_modification_rules`, `stripped_msg_removed` in `src/proxy/rules.py`
- `_find_system_reminder_blocks`, `_find_all_system_reminder_blocks` in `src/proxy/payload_helpers.py`
- `_STANDALONE_SR_RE`, `_ENV_CONTEXT_RE` in `src/proxy/strip_sr.py`
- span render: `src/proxy_display/render_messages.py`, `src/proxy_display/render_sections.py`
- probe scripts: `dev/proxy_dual_log/green_overlay_probe.py`, `dev/proxy_dual_log/groundtruth_message_spans_probe.py`
- prior span-model work: `09_inline_span_rendering.md` (Form B equal-anchor spans)
