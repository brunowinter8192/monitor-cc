# Proxy Pane ⚠SR Badge Intermittent

## Symptom

The proxy pane in Monitor_CC did not consistently show the ⚠SR badge on strip events. Original assumption: the badge disappears after a longer pane lifetime, comes back after a Ctrl+R respawn. A second investigation round refined the symptom: **intermittent, not binary** — some REQs have the badge, others don't, even in a long-running pane process.

As of 2026-05-12: the user reports the monitor runs fine. The symptom in its current form was no longer observed. Investigation concluded as resolved-by-drift / no-longer-reproducible.

## Established Facts (as of 2026-05-09)

1. Strip runs. Every REQ in the JSONL has 10 mods incl. `stripped_deferred_tools_sr`, `stripped_skills_sr`. `stripped_msg_indices=[0]`, `stripped_msg_removed["0"]` contains literal `<system-reminder>` chunks.
2. `_aggregate_entry_tags(entry)` correct — returns `['SR']` for REQ#1 (msg_count=1, BP:1, `diff_from_prev.first_diff_index=0`). For REQ#2–#7 returns `[]`, because the strip on msg[0] sits outside the delta range — by design.
3. `format_proxy_block` run directly against freshly parsed JSONL produces `▶ #1 opus 1msg BP:1 eff:hig think:128k CR:0 CC:0 🔧+7 ⚠SR  TTFB:2.5s` (visible_width=71). The badge IS rendered in fresh state.
4. Width truncation is NOT the cause — Ctrl+R doesn't change the pane width and restores the badge.
5. A live pane showed the badge on REQ#46 (msg_count=91, CR:143k, CC:6.4k): `▶ #46 opus 91msg BP:1 eff:hig think:128k CR:143k CC:6.4k Δmsgs:+1.8k(~511tok) ⚠SR TTFB:4.3s`. So the symptom is intermittent.
6. A worker had started comparing commit `df9ec75` (dev vs main) — investigation aborted mid-flight (context limit).

## Hypotheses (left open)

- **H1:** `_lazy_load_messages` mutates entries only under certain conditions (first vs second call).
- **H2:** the `diff_from_prev.first_diff_index` recompute pushes only certain REQs out of the delta range.
- **H3:** `_proxy_cache_turns` selectively regroups it away.
- **H4:** `df9ec75` contains a fix that desyncs dev/main — the live pane ran on old code.

## Status (as of the initial investigation)

Two investigation workers died at the context limit (proxy-state-bug, proxy-strip-state). Investigation paused; since then no reproduction reported — the monitor stable. Parked; on recurrence, a new investigation round with a more tightly scoped approach (repro only on concrete live data, several REQs, no broad code-reading session).

## Where (if reactivated)

- `src/proxy/` (strip logic)
- `src/panes/` (proxy-pane renderer, `format_proxy_block`, `_aggregate_entry_tags`)
- `_lazy_load_messages`, `_proxy_cache_turns`, `diff_from_prev.first_diff_index`
- Commit `df9ec75` for the dev/main comparison

---

## Resolution — ⚠SR/⚠TN Double-Fire (2026-06)

### Symptom (Refined)

⚠SR/⚠TN/⚠ND badges fired on REQs where no genuinely-new SR/TN existed — every real TN/SR was badged TWICE: once at gap=0 (genuinely new) and again ~2 REQs later at gap=2 (false positive).

### Root Cause — H2 Confirmed

**H2 was the cause.** `diff_from_prev.first_diff_index` is a content-diff anchor for cache-BP3 placement — correct for that purpose, but it REGRESSES into old message indices whenever a previous message changes by even 1 character.

Concrete mechanism: `_apply_first_pass` in `rules.py` appends `\n` to the end of the TN-strip wake-up block (`_WAKEUP_TEXT`). On the next turn, Claude Code re-serializes the same message list to a string (47c→48c, blocks→empty). `first_diff_index` then points at this old, slightly-changed message — not at the first genuinely new one. That put the gate value for "strips to count" BELOW `prev_message_count`, and the strip at that old index was counted as "new" again → double-fire.

**H1, H3, H4 ruled out:** `_lazy_load_messages` mutation effects, the `_proxy_cache_turns` regroup, and dev/main code desync were NOT causal — the symptom was deterministically reproducible on freshly parsed JSONL data with no live-pane interaction at all.

### Fix

`start = message_count - (messages_added or 0)` = `prev_message_count` — the index of the first genuinely new message. `messages_added` is already present in `diff_from_prev`.

Applied at BOTH affected spots:
- `_aggregate_entry_tags()` in `src/proxy_display/render_messages.py` (badge gate for ⚠SR/⚠TN/⚠ND)
- `classify_tags()` in `src/proxy/strip_vocab.py` (LEAK/SUS delta scope)

`first_diff_index` / `parser.py` NOT touched — stays correct for its cache-BP3 purpose. Edge cases preserved: `fdi is None` → `start=0` (first REQ, all msgs new); `fdi < 0` → early return (byte-identical re-fire, no new strip activity).

### Verification

Tested against the live log `src/logs/api_requests_opus_monitor_cc_1780585154.jsonl`:
- 10 TN false positives (gap=2 regressions) suppressed
- 0 cross-request double-flags after the fix
- All genuine SR/TN/ND badges preserved (task-tools-nag SR, deferred-tools/skills SR, real timer TNs)

Scope decision (user-confirmed): only the double-fire is removed; ALL real reminder strips stay badged.
