# t1_autojump_removal report

- time: 2026-09-24 21:27:13

| check | result | detail |
|---|---|---|
| menubar log and settings resolve under the isolated home | PASS | MENUBAR_LOG=/var/folders/t2/_8msw65s0glfkr10g1mp_4g40000gn/T/session_launcher_home_ttz_fw4d/Library/Application Support/com.brunowinter.monitor-cc-menubar/menubar.log |
| no auto-jump identifiers in any .py under src/ and dev/ | PASS | scanned src/ and dev/, 0 hits |
| old settings.json with the removed key still loads | PASS | loaded (500, 480) |
| settings without a file fall back to panel defaults | PASS | defaults (422, 460) |
| save writes only panel_width and panel_min_height | PASS | file after save: {'panel_width': 510, 'panel_min_height': 470} |
| FocusController keeps status tracking, has no tick | PASS | statuses_changed True then False after update_statuses |
| PanelSettings has two fields, controller has no toggle action | PASS | PanelSettings fields ['panel_min_height', 'panel_width'] |

RESULT: PASS