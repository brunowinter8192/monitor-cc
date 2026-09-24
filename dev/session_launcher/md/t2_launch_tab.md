# t2_launch_tab report

- time: 2026-09-24 20:29:37
- every case ran in its own subprocess, all cases in parallel

| case | result | detail |
|---|---|---|
| click_handling | PASS | no desktop -> ignored; busy -> ignored; occupied -> refused; ok -> launch(4, '/Users/brunowinter2000/Documents/wise2627'), panel closed; bad index ignored |
| headers | PASS | {"sessions": "[Sessions] · RAG · Models · Launch", "rag": "Sessions · [RAG] · Models · Launch", "models": "Sessions · RAG · [Models] · Launch", "launch": "Sessions · RAG · Models · [Launch]"} |
| occupied_marking | PASS | enabled {1: False, 2: True, 3: False, 4: True, 5: True}, titles {1: ' 1*', 2: ' 2 ', 3: ' 3*', 4: ' 4 ', 5: ' 5 '}, select 1 refused, select 2 shows [2] |
| project_rows | PASS | 10 rows in order: ['ai/Meta/ClaudeCode/cli/gh-cli', 'ai/Meta/ClaudeCode/cli/reddit-cli', 'ai/Meta/ClaudeCode/cli/websearch', 'ai/Meta/ClaudeCode/cli/rag-cli', 'ai/Meta/iterative-dev', 'ai/trading', 'ai/trading_ai', 'ai/monitor-cc', 'general', 'wise2627'] |
| space_switch_units | PASS | no PostEvent -> SpaceSwitchError + one CGRequestPostEventAccess | PostEvent granted -> no request | desktop -> space id for 1..5; missing and ambiguous desktop raise | hotkey key codes 18,19,20,21,23 down+up | wait_until_active: returns on target, raises switch_timeout otherwise |
| start_command | PASS | 10 commands match exactly, e.g. cd /Users/brunowinter2000/Documents/ai/monitor-cc && PATH="$HOME/.local/bin:$PATH" ./src/claude_proxy_start.sh --project /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/gh-cli |
| tick_and_selection | PASS | tick: no change -> 0 rebuilds, change -> 1 rebuild, selection cleared, open() resets, closed panel idle |
| workflow_failures | PASS | postevent missing: no window opened, FAILED desktop=2 project=/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/gh-cli stage=switch SpaceSwitchError('postevent_not_granted') | switch timeout: no window opened, FAILED desktop=2 project=/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/gh-cli stage=switch SpaceSwitchError('switch_timeout_3s') | desktop 6: FAILED desktop=6 project=/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/gh-cli stage=validate ValueError('desktop 6 not in (1, 2, 3, 4, 5)') | unknown project: FAILED desktop=2 project=/tmp/not-in-list stage=validate ValueError('project /tmp/not-in-list not in launch list') | osascript rc=1: FAILED desktop=2 project=/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/gh-cli stage=open_window rc=1 stderr=boom |
| workflow_success | PASS | order ['switch', 'sleep', 'open']; log: OK desktop=3 project=/Users/brunowinter2000/Documents/ai/monitor-cc stage=open_window switch_ms=280 active_desktop_after=3 |

RESULT: PASS