# test_strip_markers: highlight_stripped

2/2 strands passed

## PASS test_highlight_stripped_basic


[1;34m============================================================
  1. highlight_stripped — basic
============================================================[0m
[2m  outer_bg='' (ZEBRA_BG_A)[0m
[48;2;94;81;47m<system-reminder>The following skills are available for use with the Skill tool:[39m
[48;2;94;81;47m- bead-cli[39m
[48;2;94;81;47m- iterative-dev[39m
[48;2;94;81;47m</system-remi...
[2m  outer_bg=ZEBRA_BG_B[0m
[48;2;94;81;47m<system-reminder>The following skills are available for use with the Skill tool:[39m
[48;2;94;81;47m- bead-cli[39m
[48;2;94;81;47m- iterative-dev[39m
[48;2;94;81;47m</system-remi...
[2m  no chunks → passthrough[0m
  ✓ unchanged: <system-reminder>The following skills are available for use 
[2m  chunk not found → graceful skip[0m
  ✓ unchanged: foo bar
[2m  multiple occurrences[0m
  ✓ 2 occurrences highlighted: AAA [48;2;94;81;47mremove_me[39m BBB [48;2;94;81;47mremove_me[39m CCC
[0m

## PASS test_highlight_stripped_multiline_chunk


[1;34m============================================================
  1b. highlight_stripped — multi-line chunk per-line coverage
============================================================[0m
[2m  input text lines: 5, output split lines: 5[0m
[2m    line 0: bg=no  | 'PREFIX'[0m
[2m    line 1: bg=YES | '\x1b[48;2;94;81;47mA\x1b[39m'[0m
[2m    line 2: bg=YES | '\x1b[48;2;94;81;47mB\x1b[39m'[0m
[2m    line 3: bg=YES | '\x1b[48;2;94;81;47mC\x1b[39m'[0m
[2m    line 4: bg=no  | 'SUFFIX'[0m
  ✓ all 3 chunk lines carry DIM_YELLOW_BG
[2m  outer_bg=ZEBRA_BG_B — restored after final chunk line[0m
  ✓ outer_bg ZEBRA_BG_B present on final chunk line after SOFT_RESET
[0m
