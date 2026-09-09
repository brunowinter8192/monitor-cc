# 2026-09-09 — message_passes split and helper extraction (refactor scan, cohesion step)

## Context

Part of the src-wide refactor scan (Phase 1 Step 2, cohesion). Thresholds applied as fixed:
file ≤ 400 LOC, function < 50 LOC, 100 LOC a hard target. `message_passes.py` was 616 LOC and
`_apply_first_pass` 100 LOC; fifteen further proxy functions sat between 50 and 73 LOC.

## What was done

- `message_passes.py` split by concern into three modules: the four structural passes stayed
  (`_apply_role_system_strip`, `_apply_first_pass`, `_apply_cumulative_sr_strips`,
  `_apply_final_sr_pass`); the eight template-shaped passes became one generic runner plus one
  declarative spec each in `message_passes_simple.py`; the wake-up concern
  (`_dedup_wakeup_blocks`, `_unwrap_full_sr_wrapper`, `_SR_FULL_WRAP_RE`) moved to
  `message_passes_wakeup.py`.
- `_apply_first_pass` dropped to under 50 LOC via one handler per elif branch.
- `_strip_bg_launch_ack` and `_strip_interrupt_marker` were found to be the byte-identical
  content walk (str, text block, tool_result with str or list-of-text inner) differing only in
  predicate and replacement; both now delegate to
  `payload_helpers._walk_replace_marker_blocks`. The six other strip modules were checked and
  left alone: `strip_hook_prefix`/`strip_git_lock`/`strip_bd_noise` share a second, distinct
  always-transform shape; `strip_po` lacks their equality guard; `strip_sn_notice` and
  `strip_bg_completed` do not descend into tool_result at all.
- Fifteen helper extractions in `cache`, `diff_engine`, `logging`, `message_summary`, `rules`,
  `rules_config`, `strip_inject_delta`, `strip_vocab`.

## Evidence

- `dev/proxy/pipeline_byte_identity.py` (new) replays the full write-side pipeline
  (`apply_modification_rules` → `_strip_all_cache_control` → `_set_cache_breakpoints` →
  `_build_forwarded_delta` → `_build_stripped_injected_deltas` → `_build_errors_entries`) over a
  frozen 60-request prefix of a real `_original.jsonl`, for both `main` and `worker:x` context,
  timestamps normalized out. Hash before and after the refactor:
  `8bc6bde611342924989faf234f728969d31b2112c58d3ceb415254da9ec4d825`, identical.
- The eight existing proxy test scripts and the 13 dual_log_cli tests all passed after the split.

## Pitfalls recorded

- The live `_original.jsonl` grows during a session, so the harness needs a pinned snapshot
  (`PROXY_PIPELINE_BYTE_IDENTITY_LOG` env override) for a before/after comparison.
- Spec differences between the eight template passes are load-bearing: guard function
  (`_content_contains` vs `_top_level_content_contains`), multi-marker any-guard,
  `pass_injected_by_idx` only for bg-exit, `full_replace=True` on three passes, and
  `_apply_sn_notice_strip`'s two-role gate with a role=system skip predicate. Each is expressed
  in its spec dict, not in the runner.
- The worker that performed this milestone died at its context limit during the recap; this
  entry was written by the orchestrator from the worker's completion report.
