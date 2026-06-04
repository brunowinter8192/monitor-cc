# 12 — Function Attribution Coverage Analysis

## What we did

Built `dev/proxy_dual_log/attribution_coverage.py` — a read-only script that processes all 19
`_stripped`/`_injected` dual-log pairs from `src/logs/dual_log/` and answers: can every entry
be attributed to a responsible proxy function?

**Approach:** Per-entry attribution using 4 mechanisms:
1. **sys delta** — by index position (sys[2] → `_apply_system_passes`, sys[3] → `_strip_sys3`)
2. **tools delta** — by shape (`{whole:True}` → `_strip_unused_tools`, `{desc:[...]}` → `_strip_tool_descriptions`)
3. **messages delta** — vocab marker match via `strip_vocab.attribute_chunk()` (first match on each s_text item), then residual gap checks, then json_reser detection as fallback
4. **fields delta** — by field key → `_inject_model_override`

Important classification decision: vocab/residual checks run **before** json_reser detection so
that TN/NAG/etc. blocks whose messages were also json_reserialized get attributed to the proxy
strip rule (not the format-change side effect).

**Dev scripts used:**
- `dev/proxy_dual_log/attribution_coverage.py` — built this phase
- Report: `dev/proxy_dual_log/attribution_coverage_reports/20260604.md`

## What we found

### Coverage numbers (19 pairs, 646 strip entries, 491 inject entries)

| Side | RAW | ADJUSTED (fp excluded) |
|---|---|---|
| Strip | 87.6% (566/646) | **100.0%** (566/566) |
| Inject | 33.0% (162/491) | **100.0%** (162/162) |

ADJUSTED = 100% for both: every entry is either attributed, a known residual gap, or an
identified false positive. Zero truly unattributed entries remain.

### Strip attribution breakdown

| Section | Function | Count |
|---|---|---|
| sys[2] | `_apply_system_passes` (replaced_system_prompt) | 36 |
| sys[3] | `_strip_sys3` | 18 |
| tools whole | `_strip_unused_tools` | 72 |
| tools desc | `_strip_tool_descriptions` | 90 |
| msg NAG | `strip_vocab.NAG` marker | 128 |
| msg TN | `strip_vocab.TN` marker | 57 |
| msg PYR | `strip_vocab.PYR` marker | 29 |
| msg DEF | `strip_vocab.DEF` marker | 19 |
| msg SK | `strip_vocab.SK` marker | 18 |
| msg PP | `strip_vocab.PP` marker | 5 |
| msg ENV (residual) | `strip_sr._ENV_CONTEXT_RE` — no vocab entry | 15 |
| msg HP (residual) | `strip_hook_prefix._strip_hook_prefix` — no vocab entry | 11 |
| msg UI_PARTIAL (residual) | `_apply_first_pass` UI mode=partial — no secondary marker | 5 |
| msg DATE_SR (residual) | `strip_sr.date-changed template` — no vocab entry | 1 |
| msg SN (residual) | `strip_sr.system-notification template` — no vocab entry | 2 |
| msg FM (residual) | `strip_sr.file-modified template` — no vocab entry | 1 |
| msg json_reser | FALSE POSITIVE (see below) | 80 |
| fields | `_inject_model_override` (orig replaced) | 59 |

### Inject attribution breakdown

| Section | Function | Count |
|---|---|---|
| sys[2] | `_apply_system_passes` (proxy rules) | 36 |
| sys[3] | `_strip_sys3` stub `"."` | 18 |
| tools | `inject_mcp_tools` | 0 |
| msg BGK_replacement | `_strip_bg_exit_notifications` (injects "background done") | 49 |
| msg json_reser | FALSE POSITIVE (87) + json_reser_combined (242) = 329 | 329 |
| fields | `_inject_model_override` | 59 |

**BGK discovery:** `_strip_bg_exit_notifications` doesn't just strip — it REPLACES the first
kill-notification with `"background done — check worker or other process"`. This creates paired
strip+inject entries: the strip entry has the `BGK` vocab code (Background command marker),
the inject entry carries the replacement text. The inject entries at BGK positions have
corresponding stripped entries so they're classified as `json_reser_combined` for most positions,
but the inject-only positions (where the replacement was at a different block index) are
correctly attributed as `BGK_replacement`.

### Residual gaps — strip_vocab.py additions needed

| Code | Rule | Required addition |
|---|---|---|
| ENV | `strip_sr._ENV_CONTEXT_RE` | New rule in RULES dict, marker: `"As you answer the user's questions, you can use the following context:\n# userEmail"` |
| HP | `strip_hook_prefix._strip_hook_prefix` | New rule, marker: `"PreToolUse:"` + secondary `"hook error"` |
| UI_PARTIAL | `_apply_first_pass` mode=partial | Add secondary marker to UI rule: `"IMPORTANT: After completing your current task"` |
| DATE_SR | `strip_sr.date-changed` | Add `"The date has changed."` marker to existing CMD rule |
| SN | `strip_sr.system-notification` | New rule, marker: `"[SYSTEM NOTIFICATION"` |
| FM | `strip_sr.file-modified` | New rule, markers: `"Note: "` + `" was modified"` |

### json_reserialization bug (DISTINCT FINDING)

**Root cause:** `_set_cache_breakpoints` (`cache.py`) normalises user-message content from
plain string `"text"` to single-text-block-list `[{"type":"text","text":"text"}]`. When
`_build_stripped_injected_deltas` in `logging.py` diffs orig vs fwd, it calls `_strip_cache_control`
but NOT `_normalize_msg_shape_for_hash`. Result: string vs block-list → `SequenceMatcher.ratio` ≈ 0.05
→ whole-block replace → false stripped+injected entries at every cache-normalised user message.

**Scope:** 80 strip-side + 329 inject-side false positive entries across 19 pairs.
The strip-side entries are short user messages ("quota", "ok", "recap", "passt", etc.) or
longer user messages that had no proxy strip — all rendered as false yellow+green in the monitor.

**Fix location:** `logging.py._build_stripped_injected_deltas` — apply `_normalize_msg_shape_for_hash()`
(already at line 175) to each message before passing to `_diff_messages`. The function exists
(used for hash comparison at line 193) but is not applied to the actual diff content.

**Fix sketch:**
```python
# In _build_stripped_injected_deltas, before _diff_messages call:
orig_msgs_norm = [_normalize_msg_shape_for_hash(m) for m in orig_msgs]
fwd_msgs_norm  = [_normalize_msg_shape_for_hash(m) for m in fwd_msgs]
msg_diffs = _diff_messages(orig_msgs_norm, fwd_msgs_norm)
```

### natural_msg_evolution

0 blocks found. All 19 "unknown" blocks were actual proxy strips lacking vocab entries
(HP/UI_PARTIAL/SN/FM). No diff entries exist that are natural evolution — every message
diff is either json_reserialization or an attributable proxy strip.

## Decision / next

**fn field: do NOT materialise yet.** Prerequisites:
1. Fix json_reserialization bug in `logging.py._build_stripped_injected_deltas`
2. Add 6 vocab entries to `strip_vocab.RULES` (ENV, HP, UI_PARTIAL, DATE_SR, SN, FM)
3. Re-run script to confirm ADJUSTED ≈ 100% holds after fix
4. Then add `fn` field to log entries

Both steps are contained fixes: json_reser fix = 3-line normalization; vocab additions = 6
entries in `RULES` dict. Estimated combined scope: 1 session.
