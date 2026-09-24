# test_open_or_focus_monitor

7/7 strands passed

## PASS _test_session_name_reused_not_rederived

  [OK  ] system.generate_session_name IS tmux_launcher.generate_session_name: <function generate_session_name at 0x108055b10>
  [OK  ] session name for a cwd with a space matches tmux_launcher exactly: got='monitor_cc_cbef93a6' expected='monitor_cc_cbef93a6'
  [OK  ] session name has the monitor_cc_<8-hex> shape: name='monitor_cc_cbef93a6'

## PASS _test_launch_cmd_quotes_cwd_with_space

  [OK  ] cd target is the given root, shell-quoted: cd_part='cd /Users/x/monitor-cc'
  [OK  ] cwd survives shlex round-trip as exactly one argument (not split/executed): parsed=['/opt/homebrew/bin/python3', 'workflow.py', '--project', '/tmp/my project; rm -rf /']

## PASS _test_existing_session_killed_then_relaunched

  [OK  ] existing session → kill_session called with the derived session name: calls={'checked': 'monitor_cc_5e3ed678', 'kill': 'monitor_cc_5e3ed678', 'launch': '/tmp/existing-project'}
  [OK  ] existing session → _launch_monitor called with the row cwd afterwards: calls={'checked': 'monitor_cc_5e3ed678', 'kill': 'monitor_cc_5e3ed678', 'launch': '/tmp/existing-project'}

## PASS _test_branch_launches_when_session_absent

  [OK  ] no session → _launch_monitor called with the row cwd: calls={'checked': 'monitor_cc_3d463546', 'kill': None, 'launch': '/tmp/new-project'}
  [OK  ] no session → kill_session NOT called: calls={'checked': 'monitor_cc_3d463546', 'kill': None, 'launch': '/tmp/new-project'}

## PASS _test_empty_cwd_is_noop

  [OK  ] empty cwd short-circuits before any tmux/kill/launch call: calls={'checked': None, 'kill': None, 'launch': None}

## PASS _test_resolve_python3_uses_plist_path_under_bare_environ

  [OK  ] python3 resolved under a bare PATH comes from the fixture plist PATH: resolved='/var/folders/t2/_8msw65s0glfkr10g1mp_4g40000gn/T/tmpx2jew79v/plist_bin/python3' expected='/var/folders/t2/_8msw65s0glfkr10g1mp_4g40000gn/T/tmpx2jew79v/plist_bin/python3' stderr=''
  [OK  ] an empty plist PATH does not resolve to the fixture python3: resolved='/usr/bin/python3' stderr=''

## PASS _test_launch_monitor_uses_native_path_only

  [OK  ] _ghostty_version removed from system.py: hasattr=False
  [OK  ] _launch_monitor_ghostty_fallback removed from system.py: hasattr=False
  [OK  ] _launch_monitor calls _launch_monitor_ghostty_native unconditionally: calls={'native': 'cd /Users/brunowinter2000/Documents/ai/monitor-cc/.claude/worktrees/mcfix-tests3 && /opt/homebrew/bin/python3 workflow.py --project /tmp/native-path-project'}
