# P5 -- proxy pane message-row copy-by-click probe run (2026-09-14T12:44:16.347338+00:00)

**Result: 29/29 checks passed**

| Check | Result |
|---|---|
| both message rows keyed | PASS |
| both message rows registered as copy rows | PASS |
| REQ row still registered as a copy row too | PASS |
| msg[0] serialization non-empty | PASS |
| msg[1] serialization non-empty | PASS |
| msg[0] text appears verbatim inside the REQ-level copy | PASS |
| msg[1] text appears verbatim inside the REQ-level copy | PASS |
| msg[0] exact text | PASS |
| msg[1] exact text | PASS |
| main: click on msg row 0 copy column triggers copy | PASS |
| main: flash keyed by the msg's own key, not entry_idx | PASS |
| main: sibling msg row does NOT flash from this copy | PASS |
| main: click on msg row 1 copy column triggers copy | PASS |
| main: non-copy click on msg row returns no-change | PASS |
| main: non-copy click on msg row leaves expand_states untouched | PASS |
| main: non-copy click on msg row writes nothing to clipboard | PASS |
| main: REQ copy-click still fires | PASS |
| main: REQ flash keyed by entry_idx (unchanged) | PASS |
| worker: click on msg row 0 copy column triggers copy | PASS |
| worker: flash keyed by the msg's own key, not entry_idx | PASS |
| worker: sibling msg row does NOT flash from this copy | PASS |
| worker: click on msg row 1 copy column triggers copy | PASS |
| worker: non-copy click on msg row returns no-change | PASS |
| worker: non-copy click on msg row leaves expand_states untouched | PASS |
| worker: non-copy click on msg row writes nothing to clipboard | PASS |
| worker: REQ copy-click still fires | PASS |
| worker: REQ flash keyed by entry_idx (unchanged) | PASS |
| message keys still present at narrow width (rendering itself unaffected) | PASS |
| no msg row registered as a copy row at width=10 | PASS |
