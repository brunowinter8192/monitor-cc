# Hotkey/Menubar Latency Report

Source: `/Users/brunowinter2000/Library/Application Support/com.brunowinter.monitor-cc-menubar/menubar.log`
Generated: 2026-09-25T16:46:18+00:00

## Main-Thread Tick Latency (over-threshold ticks only)

Total-duration distribution: n=1261 mean=702.7 median=226.0 p90=2783.0 p95=2884.0 max=4577.0

### Per-Phase Distribution (ms)

- `bg_task_lsof`: n=853 mean=27.8 median=0.0 p90=103.0 p95=105.0 max=138.0
- `bg_timer_scan`: n=853 mean=40.7 median=36.0 p90=54.0 p95=57.0 max=135.0
- `desktop_detection`: n=853 mean=565.8 median=0.0 p90=2432.0 p95=2472.0 max=3724.0
- `focus_tick`: n=1175 mean=0.2 median=0.0 p90=0.0 p95=0.0 max=84.0
- `ghostty`: n=853 mean=150.8 median=152.0 p90=167.0 p95=173.0 max=776.0
- `launch_tick`: n=86 mean=0.4 median=0.0 p90=0.0 p95=0.0 max=30.0
- `panel_rebuild_update`: n=1261 mean=95.9 median=0.0 p90=304.0 p95=467.0 max=3742.0
- `per_project_loop`: n=853 mean=17.3 median=15.0 p90=20.0 p95=21.0 max=1763.0
- `proc_cache`: n=853 mean=37.7 median=0.0 p90=136.0 p95=143.0 max=398.0
- `queue_tick`: n=918 mean=5.9 median=0.0 p90=0.0 p95=2.0 max=491.0
- `rag_tick`: n=1261 mean=29.1 median=0.0 p90=96.0 p95=245.0 max=761.0
- `sessions_refresh_total`: n=853 mean=802.4 median=178.0 p90=2806.0 p95=2858.0 max=4515.0
- `snapshot_consume`: n=408 mean=5.4 median=0.0 p90=0.0 p95=3.0 max=545.0
- `tmux_state`: n=853 mean=3.1 median=0.0 p90=7.0 p95=7.0 max=14.0

### Slowest 10 Entries

- 2026-08-19T18:14:14 total=4577ms — sessions_refresh_total=4515ms desktop_detection=3544ms ghostty=665ms proc_cache=160ms bg_task_lsof=111ms bg_timer_scan=53ms per_project_loop=22ms tmux_state=14ms panel_rebuild_update=8ms focus_tick=0ms queue_tick=0ms rag_tick=0ms
- 2026-08-19T17:56:21 total=4433ms — sessions_refresh_total=4390ms desktop_detection=3255ms ghostty=581ms proc_cache=393ms bg_task_lsof=137ms bg_timer_scan=35ms per_project_loop=19ms panel_rebuild_update=7ms tmux_state=6ms focus_tick=0ms queue_tick=0ms rag_tick=0ms
- 2026-09-03T16:56:25 total=4287ms — panel_rebuild_update=3742ms snapshot_consume=545ms focus_tick=0ms rag_tick=0ms
- 2026-08-19T18:44:51 total=4154ms — sessions_refresh_total=4097ms desktop_detection=3724ms proc_cache=133ms ghostty=117ms bg_task_lsof=103ms bg_timer_scan=56ms per_project_loop=20ms tmux_state=0ms focus_tick=0ms queue_tick=0ms rag_tick=0ms panel_rebuild_update=0ms
- 2026-08-19T18:43:37 total=4071ms — sessions_refresh_total=4012ms desktop_detection=3627ms proc_cache=144ms ghostty=124ms bg_task_lsof=100ms bg_timer_scan=59ms per_project_loop=17ms tmux_state=0ms focus_tick=0ms queue_tick=0ms rag_tick=0ms panel_rebuild_update=0ms
- 2026-08-19T18:14:24 total=4067ms — sessions_refresh_total=4013ms desktop_detection=3630ms ghostty=133ms proc_cache=130ms bg_task_lsof=101ms bg_timer_scan=54ms per_project_loop=13ms tmux_state=5ms focus_tick=0ms queue_tick=0ms rag_tick=0ms panel_rebuild_update=0ms
- 2026-08-19T18:44:09 total=4062ms — sessions_refresh_total=4012ms desktop_detection=3603ms ghostty=156ms proc_cache=128ms bg_task_lsof=105ms bg_timer_scan=49ms per_project_loop=20ms tmux_state=0ms focus_tick=0ms queue_tick=0ms rag_tick=0ms panel_rebuild_update=0ms
- 2026-08-19T18:45:01 total=4054ms — sessions_refresh_total=3999ms desktop_detection=3554ms ghostty=160ms proc_cache=135ms bg_task_lsof=123ms bg_timer_scan=54ms per_project_loop=19ms tmux_state=9ms focus_tick=0ms queue_tick=0ms rag_tick=0ms panel_rebuild_update=0ms
- 2026-08-19T18:15:27 total=4048ms — sessions_refresh_total=4001ms desktop_detection=3643ms proc_cache=127ms ghostty=117ms bg_task_lsof=103ms bg_timer_scan=47ms per_project_loop=11ms tmux_state=0ms focus_tick=0ms queue_tick=0ms rag_tick=0ms panel_rebuild_update=0ms
- 2026-08-19T18:43:58 total=4044ms — sessions_refresh_total=3990ms desktop_detection=3589ms proc_cache=140ms ghostty=132ms bg_task_lsof=109ms bg_timer_scan=53ms per_project_loop=20ms tmux_state=0ms focus_tick=0ms queue_tick=0ms rag_tick=0ms panel_rebuild_update=0ms

