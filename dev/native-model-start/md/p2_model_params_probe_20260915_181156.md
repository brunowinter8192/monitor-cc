# P2 — model_params probe run (2026-09-15T18:11:56.549386+00:00)

**Result: 73/73 checks passed**

| Check | Result |
|---|---|
| opus family: injected=True | PASS |
| opus family: model REWRITTEN to claude-fable-5 (legacy behavior) | PASS |
| opus family: thinking applied | PASS |
| opus family: effort applied via output_config | PASS |
| opus family: max_tokens applied | PASS |
| sonnet family: injected=True | PASS |
| sonnet family: model REWRITTEN to claude-sonnet-5 (legacy behavior) | PASS |
| haiku family: no legacy section -> untouched, injected=False | PASS |
| injected=True | PASS |
| model field UNCHANGED (still claude-fable-5, not rewritten) | PASS |
| thinking applied | PASS |
| effort applied via output_config | PASS |
| max_tokens applied | PASS |
| claude-opus-5 hit: injected=True, model untouched | PASS |
| claude-sonnet-5 hit: injected=True, model untouched | PASS |
| injected=False | PASS |
| payload identical (same dict values) | PASS |
| suffixed id 'claude-opus-4-8[1m]' vs table key 'claude-opus-4-8' -> exact match FAILS | PASS |
| injected=True (from model_params, not legacy) | PASS |
| model NOT rewritten despite legacy model_override.model=claude-fable-5 being present too | PASS |
| thinking/effort/max_tokens match model_params values | PASS |
| empty model_params {} -> injected=False (no entry for this model) | PASS |
| model NOT rewritten to claude-fable-5 — legacy path never consulted despite being 'enabled' | PASS |
| empty {} entry for a matched model -> injected=False, untouched | PASS |
| partial entry (effort only): injected=True | PASS |
| effort applied | PASS |
| thinking NOT added (key absent from entry) | PASS |
| max_tokens UNCHANGED from original payload (key absent from entry, not injected) | PASS |
| no raise propagated | PASS |
| injected=False, payload untouched | PASS |
| (a) first request applies config1 (effort=low) | PASS |
| (a) first request applies config1 (max_tokens=32000) | PASS |
| (a) fixated dict now holds an entry for claude-fable-5 | PASS |
| (b) SAME fixated dict: config2 change ignored, still effort=low | PASS |
| (b) SAME fixated dict: config2 change ignored, still max_tokens=32000 | PASS |
| (b) injected still True on the pinned replay | PASS |
| (c) fresh dict applies config2 (effort=high) | PASS |
| (c) fresh dict applies config2 (max_tokens=128000) | PASS |
| (d) legacy first call: injected=True | PASS |
| (d) legacy first call: model REWRITTEN (byte-identical to unfixated Test 1) | PASS |
| (d) legacy first call: thinking applied | PASS |
| (d) legacy first call: effort applied | PASS |
| (d) legacy first call: max_tokens applied | PASS |
| (d) fixated dict now holds an entry for claude-opus-4-8 | PASS |
| (d) SAME fixated dict: still injected despite config now disabled | PASS |
| (d) SAME fixated dict: model still rewritten to claude-fable-5 | PASS |
| miss: injected=False on first call | PASS |
| miss: fixated dict still records the (empty) snapshot | PASS |
| miss stays pinned: still injected=False despite the entry now existing | PASS |
| miss stays pinned: payload2 unchanged | PASS |
| load failure: injected=False, no raise | PASS |
| load failure: nothing pinned for claude-fable-5 | PASS |
| next call retries live and succeeds: injected=True | PASS |
| next call retries live and succeeds: effort=medium applied | PASS |
| next call retries live and succeeds: now pinned for claude-fable-5 | PASS |
| (a) clear_thinking_20251015 removed, changed=True | PASS |
| (a) clear_tool_uses_20250919 survives untouched | PASS |
| (a) original payload's edits list not mutated in place (still has both edits) | PASS |
| (b) sole edit removed -> context_management key dropped entirely (no empty edits list) | PASS |
| (c) thinking enabled -> unchanged, changed=False | PASS |
| (c) thinking enabled -> context_management is the SAME object, byte-identical | PASS |
| (d) no context_management -> no-op, changed=False | PASS |
| (e) no clear_thinking edit present -> untouched, changed=False | PASS |
| (f) model_params injection (thinking toggle OFF) set thinking to disabled | PASS |
| (f) end-to-end: the self-contradictory 400-causing payload is now self-consistent | PASS |
| thinking ON value recorded in the forwarded_delta entry | PASS |
| thinking OFF value recorded in the forwarded_delta entry | PASS |
| thinking absent from payload -> key present in the entry, value None | PASS |
| (a) context_management now appears in stripped fields_delta (new: was injected-only before) | PASS |
| (a) the real fn_map carries NO field-level entry at all (thinking is equally unattributed there — pre-existing dead code, not something this fix changes) | PASS |
| (a) confirms by content: src/proxy/strip_inject_delta.py's own _FIELD_STRIP_FN/_FIELD_INJECT_FN have been removed entirely (they were never live) | PASS |
| (b) attribution_coverage.py now attributes the strip to _strip_clear_thinking_edit, not UNATTR (got: '_strip_clear_thinking_edit (removed: thinking disabled)') | PASS |
| (b) the inject side (Claude Code / _inject_context_management adding the edit) is unchanged and still correctly attributed | PASS |
