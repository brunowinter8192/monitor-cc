# verify_against_ps

Run: 2026-09-25T16:45:50+00:00

- OK   pid sets: snapshot 887, ps 885, only in snapshot 5, only in ps 3 (churn between the two reads)
- OK   parent links equal for 882 shared pids, mismatches 0
- OK   firefox members: ps 16, snapshot 16, differing 0
- OK   monitor sessions: tmux ['monitor_cc_25c51a2e', 'monitor_cc_52070e64', 'monitor_cc_52fce57c', 'monitor_cc_sysloadtest'] vs actions ['monitor_cc_25c51a2e', 'monitor_cc_52070e64', 'monitor_cc_52fce57c', 'monitor_cc_sysloadtest']
- OK   group counts {'killable': 43, 'doubtful': 9, 'essential': 835} add up to 887 rows
- INFO top-10 CPU overlap between top(instant) and ps(decaying average): 6/10; snapshot top [403, 762, 864, 9571, 76068, 57133, 395, 57157, 554, 92925]; ps top [9571, 25614, 92925, 762, 94451, 57157, 505, 76068, 403, 24442]
