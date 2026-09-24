# tmux_launcher layout regression checks

3/3 strands passed

## PASS _strand_launch

  PASS  launch: window/pane creation sequence (7 windows, 8 panes)
  PASS  launch: pane title map (2.0/3.0 split, 4.0/5.0/6.0/6.1 shifted)
  PASS  launch: M-* copy bindings (M-w -> 4.0, M-n -> 6.1)
  PASS  launch: per-window option loop covers windows 0..6

## PASS _strand_restart_all_present

  PASS  restart, all present: zero create/split calls (pure respawn)

## PASS _strand_restart_self_heal

  PASS  restart, self-heal: whole missing window (3) recreated, single missing pane (6.1) split back in
  PASS  restart, self-heal: exactly 8 panes respawned after healing
