# P1 -- worker-selection click probe run (2026-09-15T19:24:51.493027+00:00)

**Result: 75/75 checks passed**

| Check | Result |
|---|---|
| worker-proxy: one header region per worker | PASS |
| worker-proxy: region targets match worker names | PASS |
| worker-proxy: region coordinates plausible (1-based, sc<=ec, er>=1) | PASS |
| worker-proxy: header regions do not overlap | PASS |
| worker-proxy: digit-key '1' selects 'alice' | PASS |
| worker-proxy: click at col 24 row 2 on '[1]alice' selects it | PASS |
| worker-proxy: click/key parity for 'alice' | PASS |
| worker-proxy: digit-key '2' selects 'bob' | PASS |
| worker-proxy: click at col 44 row 2 on '[2]bob' selects it | PASS |
| worker-proxy: click/key parity for 'bob' | PASS |
| worker-proxy: digit-key '3' selects 'carol' | PASS |
| worker-proxy: click at col 64 row 2 on '[3]carol' selects it | PASS |
| worker-proxy: click/key parity for 'carol' | PASS |
| worker-proxy wrap: all 4 markers have >=1 region at pane_width=200 | PASS |
| worker-proxy wrap: all 4 markers have >=1 region at pane_width=60 | PASS |
| worker-proxy wrap: click on segment (56, 60, 2) of straddling '[3]gamma-long-name' (pane_width=60) selects it | PASS |
| worker-proxy wrap: click on segment (1, 24, 3) of straddling '[3]gamma-long-name' (pane_width=60) selects it | PASS |
| worker-proxy wrap: all 4 markers have >=1 region at pane_width=40 | PASS |
| worker-proxy wrap: click on segment (36, 40, 2) of straddling '[2]beta' (pane_width=40) selects it | PASS |
| worker-proxy wrap: click on segment (1, 13, 3) of straddling '[2]beta' (pane_width=40) selects it | PASS |
| worker-proxy wrap: click on segment (16, 40, 3) of straddling '[3]gamma-long-name' (pane_width=40) selects it | PASS |
| worker-proxy wrap: click on segment (1, 4, 4) of straddling '[3]gamma-long-name' (pane_width=40) selects it | PASS |
| worker-proxy wrap: all 4 markers have >=1 region at pane_width=30 | PASS |
| worker-proxy wrap: click on segment (15, 30, 2) of straddling '[1]alpha' (pane_width=30) selects it | PASS |
| worker-proxy wrap: click on segment (1, 3, 3) of straddling '[1]alpha' (pane_width=30) selects it | PASS |
| worker-proxy wrap: click on segment (26, 30, 3) of straddling '[3]gamma-long-name' (pane_width=30) selects it | PASS |
| worker-proxy wrap: click on segment (1, 24, 4) of straddling '[3]gamma-long-name' (pane_width=30) selects it | PASS |
| worker-proxy wrap: click on segment (27, 30, 4) of straddling '[4]delta' (pane_width=30) selects it | PASS |
| worker-proxy wrap: click on segment (1, 15, 5) of straddling '[4]delta' (pane_width=30) selects it | PASS |
| worker-proxy wrap: sweep actually forced >=1 straddling marker | PASS |
| worker-tokens: one header region per worker | PASS |
| worker-tokens: region targets match worker names | PASS |
| worker-tokens: region coordinates plausible (1-based, sc<=ec, er>=1) | PASS |
| worker-tokens: digit-key '1' selects 'w1' | PASS |
| worker-tokens: click at col 24 row 2 on '[1]w1' selects it | PASS |
| worker-tokens: click/key parity for 'w1' | PASS |
| worker-tokens: digit-key '2' selects 'w2' | PASS |
| worker-tokens: click at col 41 row 2 on '[2]w2' selects it | PASS |
| worker-tokens: click/key parity for 'w2' | PASS |
| worker-tokens wrap: all 5 markers have >=1 region at pane_width=200 | PASS |
| worker-tokens wrap: click on segment (16, 45, 2) of 'capture-git-status' (pane_width=200) selects it | PASS |
| worker-tokens wrap: click on segment (48, 75, 2) of 'devproxy-docs' (pane_width=200) selects it | PASS |
| worker-tokens wrap: click on segment (78, 106, 2) of 'gcommit-umlaut' (pane_width=200) selects it | PASS |
| worker-tokens wrap: click on segment (109, 140, 2) of 'spawn-placement-msg' (pane_width=200) selects it | PASS |
| worker-tokens wrap: click on segment (143, 169, 2) of 'verifier-retire' (pane_width=200) selects it | PASS |
| worker-tokens wrap: all 5 markers have >=1 region at pane_width=60 | PASS |
| worker-tokens wrap: click on segment (16, 45, 2) of 'capture-git-status' (pane_width=60) selects it | PASS |
| worker-tokens wrap: click on segment (48, 60, 2) of 'devproxy-docs' (pane_width=60) selects it | PASS |
| worker-tokens wrap: click on segment (1, 15, 3) of 'devproxy-docs' (pane_width=60) selects it | PASS |
| worker-tokens wrap: click on segment (18, 46, 3) of 'gcommit-umlaut' (pane_width=60) selects it | PASS |
| worker-tokens wrap: click on segment (49, 60, 3) of 'spawn-placement-msg' (pane_width=60) selects it | PASS |
| worker-tokens wrap: click on segment (1, 20, 4) of 'spawn-placement-msg' (pane_width=60) selects it | PASS |
| worker-tokens wrap: click on segment (23, 49, 4) of 'verifier-retire' (pane_width=60) selects it | PASS |
| worker-tokens wrap: all 5 markers have >=1 region at pane_width=40 | PASS |
| worker-tokens wrap: click on segment (16, 40, 2) of 'capture-git-status' (pane_width=40) selects it | PASS |
| worker-tokens wrap: click on segment (1, 5, 3) of 'capture-git-status' (pane_width=40) selects it | PASS |
| worker-tokens wrap: click on segment (8, 35, 3) of 'devproxy-docs' (pane_width=40) selects it | PASS |
| worker-tokens wrap: click on segment (38, 40, 3) of 'gcommit-umlaut' (pane_width=40) selects it | PASS |
| worker-tokens wrap: click on segment (1, 26, 4) of 'gcommit-umlaut' (pane_width=40) selects it | PASS |
| worker-tokens wrap: click on segment (29, 40, 4) of 'spawn-placement-msg' (pane_width=40) selects it | PASS |
| worker-tokens wrap: click on segment (1, 20, 5) of 'spawn-placement-msg' (pane_width=40) selects it | PASS |
| worker-tokens wrap: click on segment (23, 40, 5) of 'verifier-retire' (pane_width=40) selects it | PASS |
| worker-tokens wrap: click on segment (1, 9, 6) of 'verifier-retire' (pane_width=40) selects it | PASS |
| worker-tokens wrap: all 5 markers have >=1 region at pane_width=34 | PASS |
| worker-tokens wrap: click on segment (16, 34, 2) of 'capture-git-status' (pane_width=34) selects it | PASS |
| worker-tokens wrap: click on segment (1, 11, 3) of 'capture-git-status' (pane_width=34) selects it | PASS |
| worker-tokens wrap: click on segment (14, 34, 3) of 'devproxy-docs' (pane_width=34) selects it | PASS |
| worker-tokens wrap: click on segment (1, 7, 4) of 'devproxy-docs' (pane_width=34) selects it | PASS |
| worker-tokens wrap: click on segment (10, 34, 4) of 'gcommit-umlaut' (pane_width=34) selects it | PASS |
| worker-tokens wrap: click on segment (1, 4, 5) of 'gcommit-umlaut' (pane_width=34) selects it | PASS |
| worker-tokens wrap: click on segment (7, 34, 5) of 'spawn-placement-msg' (pane_width=34) selects it | PASS |
| worker-tokens wrap: click on segment (1, 4, 6) of 'spawn-placement-msg' (pane_width=34) selects it | PASS |
| worker-tokens wrap: click on segment (7, 33, 6) of 'verifier-retire' (pane_width=34) selects it | PASS |
| worker-tokens wrap: the narrow sweep actually forced >=1 straddling marker | PASS |
| worker-tokens wrap: pane_width=34 (the pane's real 34% window share) was swept | PASS |