## Background Discovery-Worker Cycle Latency (over-threshold cycles only)

Total-duration distribution: n=159022 mean=1712.6 median=1490.0 p90=2811.0 p95=3309.0 max=38675.0

### Per-Phase Distribution (ms)

- `bg_task_lsof`: n=159022 mean=124.7 median=99.0 p90=155.0 p95=172.0 max=13023.0
- `desktop_detection`: n=159022 mean=1169.6 median=1102.0 p90=2294.0 p95=2637.0 max=21409.0
- `ghostty`: n=159022 mean=155.8 median=100.0 p90=154.0 p95=210.0 max=8826.0
- `per_project_loop`: n=159022 mean=35.5 median=13.0 p90=33.0 p95=52.0 max=14074.0
- `proc_cache`: n=159022 mean=139.9 median=107.0 p90=152.0 p95=194.0 max=6942.0
- `tmux_state`: n=159022 mean=9.4 median=0.0 p90=15.0 p95=21.0 max=4644.0

### Slowest 10 Entries

- 2026-09-03T16:49:37 total=38675ms — per_project_loop=12155ms proc_cache=4774ms tmux_state=4613ms bg_task_lsof=4276ms ghostty=3449ms desktop_detection=3023ms
- 2026-09-03T16:55:17 total=37391ms — per_project_loop=10027ms desktop_detection=5954ms bg_task_lsof=3809ms proc_cache=3529ms ghostty=2794ms tmux_state=1931ms
- 2026-09-03T16:47:55 total=32443ms — per_project_loop=12390ms desktop_detection=3753ms bg_task_lsof=3715ms proc_cache=3644ms ghostty=2856ms tmux_state=1072ms
- 2026-09-03T16:48:27 total=32296ms — per_project_loop=11529ms proc_cache=4907ms bg_task_lsof=3779ms ghostty=3098ms desktop_detection=3033ms tmux_state=2394ms
- 2026-09-03T16:48:59 total=31170ms — per_project_loop=8697ms desktop_detection=5480ms proc_cache=3933ms bg_task_lsof=3616ms ghostty=3084ms tmux_state=1466ms
- 2026-09-03T16:56:18 total=30829ms — per_project_loop=10182ms proc_cache=4141ms bg_task_lsof=3756ms desktop_detection=3479ms ghostty=3323ms tmux_state=1136ms
- 2026-09-03T16:55:47 total=30447ms — proc_cache=6942ms bg_task_lsof=5712ms desktop_detection=4679ms ghostty=4248ms per_project_loop=2777ms tmux_state=1225ms
- 2026-09-03T16:44:41 total=30373ms — per_project_loop=10739ms tmux_state=4644ms proc_cache=3875ms bg_task_lsof=3367ms desktop_detection=2369ms ghostty=2272ms
- 2026-09-03T16:50:05 total=28252ms — per_project_loop=5663ms bg_task_lsof=5016ms proc_cache=4955ms tmux_state=3279ms desktop_detection=2868ms ghostty=2709ms
- 2026-08-28T21:54:33 total=28191ms — per_project_loop=8563ms desktop_detection=7397ms ghostty=4951ms proc_cache=3151ms bg_task_lsof=2596ms tmux_state=678ms

## Hotkey Queue-Delay (queue_delay_ms = handler-entry time - Carbon event timestamp)

Overall: n=12296 mean=0.6 median=0.2 p90=0.3 p95=0.4 max=2394.8

### Per Hotkey

- `cmd+1`: n=776 mean=0.2 median=0.1 p90=0.2 p95=0.3 max=10.6
- `cmd+2`: n=982 mean=0.9 median=0.1 p90=0.2 p95=0.3 max=214.4
- `cmd+3`: n=575 mean=0.2 median=0.2 p90=0.3 p95=0.3 max=12.3
- `cmd+4`: n=624 mean=0.2 median=0.2 p90=0.3 p95=0.3 max=2.9
- `cmd+5`: n=32 mean=0.2 median=0.2 p90=0.3 p95=0.3 max=0.4
- `cmd+k`: n=8838 mean=0.6 median=0.2 p90=0.3 p95=0.4 max=2394.8
- `cmd+l`: n=166 mean=2.5 median=0.2 p90=0.5 p95=0.6 max=134.4
- `cmd+left`: n=124 mean=0.2 median=0.1 p90=0.2 p95=0.3 max=0.4
- `cmd+right`: n=179 mean=0.2 median=0.1 p90=0.2 p95=0.3 max=0.5

## Focus-Path Timing (_focus_session)

- `lookup_ms` (get_ghostty_terminal_id): n=3696 mean=0.0 median=0.0 p90=0.1 p95=0.1 max=7.3
- `osascript_ms` (osascript run): n=3696 mean=110.8 median=103.4 p90=122.4 p95=130.4 max=3795.7
