# 17 — Badge False-Positives in the Strip/Inject Count

Discovered 2026-06-09 during #12 live-verify of the operation-transcript span-derivation. The
REQ-header `{n}strip {n}inj` badge (count of distinct strip/inject fns per request, via
`_strip_fns_lookup`/`_inject_fns_lookup`, built in `parser.py:accumulate_dual_log` from the
`_stripped`/`_injected` log `fn_map`) over-counts. Three distinct phantom sources, ALL verified
end-to-end on real log data — no open hypotheses.

Guiding principle (user, 2026-06-09): a strip/inject is badged ONLY when something **substantial**
happens — a real content injection like the bg-exit "background done" notification, or a real
content strip. Field overrides, structural placeholders, and spurious whitespace are NOT badge-worthy.

## Source 1 — Field-override attribution (REQ #33 class)

**Symptom:** REQ shows `1inj` (no strip); the only change is a top-level field override
(model / effort / thinking / max_tokens). No content injected — phantom.

**Root cause:** `logging.py:358` (`s_fn_map`) and `:364` (`i_fn_map`) write the field-change fn
(`_FIELD_STRIP_FN` / `_FIELD_INJECT_FN`, default `_inject_model_override`) into `fn_map` with loc_key
`field.{key}`. The badge counts `set(fn_map.values())`, so field overrides count as content
strip/inject. The proxy overrides these fields on EVERY request → nearly every request would badge an
inject → ruins the visualization. The `fields:` drill-down already shows them (orig→fwd diff).
Why "inj without strip" at #33: the field fn_map is written only when the per-field hash changes vs
the previous request (`logging.py:356/362`); at #33 the FORWARDED override values changed (→ inject
hash changed → inj fn) while CC's ORIGINAL values were stable (→ strip hash unchanged → no strip fn).

**Fix:** write-side — drop the field-change attribution from `s_fn_map`/`i_fn_map` (logging.py
358/364). Fields belong in the `fields:` drill-down, never the content badge. Revert the read-side
`field.*` filter (`parser.py:158`) — it was a fallback masking this write-side over-attribution;
`fn_map`'s ONLY consumer is the badge, so the field entries are dead data, removed at source.

## Source 2 — Partial-strip net-new newline (REQ #115 class; msg.36.0, msg.302.1)

**Symptom:** `1strip 1inj` where the strip is real + visible but the "inj" is an invisible/meaningless
fragment `</system-reminder>\n`.

**Root cause:** `strip_sr.py:147` (partial mode) ALWAYS re-appends `\n` to the closing tag. The match
regex `_STANDALONE_SR_RE` ends with `\n?` (optionally consumes a trailing newline — needed for the
full-block-removal mode). Partial mode RESTORES the consumed `\n` — but unconditionally. When the
original had NO trailing `\n`, the regex consumed none yet the append adds one → a NET-NEW `\n` in the
forwarded payload. `_extract_block_op` then sees a tail diff (`</system-reminder>` vs
`</system-reminder>\n`) → op `injected="</system-reminder>\n"` → `("injected", …)` span →
`has_i=True` → fn_map (`unknown`) → phantom badge. This is also a real proxy-output bug: a spurious
newline forwarded to the API. Verified end-to-end (flow 7ab56ecd; `compose_block` Inv1/Inv2 PASS — the
composition is correct, the bad op originates upstream in the strip).

**Fix:** write-side `strip_sr.py:147` — restore the `\n` only if the matched original had one
(`trailing_nl = '\n' if full.endswith('\n') else ''`). Removes the spurious newline AND the phantom.
NOT "remove the append entirely" — that would drop the legitimate separator when the original HAD a
`\n`, gluing the following content onto the tag. CI invariant `test_composition_invariant.py` SAFE
(structural composition unchanged, cleaner op).

## Source 3 — Empty-block "." placeholder (msg.0.0 / msg.0.1, REQ#1 only)

**Symptom:** `1inj` where the injected text is just ".".

**Root cause:** `strip_sr.py` `... or '.'` (lines 73/83/94) replaces a fully-stripped block's empty
content with "." (intentional — Anthropic rejects empty content blocks). The "." then surfaces as an
injected span → `has_i=True` → fn_map (`unknown`) → phantom badge.

