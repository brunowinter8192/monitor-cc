# run_scenarios

Old tree: git archive of the pre-M3 commit at /tmp/pf_old. New tree: this worktree.

scenario | steps | verdict
---|---|---
hover | 51 | PASS
grow_and_new_turn | 61 | PASS
late_response | 60 | PASS
late_overlay | 60 | PASS
expand_collapse | 38 | PASS
search | 37 | PASS
width | 61 | PASS
copy_feedback | 8 | PASS
reparse | 21 | PASS
unsorted_turns | 21 | PASS
tripwire | 3 | PASS

## hover
- byte-identical mismatching steps: []
- hover-step group renders: 0
- max group renders on a grow step: 0
- change steps (label, groups rendered): [('expand', 2)]
- warm groups rendered: [43]

## grow_and_new_turn
- byte-identical mismatching steps: []
- hover-step group renders: 0
- max group renders on a grow step: 1
- change steps (label, groups rendered): []
- warm groups rendered: [22]

## late_response
- byte-identical mismatching steps: []
- hover-step group renders: 0
- max group renders on a grow step: 0
- change steps (label, groups rendered): [('resp30', 29), ('resp90', 9), ('resp150', 10), ('resp197', 8), ('resp200', 1)]
- warm groups rendered: [29]

## late_overlay
- byte-identical mismatching steps: []
- hover-step group renders: 0
- max group renders on a grow step: 0
- change steps (label, groups rendered): [('overlay_lag40', 8), ('overlay_lag20', 8), ('overlay_lag5', 8), ('overlay_lag0', 7), ('overlay_full', 21)]
- warm groups rendered: [29]

## expand_collapse
- byte-identical mismatching steps: []
- hover-step group renders: 0
- max group renders on a grow step: 0
- change steps (label, groups rendered): [("toggle('req', 20)", 1), ("toggle('sys', 20)", 1), ("toggle('tools', 20)", 1), ("toggle('beta', 20)", 1), ("toggle('fields', 20)", 1), ("toggle('req', 120)", 1), ("toggle('req', 121)", 1), ("toggle('tools', 121)", 1), ("collapse('req', 20)", 1), ("collapse('req', 120)", 1), ('refresh_strip_inactive', 1)]
- warm groups rendered: [43]

## search
- byte-identical mismatching steps: []
- hover-step group renders: 0
- max group renders on a grow step: 0
- change steps (label, groups rendered): [('search[tool]', 43), ('jump1[tool]', 1), ('jump2[tool]', 1), ('jump3[tool]', 1), ('search[system-reminder]', 43), ('jump1[system-reminder]', 1), ('jump2[system-reminder]', 2), ('jump3[system-reminder]', 2), ('search_cleared', 32)]
- warm groups rendered: [43]

## width
- byte-identical mismatching steps: []
- hover-step group renders: 0
- max group renders on a grow step: 0
- change steps (label, groups rendered): [('width60', 43), ('width80', 43), ('width100', 43), ('width120', 43), ('width80', 43), ('width60', 43)]
- warm groups rendered: [43]

## copy_feedback
- byte-identical mismatching steps: []
- hover-step group renders: 0
- max group renders on a grow step: 0
- change steps (label, groups rendered): [('flash_req5', 1), ('flash_msg20', 1), ('flash_expired', 2), ('flash_empty', 0), ('feedback_none', 43)]
- warm groups rendered: [43]

## reparse
- byte-identical mismatching steps: []
- hover-step group renders: 0
- max group renders on a grow step: 0
- change steps (label, groups rendered): [('after_reset', 15), ('after_refill', 29)]
- warm groups rendered: [22]

## unsorted_turns
- byte-identical mismatching steps: []
- hover-step group renders: 0
- max group renders on a grow step: 0
- change steps (label, groups rendered): [('swapped', 1), ('sorted_again', 2)]
- warm groups rendered: [43]

## tripwire
- byte-identical mismatching steps: n/a
- tripwire outcomes: ['ValueError', 'ValueError', 'ValueError']

subprocess failures: []
