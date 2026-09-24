# test_monitor_sweep_scheduler

6/6 strands passed

## PASS _test_pure_gate_boundaries

  [OK  ] fresh state (last_ts=0.0) is due
  [OK  ] a run 1h ago is NOT due
  [OK  ] a run 25h ago IS due
  [OK  ] exactly 24h ago IS due (>= boundary, not >)

## PASS _test_fresh_state_runs

  [OK  ] fresh state (no state file) triggers a sweep attempt

## PASS _test_run_1h_ago_does_not_run

  [OK  ] a run 1h ago does NOT trigger a sweep attempt

## PASS _test_run_25h_ago_runs

  [OK  ] a run 25h ago DOES trigger a sweep attempt

## PASS _test_reentry_guard_blocks_concurrent_trigger

  [OK  ] a concurrent tick while a sweep is in-progress does not re-trigger

## PASS _test_attempt_timestamp_persisted_before_sweep_completes

  [OK  ] attempt timestamp is on disk before the sweep itself finishes
