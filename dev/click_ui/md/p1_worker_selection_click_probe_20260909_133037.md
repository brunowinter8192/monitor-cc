# P1 -- worker-selection click probe run (2026-09-09T13:30:37.282887+00:00)

**Result: 35/35 checks passed**

| Check | Result |
|---|---|
| worker-proxy: one header region per worker | PASS |
| worker-proxy: region targets match worker names | PASS |
| worker-proxy: region coordinates plausible (1-based, sc<=ec, er>=1) | PASS |
| worker-proxy: header regions do not overlap | PASS |
| worker-proxy: digit-key '1' selects 'alice' | PASS |
| worker-proxy: click at col 18 row 2 on '[1]alice' selects it | PASS |
| worker-proxy: click/key parity for 'alice' | PASS |
| worker-proxy: digit-key '2' selects 'bob' | PASS |
| worker-proxy: click at col 27 row 2 on '[2]bob' selects it | PASS |
| worker-proxy: click/key parity for 'bob' | PASS |
| worker-proxy: digit-key '3' selects 'carol' | PASS |
| worker-proxy: click at col 36 row 2 on '[3]carol' selects it | PASS |
| worker-proxy: click/key parity for 'carol' | PASS |
| worker-proxy wrap: all 4 markers have >=1 region at pane_width=200 | PASS |
| worker-proxy wrap: all 4 markers have >=1 region at pane_width=60 | PASS |
| worker-proxy wrap: click on segment (54, 60, 2) of straddling '[4]delta' (pane_width=60) selects it | PASS |
| worker-proxy wrap: click on segment (1, 1, 3) of straddling '[4]delta' (pane_width=60) selects it | PASS |
| worker-proxy wrap: all 4 markers have >=1 region at pane_width=40 | PASS |
| worker-proxy wrap: click on segment (34, 40, 2) of straddling '[3]gamma-long-name' (pane_width=40) selects it | PASS |
| worker-proxy wrap: click on segment (1, 11, 3) of straddling '[3]gamma-long-name' (pane_width=40) selects it | PASS |
| worker-proxy wrap: all 4 markers have >=1 region at pane_width=30 | PASS |
| worker-proxy wrap: click on segment (25, 30, 2) of straddling '[2]beta' (pane_width=30) selects it | PASS |
| worker-proxy wrap: click on segment (1, 1, 3) of straddling '[2]beta' (pane_width=30) selects it | PASS |
| worker-proxy wrap: click on segment (24, 30, 3) of straddling '[4]delta' (pane_width=30) selects it | PASS |
| worker-proxy wrap: click on segment (1, 1, 4) of straddling '[4]delta' (pane_width=30) selects it | PASS |
| worker-proxy wrap: sweep actually forced >=1 straddling marker | PASS |
| workers-pane: one header-row region per worker | PASS |
| workers-pane: header-row coordinates plausible (row>=1) | PASS |
| workers-pane: digit-key '1' expands+selects 'w1' | PASS |
| workers-pane: click on row 4 ('w1') produces same expand+select | PASS |
| workers-pane: click/key parity for 'w1' | PASS |
| workers-pane: digit-key '2' expands+selects 'w2' | PASS |
| workers-pane: click on row 7 ('w2') produces same expand+select | PASS |
| workers-pane: click/key parity for 'w2' | PASS |
| workers-pane: scroll wheel on a worker row still handled (no collision) | PASS |
