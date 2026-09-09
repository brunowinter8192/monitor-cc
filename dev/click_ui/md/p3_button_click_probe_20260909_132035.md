# P3 -- pane-chrome button click probe run (2026-09-09T13:20:35.044235+00:00)

**Result: 32/32 checks passed**

| Check | Result |
|---|---|
| warnings: [refresh] button region registered | PASS |
| warnings: exactly one header region, on row 2 (shifted past the new search bar) | PASS |
| warnings: button text visible in header | PASS |
| warnings: 'r' key sets _force_refresh | PASS |
| warnings: click on [refresh] sets _force_refresh (same as key) | PASS |
| warnings: width guard -- no region and no button text when pane_width=10 | PASS |
| workers: freeze region registered live | PASS |
| workers: freeze region registered frozen | PASS |
| workers: badge reads [LIVE] when not frozen | PASS |
| workers: badge reads [FROZEN] when frozen | PASS |
| workers: 'f' key toggles frozen False->True | PASS |
| workers: click on freeze badge toggles frozen False->True (same as key) | PASS |
| workers: click on freeze badge toggles frozen True->False | PASS |
| workers: clicking the freeze badge did not select/expand a worker (no collision) | PASS |
| workers: normal row click still selects+expands (milestone-1 undisturbed) | PASS |
| workers: width guard -- no freeze region when pane_width=10 (too narrow) | PASS |
| proxy: _build_proxy_output returns a plain string (header+'\n'+body baked in) | PASS |
| proxy: search bar text visible on the first line | PASS |
| proxy: no leftover _proxy_header_regions module attribute (that was the reverted-button's) | PASS |
| proxy: no leftover _format_proxy_header function in format.py (that was the reverted-button's) | PASS |
| proxy: row 1 is NOT a body key (it's the search bar) | PASS |
| proxy: row 2 resolves to a body row (REQ key) | PASS |
| proxy: click on row 1 focuses the search bar | PASS |
| proxy: click on row 2 toggles expand/collapse at the shifted row | PASS |
| proxy: at least one copy row registered | PASS |
| proxy: copy row is >= 2 (never lands on the header row) | PASS |
| proxy: copy-symbol click still fires at its own shifted row | PASS |
| proxy: 'u' key (_undo_proxy_expand) still undoes the last toggle, unchanged | PASS |
| proxy: scroll wheel (button 64) still works | PASS |
| proxy: first body row after header shift is >= 2 | PASS |
| proxy: _proxy_just_expanded set by the click | PASS |
| proxy: just-expanded entry stays visible in the next render (auto-scroll intact) | PASS |
