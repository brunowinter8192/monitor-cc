# test_classify

9/9 strands passed

## PASS _test_system_and_core_are_essential

  PASS  WindowServer essential
  PASS  mds essential
  PASS  hot mdworker under /System stays essential
  PASS  menubar essential
  PASS  ghostty essential
  PASS  tmux server essential
  PASS  launchd essential
  PASS  Preview under /System/Applications is a user app, doubtful by memory
  PASS  hot system pids listed in summary

## PASS _test_caller_chain_and_session_are_excluded

  PASS  own claude ancestor essential
  PASS  own process essential
  PASS  sibling inside own session essential
  PASS  other monitor session still killable
  PASS  caller inside a monitor session protects that session

## PASS _test_monitor_and_worker_sessions

  PASS  monitor pane killable by session
  PASS  monitor action carries exact name and created stamp
  PASS  worker without claude killable
  PASS  worker with claude: claude doubtful
  PASS  worker with claude: its shell not killable
  PASS  worker session with claude yields no session action
  PASS  unreadable tmux: nothing is killable by session

## PASS _test_firefox_tree

  PASS  main firefox killable
  PASS  helper is covered by the main pid action
  PASS  detached crashhelper has its own exact pid action
  PASS  grep that only mentions Firefox.app is untouched
  PASS  pid actions carry lstart for the pid-reuse guard

## PASS _test_worker_proxies

  PASS  proxy of a live worker essential
  PASS  stale proxy with connections is doubtful
  PASS  stale proxy without connections is killable by exact pid
  PASS  main proxy with live parent essential
  PASS  parentless main proxy doubtful
  PASS  unreadable connection state: stale proxy is doubtful
  PASS  unreadable tmux: stale proxy is doubtful

## PASS _test_task_file_holders

  PASS  young live holder essential
  PASS  the 1h26m silent heredoc shell is doubtful with its file facts
  PASS  holder owner names the project
  PASS  orphan holder (ppid 1, no claude ancestor) killable by pid
  PASS  holder with unresolved ancestry is doubtful, never killable

## PASS _test_mineru_tree_is_protected

  PASS  convert by relative script plus exact cwd is protected
  PASS  whole spawned tree is protected
  PASS  lookalike convert in another cwd is not protected
  PASS  a Mineru substring in a script name is not protected
  PASS  explicit protect pid is honored
  PASS  protected owner names the job
  PASS  extra protect root extends the exact match

## PASS _test_doubtful_cases

  PASS  llama-server doubtful, never killable
  PASS  OrbStack doubtful, never killable
  PASS  claude main doubtful with cwd and tty facts
  PASS  cpu over threshold
  PASS  rss over threshold
  PASS  life-long burn over threshold
  PASS  quiet user process is essential
  PASS  other user daemon essential

## PASS _test_actions_are_exact_and_merged

  PASS  one action per session, not per pane
  PASS  action sums the covered load
  PASS  every action target is an exact pid or session name
  PASS  summary counts add up