**Fix:** write-side `logging.py` (the `i_fn_map` assignment, ~330-341) — skip the fn_map attribution
when the injected text is just ".". The `or '.'` itself STAYS (intentional proxy correctness — it is
primarily a strip, the "." only exists to let the message pass the API; it is not an injection).

## Source 4 — System/tools empty-block placeholder (sys.2/sys.3, tool_d)

**Symptom (2026-06-12):** REQ shows `1inj` (no strip); expanded view shows field/system changes only,
no visible injected message. Live `_injected` dual-log (74 entries) shows ~2 entries with
`fn_map: {"sys.2": "_apply_system_passes", "sys.3": "_strip_sys3"}` where the injected content is
literally `[["injected", "."]]` — a single `"."`.

**Root cause:** The `"."` skip added in Source 3 was written into `_process_messages_section` only.
`_process_system_section` and the desc_changes path of `_process_tools_section` in
`src/proxy/strip_inject_delta.py` had no equivalent guard — `i_fn[lk]` was written unconditionally
whenever `has_i = True`, including when the only injected span was `"."`.

Two system-side producers:
- `_strip_sys3()` (`content_strip.py:166`): `new_system[3] = {**block, "text": "."}` — always
  replaces sys[3] with `"."`. `_diff_text(long_sys3_text, ".")` ratio < 0.1 → spans
  `[("stripped", long_text), ("injected", ".")]` → `has_i=True` → phantom `i_fn["sys.3"]`.
- `_apply_system_passes()` (`rules.py:98`): `system_rules if system_rules else "."` — `"."` only
  when `system_rules` is empty. The non-empty case (real rules → real inject) is NOT a phantom.

**Fix:** `_process_system_section` and `_process_tools_section` (desc_changes loop) — compute
`i_text = " ".join(t for tag, t in i_spans if tag == "injected" and t)` inside the hash-change gate;
skip `i_fn[lk]` when `i_text == "."`. Overlay dicts (`i_sys`, `i_tools`) remain unconditional.
Whole-tool MCP inject path (`tool_w.*`, lines 91-97) unaffected — handles tool names, not spans.
Implemented in `src/proxy/strip_inject_delta.py` (6-line change, 2026-06-12).

**Live-log evidence:** 74 `_injected` entries from
`src/logs/dual_log/api_requests_opus_monitor_cc_1781103293_injected.jsonl`:
- 64 entries: empty `fn_map` (correct, field-override phantoms already fixed)
- 8 entries: `msg.* → _apply_bg_exit_strip` (legitimate bg-exit, badge correct)
- ~2 entries: `sys.2 → _apply_system_passes` + `sys.3 → _strip_sys3`, injected text = `"."` — phantom

**Note on sys.2 real content rewrites:** one live entry showed `sys.2 → [["injected", "# Communication\n\n..."]]`
(non-`"."` content). This IS a legitimate inject — `_apply_system_passes` replaces sys[2] with
proxy-owned rules. The badge is correct; hash suppression prevents repeated badging for identical
rules. Not a phantom.

## Fix Plan (ordered, one stage)

1. `parser.py:158` — revert read-side `field.*` filter back to `set(fn_map.values())`.
2. `logging.py:358` + `:364` — drop field-change attribution from `s_fn_map` / `i_fn_map`.
3. `strip_sr.py:147` — preserve the original trailing-`\n` state.
4. `logging.py` ~330-341 — skip the `i_fn_map` attribution when the injected text is just ".". ✅ Done (was message-path only; migrated to `strip_inject_delta.py` when logging.py was refactored)
5. Verify on real `_injected`/`_stripped` logs: field-only reqs → no badge; the `</system-reminder>\n`
   and `.` phantoms gone; bg-exit + real content injects still badge. Update current-state docs:
   `src/proxy/DOCS.md`, `src/proxy_display/DOCS.md`. ✅ Done
6. Extend `"."` skip to system + tools-desc sections in `strip_inject_delta.py`. ✅ Done (2026-06-12)
