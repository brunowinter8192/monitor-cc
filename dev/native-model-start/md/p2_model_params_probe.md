# p2_model_params_probe

15/15 strands passed

## PASS test_legacy_only_unchanged


[Test 1] Legacy-only config -> byte-identical legacy behavior
  PASS  opus family: injected=True
  PASS  opus family: model REWRITTEN to claude-fable-5 (legacy behavior)
  PASS  opus family: thinking applied
  PASS  opus family: effort applied via output_config
  PASS  opus family: max_tokens applied
  PASS  sonnet family: injected=True
  PASS  sonnet family: model REWRITTEN to claude-sonnet-5 (legacy behavior)
  PASS  haiku family: no legacy section -> untouched, injected=False

## PASS test_model_params_hit


[Test 2] model_params hit -> params applied, model field NEVER touched
  PASS  injected=True
  PASS  model field UNCHANGED (still claude-fable-5, not rewritten)
  PASS  thinking applied
  PASS  effort applied via output_config
  PASS  max_tokens applied
  PASS  claude-opus-5 hit: injected=True, model untouched
  PASS  claude-sonnet-5 hit: injected=True, model untouched

## PASS test_model_params_miss


[Test 3] model_params miss -> payload untouched
  PASS  injected=False
  PASS  payload identical (same dict values)

## PASS test_suffixed_model_id_is_deliberate_miss


[Test 4] Suffixed model-id variant -> deliberate MISS (no normalization)
  PASS  suffixed id 'claude-opus-4-8[1m]' vs table key 'claude-opus-4-8' -> exact match FAILS

## PASS test_model_params_presence_wins_over_legacy


[Test 5] model_params PRESENT (non-empty) alongside legacy sections -> model_params wins
  PASS  injected=True (from model_params, not legacy)
  PASS  model NOT rewritten despite legacy model_override.model=claude-fable-5 being present too
  PASS  thinking/effort/max_tokens match model_params values

[Test 5b] model_params PRESENT as an EMPTY {} -> still wins, legacy fully disabled
  PASS  empty model_params {} -> injected=False (no entry for this model)
  PASS  model NOT rewritten to claude-fable-5 — legacy path never consulted despite being 'enabled'

## PASS test_empty_and_partial_entries


[Test 6] Empty per-model entry -> untouched; partial entry -> only that key applied
  PASS  empty {} entry for a matched model -> injected=False, untouched
  PASS  partial entry (effort only): injected=True
  PASS  effort applied
  PASS  thinking NOT added (key absent from entry)
  PASS  max_tokens UNCHANGED from original payload (key absent from entry, not injected)

## PASS test_config_load_failure_fails_open


[Test 7] _load_config raising -> fail-open, no raise
  PASS  no raise propagated
  PASS  injected=False, payload untouched

## PASS test_fixation_pins_model_params_snapshot


[Test 8] Fixation: model_params pins on first request, later config change ignored
  PASS  (a) first request applies config1 (effort=low)
  PASS  (a) first request applies config1 (max_tokens=32000)
  PASS  (a) fixated dict now holds an entry for claude-fable-5
  PASS  (b) SAME fixated dict: config2 change ignored, still effort=low
  PASS  (b) SAME fixated dict: config2 change ignored, still max_tokens=32000
  PASS  (b) injected still True on the pinned replay

## PASS test_fixation_fresh_instance_picks_up_new_config


[Test 9] Fixation: a fresh fixated dict picks up the changed config
  PASS  (c) fresh dict applies config2 (effort=high)
  PASS  (c) fresh dict applies config2 (max_tokens=128000)

## PASS test_fixation_legacy_path_pinned_and_unchanged


[Test 10] Fixation: legacy path pinned too, byte-identical on first call
  PASS  (d) legacy first call: injected=True
  PASS  (d) legacy first call: model REWRITTEN (byte-identical to unfixated Test 1)
  PASS  (d) legacy first call: thinking applied
  PASS  (d) legacy first call: effort applied
  PASS  (d) legacy first call: max_tokens applied
  PASS  (d) fixated dict now holds an entry for claude-opus-4-8
  PASS  (d) SAME fixated dict: still injected despite config now disabled
  PASS  (d) SAME fixated dict: model still rewritten to claude-fable-5

## PASS test_fixation_miss_is_pinned_too


[Test 11] Fixation: a genuine miss pins 'no injection', not just a hit
  PASS  miss: injected=False on first call
  PASS  miss: fixated dict still records the (empty) snapshot
  PASS  miss stays pinned: still injected=False despite the entry now existing
  PASS  miss stays pinned: payload2 unchanged

## PASS test_fixation_load_failure_does_not_pin


[Test 12] Fixation: a load failure on first call does not pin — next call retries live
  PASS  load failure: injected=False, no raise
  PASS  load failure: nothing pinned for claude-fable-5
  PASS  next call retries live and succeeds: injected=True
  PASS  next call retries live and succeeds: effort=medium applied
  PASS  next call retries live and succeeds: now pinned for claude-fable-5

## PASS test_clear_thinking_edit_stripped_when_thinking_disabled


[Test 13] _strip_clear_thinking_edit: thinking/context_management self-consistency
  PASS  (a) clear_thinking_20251015 removed, changed=True
  PASS  (a) clear_tool_uses_20250919 survives untouched
  PASS  (a) original payload's edits list not mutated in place (still has both edits)
  PASS  (b) sole edit removed -> context_management key dropped entirely (no empty edits list)
  PASS  (c) thinking enabled -> unchanged, changed=False
  PASS  (c) thinking enabled -> context_management is the SAME object, byte-identical
  PASS  (d) no context_management -> no-op, changed=False
  PASS  (e) no clear_thinking edit present -> untouched, changed=False
  PASS  (f) model_params injection (thinking toggle OFF) set thinking to disabled
  PASS  (f) end-to-end: the self-contradictory 400-causing payload is now self-consistent

## PASS test_forwarded_delta_includes_thinking


[Test 14] _build_forwarded_delta records the forwarded 'thinking' value
  PASS  thinking ON value recorded in the forwarded_delta entry
  PASS  thinking OFF value recorded in the forwarded_delta entry
  PASS  thinking absent from payload -> key present in the entry, value None

## PASS test_context_management_strip_is_attributed


[Test 15] context_management strip: fn_map dead-code removal check + attribution_coverage fix
  PASS  (a) context_management now appears in stripped fields_delta (new: was injected-only before)
  PASS  (a) the real fn_map carries NO field-level entry at all (thinking is equally unattributed there — pre-existing dead code, not something this fix changes)
  PASS  (a) confirms by content: src/proxy/strip_inject_delta.py's own _FIELD_STRIP_FN/_FIELD_INJECT_FN have been removed entirely (they were never live)
  PASS  (b) attribution_coverage.py now attributes the strip to _strip_clear_thinking_edit, not UNATTR (got: '_strip_clear_thinking_edit (removed: thinking disabled)')
  PASS  (b) the inject side (Claude Code / _inject_context_management adding the edit) is unchanged and still correctly attributed
