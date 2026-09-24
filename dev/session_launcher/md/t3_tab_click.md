# t3_tab_click report

- time: 2026-09-24 21:28:45
- every case ran in its own subprocess with an isolated HOME, all cases in parallel
- no panel is shown and no real mouse event is sent; clicks use NSButton.performClick_ on unshown panels

| case | result | detail |
|---|---|---|
| click_routing | PASS | 16 clicks (4 open tabs x 4 buttons): 12 switch to (current, target) exactly once, 4 active-tab clicks do nothing; no open tab -> nothing |
| header_recentering | PASS | header stays centered in the top-bar strip when the panel width changes (422, 522, 322): ['Sessions', 'RAG', 'Models', 'Launch'] |
| header_structure | PASS | Sessions: 4 buttons tags 0-3 + 3 separators, text [Sessions]... | RAG: 4 buttons tags 0-3 + 3 separators, text Sessions... | Models: 4 buttons tags 0-3 + 3 separators, text Sessions... | Launch: 4 buttons tags 0-3 + 3 separators, text Sessions... |
| pieces_and_keys | PASS | header text exact for all 4 active tabs, TAB_KEYS ('main', 'rag', 'models', 'launch'), ring == TAB_KEYS |
| visual_equivalence | PASS | Sessions: ink px old 140-663 new 139-663 of 800, 4.9% pixels differ | RAG: ink px old 135-663 new 134-663 of 800, 4.0% pixels differ | Models: ink px old 135-663 new 134-663 of 800, 4.7% pixels differ | Launch: ink px old 135-659 new 134-658 of 800, 4.9% pixels differ |
| wiring | PASS | _ensure_wired left all 16 header buttons (4 headers x 4) with the panel controller as target and action selectTab: |

RESULT: PASS