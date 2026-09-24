# s1_switch_probe report

- time: 2026-09-24 20:04:35
- home desktop: 2
- permissions of this process: {'Accessibility': True, 'PostEvent': True, 'ListenEvent': True, 'ScreenCapture': True}
- ms = time from posting the action until CGSGetActiveSpace equals the target space (poll 20 ms, timeout 3 s)

| variant | works | ms | observed desktop | returned home | note |
|---|---|---|---|---|---|
| a1 CGEventPost session flags -> desktop 3 | yes | 284 | 3 | True |  |
| a1 CGEventPost session flags -> desktop 5 | yes | 288 | 5 | True |  |
| a2 CGEventPost HID flags -> desktop 3 | yes | 283 | 3 | True |  |
| a2 CGEventPost HID flags -> desktop 5 | yes | 276 | 5 | True |  |
| a3 CGEventPost session explicit ctrl -> desktop 3 | yes | 270 | 3 | True |  |
| a3 CGEventPost session explicit ctrl -> desktop 5 | yes | 276 | 5 | True |  |
| b System Events key code -> desktop 3 | yes | 283 | 3 | True |  |
| b System Events key code -> desktop 5 | yes | 271 | 5 | True |  |
| d1 CGEventPost Ctrl+Arrow -> desktop 3 | yes | 994 | 3 | True |  |
| d2 System Events Ctrl+Arrow -> desktop 3 | yes | 990 | 3 | True |  |
| c_joshuarli 1-step -> desktop 3 | yes | 23 | 3 | True |  |
| c_joshuarli 3-step -> desktop 5 | yes | 68 | 5 | True |  |
| c_jurplel 1-step -> desktop 3 | yes | 48 | 3 | True |  |
| c_jurplel 3-step -> desktop 5 | yes | 25 | 5 | True |  |
