# t2_launch_tab report

- time: 2026-09-24 20:39:50
- every case ran in its own subprocess, all cases in parallel

| case | result | detail |
|---|---|---|
| click_handling | PASS | no desktop -> ignored; busy -> ignored; occupied desktop 2 -> launched; free desktop 4 -> launch(4, '/Users/brunowinter2000/Documents/wise2627'), panel closed; bad index ignored |
| headers | PASS | {"sessions": "[Sessions] · RAG · Models · Launch", "rag": "Sessions · [RAG] · Models · Launch", "models": "Sessions · RAG · [Models] · Launch", "launch": "Sessions · RAG · Models · [Launch]"} |
| occupied_marking | PASS | enabled {1: True, 2: True, 3: True, 4: True, 5: True}, titles {1: ' 1* ', 2: ' 2 ', 3: ' 3* ', 4: ' 4 ', 5: ' 5 '}, select occupied 1 -> [1*], select 2 -> [2], select 7 ignored |
| project_rows | PASS | 10 rows in order: ['gh-cli', 'reddit-cli', 'websearch', 'rag-cli', 'iterative-dev', 'trading', 'trading_ai', 'monitor-cc', 'general', 'wise2627'] |
| request_on_open | PASS | open() requests once on the main thread and logs when missing; granted -> silent; click/launch path never requests |
| space_switch_units | PASS | no PostEvent -> switch path raises without requesting; request function requests once and returns False | PostEvent granted -> no request, returns True | desktop -> space id for 1..5; missing and ambiguous desktop raise | hotkey key codes 18,19,20,21,23 down+up | wait_until_active: returns on target, raises switch_timeout otherwise |
| start_command | PASS | 10 commands match exactly, e.g. cd /Users/brunowinter2000/Documents/ai/monitor-cc && PATH="$HOME/.local/bin:$PATH" ./src/claude_proxy_start.sh --project /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/gh-cli |
| tick_and_selection | PASS | tick: no change -> 0 rebuilds, change -> 1 rebuild, selection kept and shows [2*], open() resets, closed panel idle |
| workflow_failures | PASS | postevent missing: no window opened, FAILED desktop=2 project=/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/gh-cli stage=switch SpaceSwitchError('postevent_not_granted') | switch timeout: no window opened, FAILED desktop=2 project=/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/gh-cli stage=switch SpaceSwitchError('switch_timeout_3s') | desktop 6: FAILED desktop=6 project=/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/gh-cli stage=validate ValueError('desktop 6 not in (1, 2, 3, 4, 5)') | unknown project: FAILED desktop=2 project=/tmp/not-in-list stage=validate ValueError('project /tmp/not-in-list not in launch list') | osascript rc=1: FAILED desktop=2 project=/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/gh-cli stage=open_window rc=1 stderr=boom |
| workflow_success | PASS | order ['switch', 'sleep', 'open']; log: OK desktop=3 project=/Users/brunowinter2000/Documents/ai/monitor-cc stage=open_window switch_ms=280 active_desktop_after=3 |

RESULT: PASS