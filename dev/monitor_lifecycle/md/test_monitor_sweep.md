# test_monitor_sweep

1/1 strands passed

## PASS _test_sweep_kills_old_spares_new_and_worker

  [OK  ] enumeration includes testold
  [OK  ] enumeration includes testnew
  [OK  ] enumeration excludes worker-* session
  [OK  ] testold session killed
  [OK  ] testnew session spared
  [OK  ] worker-* session untouched
  [OK  ] testold pane process reaped (no orphan)
  [OK  ] testnew pane process still alive
  [OK  ] worker-* pane process untouched
  [OK  ] log recorded testold as KILLED
  [OK  ] log recorded testnew as SPARED
