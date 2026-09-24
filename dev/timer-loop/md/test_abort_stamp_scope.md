# test_abort_stamp_scope

1/1 strands passed

## PASS _test_abort_stamps_only_own_file

  [OK  ] killed PID's own file gets stamped: killed_count=1 content='aborted\n'
  [OK  ] killed PID's process actually terminated: poll=-15
  [OK  ] foreign 0-byte file (no associated PID) NOT stamped: content=''
  [OK  ] live wait's file in another session untouched (content): content=''
  [OK  ] live wait's process in another session still alive: poll=None
  [OK  ] [abort] log line lists only the stamped file: 2026-09-25T00:06:38 [abort] 2026-09-25T00:06:38.131 abort_action pids=[69244] killed=1 errors=0 stamped=[/private/var/folders/t2/_8msw65s0glfkr10g1mp_4g40000gn/T/abort_stamp_scope_vzwri7p0/bkilledtask1.output]
