# test_parsers_and_guards

6/6 strands passed

## PASS _test_parse_ps_and_clock

  PASS  daemon fields
  PASS  lstart is the five-token start time
  PASS  command survives
  PASS  day-prefixed etime
  PASS  cputime with fraction
  PASS  tty and args survive
  PASS  short line is skipped
  PASS  mm:ss clock

## PASS _test_parse_top_lsof_tmux

  PASS  only the last top sample is used
  PASS  no header gives empty
  PASS  lsof pairs carry the holder pid
  PASS  tmux sessions parsed, malformed skipped
  PASS  tmux panes parsed

## PASS _test_confirm_uses_exact_identity

  PASS  same lstart confirms
  PASS  other lstart is a reused pid
  PASS  vanished pid with empty stamp never confirms
  PASS  unreadable ps never confirms
  PASS  non-numeric pid never confirms
  PASS  session with same created confirms
  PASS  session with other created is a recreated session
  PASS  missing session does not confirm

## PASS _test_diff_reports_outcomes

  PASS  killed session reported gone
  PASS  killed pid reported gone
  PASS  nothing new after
  PASS  survivors are flagged
  PASS  respawned targets show up as new

## PASS _test_render_shows_all_groups

  PASS  summary lists three groups
  PASS  actions block present with the exact target
  PASS  json path echoed
  PASS  report json round-trips

## PASS _test_package_has_no_termination_code

  PASS  __init__.py has no os.kill
  PASS  __init__.py has no signal
  PASS  __init__.py has no killpg
  PASS  __init__.py has no pkill
  PASS  __init__.py has no killall
  PASS  __init__.py has no kill-session
  PASS  __init__.py has no SIGTERM
  PASS  __init__.py has no SIGKILL
  PASS  __main__.py has no os.kill
  PASS  __main__.py has no signal
  PASS  __main__.py has no killpg
  PASS  __main__.py has no pkill
  PASS  __main__.py has no killall
  PASS  __main__.py has no kill-session
  PASS  __main__.py has no SIGTERM
  PASS  __main__.py has no SIGKILL
  PASS  classify.py has no os.kill
  PASS  classify.py has no signal
  PASS  classify.py has no killpg
  PASS  classify.py has no pkill
  PASS  classify.py has no killall
  PASS  classify.py has no kill-session
  PASS  classify.py has no SIGTERM
  PASS  classify.py has no SIGKILL
  PASS  cli.py has no os.kill
  PASS  cli.py has no signal
  PASS  cli.py has no killpg
  PASS  cli.py has no pkill
  PASS  cli.py has no killall
  PASS  cli.py has no kill-session
  PASS  cli.py has no SIGTERM
  PASS  cli.py has no SIGKILL
  PASS  collect.py has no os.kill
  PASS  collect.py has no signal
  PASS  collect.py has no killpg
  PASS  collect.py has no pkill
  PASS  collect.py has no killall
  PASS  collect.py has no kill-session
  PASS  collect.py has no SIGTERM
  PASS  collect.py has no SIGKILL
  PASS  config.py has no os.kill
  PASS  config.py has no signal
  PASS  config.py has no killpg
  PASS  config.py has no pkill
  PASS  config.py has no killall
  PASS  config.py has no kill-session
  PASS  config.py has no SIGTERM
  PASS  config.py has no SIGKILL
  PASS  confirm.py has no os.kill
  PASS  confirm.py has no signal
  PASS  confirm.py has no killpg
  PASS  confirm.py has no pkill
  PASS  confirm.py has no killall
  PASS  confirm.py has no kill-session
  PASS  confirm.py has no SIGTERM
  PASS  confirm.py has no SIGKILL
  PASS  diff.py has no os.kill
  PASS  diff.py has no signal
  PASS  diff.py has no killpg
  PASS  diff.py has no pkill
  PASS  diff.py has no killall
  PASS  diff.py has no kill-session
  PASS  diff.py has no SIGTERM
  PASS  diff.py has no SIGKILL
  PASS  render.py has no os.kill
  PASS  render.py has no signal
  PASS  render.py has no killpg
  PASS  render.py has no pkill
  PASS  render.py has no killall
  PASS  render.py has no kill-session
  PASS  render.py has no SIGTERM
  PASS  render.py has no SIGKILL
  PASS  snapshot.py has no os.kill
  PASS  snapshot.py has no signal
  PASS  snapshot.py has no killpg
  PASS  snapshot.py has no pkill
  PASS  snapshot.py has no killall
  PASS  snapshot.py has no kill-session
  PASS  snapshot.py has no SIGTERM
  PASS  snapshot.py has no SIGKILL
